"""Root-cause analysis: "Session conversion dropped X% in week W. Why?"

Method: mix/rate decomposition. Overall conversion is a weighted average of
segment conversions:   C = sum_i  share_i * rate_i
so the week-over-week change splits EXACTLY into
    mix effect  = sum_i (share_i,cur - share_i,prev) * rate_i,prev   (traffic moved between segments)
    rate effect = sum_i  share_i,cur * (rate_i,cur - rate_i,prev)    (segments themselves converted worse/better)
Done for each dimension (category, price band, new vs returning), this tells you
whether the drop came from WHO showed up or from something BREAKING in a segment.

Usage:  python -m src.rca                  (auto-picks the full week with the biggest drop)
        python -m src.rca --week 2019-11-11
"""
from __future__ import annotations

import argparse

import pandas as pd

from src import config
from src.db import connect


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    con = connect(read_only=True)
    seg = con.execute("SELECT * FROM mart_weekly_segment_conversion").fetchdf()
    weeks = con.execute("SELECT week, is_full_week FROM mart_weekly_metric_tree").fetchdf()
    con.close()
    for df in (seg, weeks):
        df["week"] = pd.to_datetime(df["week"])
    return seg, weeks


def weekly_totals(seg: pd.DataFrame, full_weeks: list) -> pd.DataFrame:
    t = (seg[seg["dimension"] == "category"]          # any one dimension sums to the total
         .groupby("week")[["sessions", "purchase_sessions"]].sum())
    t["conversion"] = t["purchase_sessions"] / t["sessions"]
    t = t.loc[t.index.isin(full_weeks)]
    t["wow_change"] = t["conversion"].diff()
    t["wow_change_pct"] = t["conversion"].pct_change()
    return t


def decompose(seg: pd.DataFrame, week: pd.Timestamp, prev: pd.Timestamp) -> pd.DataFrame:
    out = []
    for dim, d in seg[seg["week"].isin([week, prev])].groupby("dimension"):
        p = d.pivot_table(index="segment", columns="week",
                          values=["sessions", "purchase_sessions"], aggfunc="sum").fillna(0)
        s0, s1 = p["sessions"][prev], p["sessions"][week]
        c0, c1 = p["purchase_sessions"][prev], p["purchase_sessions"][week]
        share0, share1 = s0 / s0.sum(), s1 / s1.sum()
        rate0 = (c0 / s0.where(s0 > 0)).fillna(0)
        rate1 = (c1 / s1.where(s1 > 0)).fillna(0)
        r = pd.DataFrame({
            "dimension": dim,
            "sessions_prev": s0, "sessions_cur": s1,
            "share_prev": share0, "share_cur": share1,
            "rate_prev": rate0, "rate_cur": rate1,
            "mix_effect": (share1 - share0) * rate0,
            "rate_effect": share1 * (rate1 - rate0),
        })
        r["total_effect"] = r["mix_effect"] + r["rate_effect"]
        out.append(r.reset_index())
    res = pd.concat(out, ignore_index=True)
    res["abs_effect"] = res["total_effect"].abs()
    return res.sort_values(["dimension", "abs_effect"], ascending=[True, False]).drop(columns="abs_effect")


def run(week: str | None = None) -> None:
    seg, weeks = load()
    full = weeks.loc[weeks["is_full_week"], "week"].tolist()
    totals = weekly_totals(seg, full)
    if len(totals) < 2:
        raise SystemExit("Need at least two full weeks of data for RCA.")

    if week:
        target = pd.Timestamp(week)
    else:
        target = totals["wow_change_pct"].idxmin()   # biggest relative week-over-week drop
    prev_candidates = [w for w in totals.index if w < target]
    if target not in totals.index or not prev_candidates:
        raise SystemExit(f"{target.date()} is not a full week with a previous full week.")
    prev = max(prev_candidates)

    res = decompose(seg, target, prev)
    total_change = totals.loc[target, "conversion"] - totals.loc[prev, "conversion"]

    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    totals.reset_index().to_csv(config.OUTPUT_DIR / "rca_weekly_conversion.csv", index=False)
    res.to_csv(config.OUTPUT_DIR / "rca_decomposition.csv", index=False)

    lines = [
        f"# Root-cause analysis: week of {target.date()} vs {prev.date()}",
        "",
        f"Session conversion went from {totals.loc[prev, 'conversion']:.3%} to "
        f"{totals.loc[target, 'conversion']:.3%} "
        f"({total_change * 100:+.3f} pp, {totals.loc[target, 'wow_change_pct']:+.1%} relative).",
        "",
    ]
    for dim, d in res.groupby("dimension"):
        check = d["total_effect"].sum()
        lines += [f"## By {dim}",
                  f"Mix effect {d['mix_effect'].sum() * 100:+.3f} pp | rate effect {d['rate_effect'].sum() * 100:+.3f} pp "
                  f"(sums to {check * 100:+.3f} pp)", "",
                  "| segment | share prev -> cur | conversion prev -> cur | contribution (pp) |",
                  "|---|---|---|---|"]
        for _, r in d.head(5).iterrows():
            lines.append(f"| {r['segment']} | {r['share_prev']:.1%} -> {r['share_cur']:.1%} | "
                         f"{r['rate_prev']:.2%} -> {r['rate_cur']:.2%} | {r['total_effect'] * 100:+.3f} |")
        lines.append("")
    top = res.loc[res["total_effect"].idxmin()]
    lines += ["## Biggest single driver",
              f"**{top['dimension']} = {top['segment']}**: contributed {top['total_effect'] * 100:+.3f} pp "
              f"(rate effect {top['rate_effect'] * 100:+.3f} pp, mix effect {top['mix_effect'] * 100:+.3f} pp).",
              "", "Next step: drill into that segment (brands, products, hours) to confirm the cause."]
    report = "\n".join(lines)
    (config.OUTPUT_DIR / "rca_summary.md").write_text(report)
    print(report)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", help="Monday of the week to explain, e.g. 2019-11-11")
    run(ap.parse_args().week)
