"""Sanity check for the hand-written CLV models: simulate customers from KNOWN
parameters, fit the models, and confirm they recover the truth.
Run:  python -m tests.test_clv_models   (or `pytest tests/` if you install pytest)
"""
import numpy as np
import pandas as pd

from src.clv import bgnbd_expected_purchases, fit_bgnbd, fit_gamma_gamma

RNG = np.random.default_rng(0)


def simulate_bgnbd(n, r, alpha, a, b, T_cal, t_hold):
    lam = RNG.gamma(r, 1 / alpha, n)
    p = RNG.beta(a, b, n)
    T = RNG.uniform(T_cal * 0.3, T_cal, n)            # customers joined at different times
    rows = []
    for i in range(n):
        t, alive, times = 0.0, True, []
        while alive:
            t += RNG.exponential(1 / lam[i])
            if t > T[i] + t_hold:
                break
            times.append(t)
            alive = RNG.random() > p[i]                # may drop out after each purchase
        cal = [s for s in times if s <= T[i]]
        rows.append((len(cal), cal[-1] if cal else 0.0, T[i], sum(1 for s in times if s > T[i])))
    return pd.DataFrame(rows, columns=["frequency", "recency", "T", "holdout"])


def test_bgnbd_recovers_parameters_and_predicts_holdout():
    true = dict(r=0.25, alpha=4.0, a=0.8, b=2.5)
    df = simulate_bgnbd(20_000, **true, T_cal=40, t_hold=20)
    est = fit_bgnbd(df)
    for k in true:
        assert abs(est[k] - true[k]) / true[k] < 0.25, (k, est[k], true[k])
    pred = bgnbd_expected_purchases(est, 20, df["frequency"], df["recency"], df["T"])
    rel_err = pred.sum() / df["holdout"].sum() - 1
    assert abs(rel_err) < 0.10, rel_err
    print(f"BG/NBD OK  estimated={ {k: round(v, 3) for k, v in est.items() if k != 'converged'} }  "
          f"true={true}  holdout error={rel_err:+.1%}")


def test_gamma_gamma_recovers_parameters():
    true = dict(p=6.0, q=4.0, gamma=50.0)
    n = 20_000
    x = RNG.integers(1, 10, n)
    nu = RNG.gamma(true["q"], 1 / true["gamma"], n)             # customer-level spend rate
    m = np.array([RNG.gamma(true["p"], 1 / nu[i], x[i]).mean() for i in range(n)])
    est = fit_gamma_gamma(pd.DataFrame({"frequency": x, "monetary_value": m}))
    implied_true = true["p"] * true["gamma"] / (true["q"] - 1)
    implied_est = est["p"] * est["gamma"] / (est["q"] - 1)
    assert abs(implied_est / implied_true - 1) < 0.10
    print(f"Gamma-Gamma OK  mean order value est={implied_est:.2f} true={implied_true:.2f}")


if __name__ == "__main__":
    test_bgnbd_recovers_parameters_and_predicts_holdout()
    test_gamma_gamma_recovers_parameters()
