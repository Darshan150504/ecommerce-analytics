"""Predictive customer lifetime value: BG/NBD (how often) + Gamma-Gamma (how much).

Both models are implemented from the original papers with numpy/scipy, so there's
no dependency on the unmaintained `lifetimes` package and you can explain every line:
  - Fader, Hardie & Lee (2005), "Counting Your Customers the Easy Way" (BG/NBD)
  - Fader, Hardie & Lee (2005), "RFM and CLV: Using Iso-Value Curves" (Gamma-Gamma)

Validation: fit on purchases before CLV_CALIBRATION_END, then predict each customer's
number of purchase days in the holdout period and compare with what actually happened,
against a naive baseline (each customer keeps their historical repeat-purchase rate).

Usage:  python -m src.clv
"""
import json

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import betaln, gammaln, hyp2f1

from src import config
from src.db import connect


# ---------------------------------------------------------------- data prep
def rfm_summary(tx: pd.DataFrame, calibration_end: pd.Timestamp, holdout_end: pd.Timestamp) -> pd.DataFrame:
    """Per-customer frequency / recency / T (in days) for the calibration period,
    plus actual holdout purchase days and revenue."""
    cal = tx[tx["purchase_date"] < calibration_end]
    hold = tx[(tx["purchase_date"] >= calibration_end) & (tx["purchase_date"] < holdout_end)]

    g = cal.groupby("user_id")
    first, last = g["purchase_date"].min(), g["purchase_date"].max()
    df = pd.DataFrame({
        "frequency": g.size() - 1,                                   # REPEAT purchase days
        "recency": (last - first).dt.days,                           # first -> last purchase
        "T": (calibration_end - first).dt.days,                      # first purchase -> end of calibration
    })
    # Gamma-Gamma uses the average value of REPEAT transactions (exclude the first)
    cal_sorted = cal.sort_values(["user_id", "purchase_date"])
    repeat = cal_sorted[cal_sorted.groupby("user_id").cumcount() > 0]
    df["monetary_value"] = repeat.groupby("user_id")["revenue"].mean()
    df["monetary_value"] = df["monetary_value"].fillna(0.0)

    h = hold.groupby("user_id").agg(holdout_purchases=("purchase_date", "size"),
                                    holdout_revenue=("revenue", "sum"))
    df = df.join(h, how="left").fillna({"holdout_purchases": 0, "holdout_revenue": 0.0})
    return df[df["T"] > 0]


# ---------------------------------------------------------------- BG/NBD
def bgnbd_loglik(params, x, tx, T, w):
    r, alpha, a, b = params
    ln_a1 = gammaln(r + x) - gammaln(r) + r * np.log(alpha)
    ln_a2 = betaln(a, b + x) - betaln(a, b) - (r + x) * np.log(alpha + T)
    ln_a3 = np.where(
        x > 0,
        betaln(a + 1, np.maximum(b + x - 1, 1e-12)) - betaln(a, b) - (r + x) * np.log(alpha + tx),
        -np.inf,
    )
    return np.sum(w * (ln_a1 + np.logaddexp(ln_a2, ln_a3)))


def fit_bgnbd(df: pd.DataFrame) -> dict:
    # Collapse identical (x, t_x, T) rows -> much faster on hundreds of thousands of customers
    agg = df.groupby(["frequency", "recency", "T"]).size().reset_index(name="w")
    x, tx, T, w = (agg[c].to_numpy(float) for c in ["frequency", "recency", "T", "w"])

    def nll(log_params):
        return -bgnbd_loglik(np.exp(log_params), x, tx, T, w) / w.sum()

    res = minimize(nll, x0=np.log([0.5, 10.0, 1.0, 3.0]), method="Nelder-Mead",
                   options={"maxiter": 5000, "xatol": 1e-6, "fatol": 1e-10})
    r, alpha, a, b = (float(v) for v in np.exp(res.x))
    if abs(a - 1) < 1e-3:
        print("[clv] warning: fitted a is ~1, where the expectation formula is undefined")
    return {"r": r, "alpha": alpha, "a": a, "b": b, "converged": bool(res.success)}


def bgnbd_expected_purchases(p: dict, t: float, x, tx, T):
    """E[# purchase days in (T, T+t] | x, t_x, T]  (Fader et al. 2005, eq. 10)."""
    r, alpha, a, b = p["r"], p["alpha"], p["a"], p["b"]
    x, tx, T = (np.asarray(v, float) for v in (x, tx, T))
    hyp = hyp2f1(r + x, b + x, a + b + x - 1, t / (alpha + T + t))
    numer = (a + b + x - 1) / (a - 1) * (1 - ((alpha + T) / (alpha + T + t)) ** (r + x) * hyp)
    denom = 1 + (x > 0) * (a / np.maximum(b + x - 1, 1e-12)) * ((alpha + T) / (alpha + tx)) ** (r + x)
    return numer / denom


def bgnbd_prob_alive(p: dict, x, tx, T):
    r, alpha, a, b = p["r"], p["alpha"], p["a"], p["b"]
    x, tx, T = (np.asarray(v, float) for v in (x, tx, T))
    return 1.0 / (1 + (x > 0) * (a / np.maximum(b + x - 1, 1e-12)) * ((alpha + T) / (alpha + tx)) ** (r + x))


# ---------------------------------------------------------------- Gamma-Gamma
def fit_gamma_gamma(df: pd.DataFrame) -> dict:
    d = df[(df["frequency"] > 0) & (df["monetary_value"] > 0)]
    x, m = d["frequency"].to_numpy(float), d["monetary_value"].to_numpy(float)

    def nll(log_params):
        p, q, g = np.exp(log_params)
        ll = (gammaln(p * x + q) - gammaln(p * x) - gammaln(q) + q * np.log(g)
              + (p * x - 1) * np.log(m) + p * x * np.log(x) - (p * x + q) * np.log(x * m + g))
        return -ll.mean()

    res = minimize(nll, x0=np.log([1.0, 3.0, max(m.mean(), 1.0)]), method="Nelder-Mead",
                   options={"maxiter": 5000, "xatol": 1e-6, "fatol": 1e-10})
    p, q, g = (float(v) for v in np.exp(res.x))
    return {"p": p, "q": q, "gamma": g, "converged": bool(res.success)}


def gg_expected_value(p: dict, x, m, population_mean: float):
    """E[average transaction value | x, m]. Customers with no repeat purchases
    get the population mean p*gamma/(q-1)."""
    x, m = np.asarray(x, float), np.asarray(m, float)
    cond = p["p"] * (p["gamma"] + x * m) / (p["p"] * x + p["q"] - 1)
    return np.where(x > 0, cond, population_mean)


# ---------------------------------------------------------------- main
def run() -> None:
    con = connect(read_only=True)
    tx = con.execute("SELECT user_id, purchase_date, revenue FROM mart_user_daily_purchases").fetchdf()
    con.close()
    tx["purchase_date"] = pd.to_datetime(tx["purchase_date"])

    cal_end, hold_end = pd.Timestamp(config.CLV_CALIBRATION_END), pd.Timestamp(config.CLV_HOLDOUT_END)
    hold_end = min(hold_end, tx["purchase_date"].max() + pd.Timedelta(days=1))
    holdout_days = (hold_end - cal_end).days

    df = rfm_summary(tx, cal_end, hold_end)
    print(f"[clv] {len(df):,} customers in calibration; {int((df['frequency'] > 0).sum()):,} repeat buyers; "
          f"holdout = {holdout_days} days")

    # --- frequency model
    bg = fit_bgnbd(df)
    print("[clv] BG/NBD params: " + ", ".join(f"{k}={v:.4f}" for k, v in bg.items() if k != "converged"))
    df["pred_holdout_purchases"] = bgnbd_expected_purchases(bg, holdout_days, df["frequency"], df["recency"], df["T"])
    # Naive baseline: each customer keeps repeating at their historical repeat rate
    df["naive_holdout_purchases"] = df["frequency"] / df["T"].clip(lower=1) * holdout_days
    df["prob_alive"] = bgnbd_prob_alive(bg, df["frequency"], df["recency"], df["T"])

    # --- spend model
    gg = fit_gamma_gamma(df)
    pop_mean = gg["p"] * gg["gamma"] / (gg["q"] - 1) if gg["q"] > 1 else df.loc[df["frequency"] > 0, "monetary_value"].mean()
    rep = df[df["frequency"] > 0]
    corr = float(np.corrcoef(rep["frequency"], rep["monetary_value"])[0, 1]) if len(rep) > 2 else float("nan")
    print(f"[clv] Gamma-Gamma params: p={gg['p']:.3f}, q={gg['q']:.3f}, gamma={gg['gamma']:.3f}; "
          f"freq-spend correlation={corr:.3f} (should be near 0 for Gamma-Gamma to be valid)")
    df["expected_order_value"] = gg_expected_value(gg, df["frequency"], df["monetary_value"], pop_mean)

    # --- holdout evaluation
    df["pred_holdout_revenue"] = df["pred_holdout_purchases"] * df["expected_order_value"]
    mae_model = (df["pred_holdout_purchases"] - df["holdout_purchases"]).abs().mean()
    mae_naive = (df["naive_holdout_purchases"] - df["holdout_purchases"]).abs().mean()
    metrics = {
        "customers": int(len(df)),
        "repeat_buyers": int((df["frequency"] > 0).sum()),
        "holdout_days": holdout_days,
        "actual_holdout_purchases": float(df["holdout_purchases"].sum()),
        "predicted_holdout_purchases": float(df["pred_holdout_purchases"].sum()),
        "naive_holdout_purchases": float(df["naive_holdout_purchases"].sum()),
        "aggregate_error_pct_model": float(df["pred_holdout_purchases"].sum() / df["holdout_purchases"].sum() - 1),
        "aggregate_error_pct_naive": float(df["naive_holdout_purchases"].sum() / df["holdout_purchases"].sum() - 1),
        "mae_per_customer_model": float(mae_model),
        "mae_per_customer_naive": float(mae_naive),
        "actual_holdout_revenue": float(df["holdout_revenue"].sum()),
        "predicted_holdout_revenue": float(df["pred_holdout_revenue"].sum()),
        "freq_spend_correlation": corr,
        "bgnbd_params": bg,
        "gamma_gamma_params": gg,
    }

    # Calibration-vs-holdout chart data: by number of repeat purchases
    df["freq_bucket"] = df["frequency"].clip(upper=7).astype(int).astype(str).replace({"7": "7+"})
    by_freq = (df.groupby("freq_bucket")
                 .agg(customers=("frequency", "size"),
                      actual=("holdout_purchases", "mean"),
                      predicted=("pred_holdout_purchases", "mean"),
                      naive=("naive_holdout_purchases", "mean"))
                 .reset_index())

    # --- forward-looking CLV (refit on ALL data, project CLV_HORIZON_DAYS ahead)
    full = rfm_summary(tx, hold_end, hold_end)
    bg_full = fit_bgnbd(full)
    gg_full = fit_gamma_gamma(full)
    pop_full = gg_full["p"] * gg_full["gamma"] / (gg_full["q"] - 1) if gg_full["q"] > 1 else pop_mean
    full["expected_purchases"] = bgnbd_expected_purchases(bg_full, config.CLV_HORIZON_DAYS,
                                                          full["frequency"], full["recency"], full["T"])
    full["prob_alive"] = bgnbd_prob_alive(bg_full, full["frequency"], full["recency"], full["T"])
    full["expected_order_value"] = gg_expected_value(gg_full, full["frequency"], full["monetary_value"], pop_full)
    full["clv"] = full["expected_purchases"] * full["expected_order_value"] * config.CLV_MARGIN
    full["clv_decile"] = pd.qcut(full["clv"].rank(method="first"), 10, labels=False) + 1   # 10 = most valuable
    deciles = (full.groupby("clv_decile")
                   .agg(customers=("clv", "size"), avg_clv=("clv", "mean"), total_clv=("clv", "sum"),
                        avg_prob_alive=("prob_alive", "mean"), avg_past_purchases=("frequency", "mean"))
                   .reset_index())
    deciles["share_of_total_clv"] = deciles["total_clv"] / deciles["total_clv"].sum()
    metrics["top_decile_share_of_clv"] = float(deciles.loc[deciles["clv_decile"] == 10, "share_of_total_clv"].iloc[0])
    metrics["clv_horizon_days"] = config.CLV_HORIZON_DAYS

    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (config.OUTPUT_DIR / "clv_metrics.json").write_text(json.dumps(metrics, indent=2, default=float))
    by_freq.to_csv(config.OUTPUT_DIR / "clv_holdout_by_frequency.csv", index=False)
    deciles.to_csv(config.OUTPUT_DIR / "clv_deciles.csv", index=False)
    full.reset_index().to_parquet(config.OUTPUT_DIR / "clv_customers.parquet", index=False)

    print(f"[clv] holdout purchases: actual {metrics['actual_holdout_purchases']:,.0f} | "
          f"model {metrics['predicted_holdout_purchases']:,.0f} ({metrics['aggregate_error_pct_model']:+.1%}) | "
          f"naive {metrics['naive_holdout_purchases']:,.0f} ({metrics['aggregate_error_pct_naive']:+.1%})")
    print(f"[clv] per-customer MAE: model {mae_model:.4f} vs naive {mae_naive:.4f}")
    print(f"[clv] top 10% of customers hold {metrics['top_decile_share_of_clv']:.1%} of {config.CLV_HORIZON_DAYS}-day CLV")
    print(by_freq.to_string(index=False))


if __name__ == "__main__":
    run()
