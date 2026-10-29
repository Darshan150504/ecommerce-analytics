"""Design a cart-abandonment reminder-email A/B test from the baseline you measured.

Question: "If we email users who abandon a cart, do more of them buy within 7 days?"
  - Unit of randomization: user (first abandonment during the test enrolls them)
  - Primary metric: 7-day purchase rate after abandonment ("recovery rate")
  - Control baseline: the natural recovery rate measured in mart_cart_abandonment

What this script does:
  1. Measures the baseline recovery rate and how many users abandon carts per week
  2. Computes sample size per arm for several minimum detectable effects (MDEs)
  3. Verifies the formula by simulation (empirical power ~ target power)
  4. Runs an A/A simulation (false-positive rate ~ alpha)
  5. Writes a filled-in test plan to outputs/experiment_plan.md

Usage:  python -m src.experiment
"""
import json
import math

import numpy as np
import pandas as pd
from scipy import stats

from src import config
from src.db import connect

RNG = np.random.default_rng(7)


def sample_size_per_arm(p0: float, rel_mde: float, alpha: float, power: float) -> int:
    """Two-sided two-proportion z-test sample size (normal approximation)."""
    p1 = p0 * (1 + rel_mde)
    z_a, z_b = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    p_bar = (p0 + p1) / 2
    n = (z_a * math.sqrt(2 * p_bar * (1 - p_bar)) + z_b * math.sqrt(p0 * (1 - p0) + p1 * (1 - p1))) ** 2 / (p1 - p0) ** 2
    return math.ceil(n)


def analyze(conv_c: int, n_c: int, conv_t: int, n_t: int, alpha: float = 0.05) -> dict:
    """Readout for a finished test: lift, 95% CI, p-value, and a sample-ratio-mismatch check."""
    p_c, p_t = conv_c / n_c, conv_t / n_t
    p_pool = (conv_c + conv_t) / (n_c + n_t)
    se_pool = math.sqrt(p_pool * (1 - p_pool) * (1 / n_c + 1 / n_t))
    z = (p_t - p_c) / se_pool
    p_value = 2 * (1 - stats.norm.cdf(abs(z)))
    se = math.sqrt(p_c * (1 - p_c) / n_c + p_t * (1 - p_t) / n_t)
    z_ci = stats.norm.ppf(1 - alpha / 2)
    srm_p = stats.chisquare([n_c, n_t]).pvalue          # expected 50/50 split
    return {"control_rate": p_c, "treatment_rate": p_t, "abs_lift": p_t - p_c,
            "rel_lift": (p_t - p_c) / p_c if p_c else float("nan"),
            "ci_low": p_t - p_c - z_ci * se, "ci_high": p_t - p_c + z_ci * se,
            "p_value": p_value, "srm_p_value": srm_p, "srm_alert": srm_p < 0.001}


def simulated_power(p0: float, rel_mde: float, n: int, alpha: float, sims: int = 2000) -> float:
    c = RNG.binomial(n, p0, sims)
    t = RNG.binomial(n, p0 * (1 + rel_mde), sims)
    return float(np.mean([analyze(ci, n, ti, n, alpha)["p_value"] < alpha for ci, ti in zip(c, t)]))


def _markdown_table(df: pd.DataFrame) -> str:
    """Markdown table without needing the optional `tabulate` package."""
    fmt = lambda v: f"{v:.4f}" if isinstance(v, float) else f"{v:,}" if isinstance(v, (int, np.integer)) else str(v)
    head = "| " + " | ".join(df.columns) + " |\n|" + "---|" * len(df.columns)
    body = "\n".join("| " + " | ".join(fmt(v) for v in row) + " |" for row in df.itertuples(index=False))
    return head + "\n" + body


def run() -> None:
    con = connect(read_only=True)
    weekly = con.execute("""
        WITH user_week AS (
            SELECT session_week AS week, user_id, BOOL_OR(recovered_7d) AS recovered
            FROM mart_cart_abandonment
            GROUP BY ALL
        )
        SELECT uw.week, COUNT(*) AS abandoning_users, AVG(recovered::INT) AS recovery_rate
        FROM user_week uw
        JOIN mart_weekly_metric_tree t USING (week)
        WHERE t.is_full_week
        GROUP BY uw.week
        ORDER BY uw.week
    """).fetchdf()
    by_cat = con.execute("""
        SELECT entry_category AS category, COUNT(DISTINCT user_id) AS abandoning_users,
               AVG(recovered_7d::INT) AS session_recovery_rate
        FROM mart_cart_abandonment GROUP BY 1 ORDER BY 2 DESC
    """).fetchdf()
    con.close()

    # A user who abandons in several weeks is enrolled once, so weekly counts slightly
    # overstate how fast unique users accumulate - fine for a planning estimate.
    full = weekly[weekly["abandoning_users"] > 0]
    if full.empty:
        raise SystemExit("No complete weeks of cart-abandonment data found.")
    p0 = float(np.average(full["recovery_rate"], weights=full["abandoning_users"]))
    weekly_users = float(full["abandoning_users"].mean())
    alpha, power = config.EXPERIMENT_ALPHA, config.EXPERIMENT_POWER

    rows = []
    for mde in config.EXPERIMENT_RELATIVE_MDES:
        n = sample_size_per_arm(p0, mde, alpha, power)
        days = math.ceil(2 * n / (weekly_users / 7))
        rows.append({"relative_mde": mde, "treatment_rate": p0 * (1 + mde), "n_per_arm": n,
                     "total_users": 2 * n, "days_needed": days,
                     "weeks_needed_rounded": max(1, math.ceil(days / 7))})
    table = pd.DataFrame(rows)

    # Pick the smallest MDE that can finish within 4 weeks (or the largest MDE otherwise)
    feasible = table[table["weeks_needed_rounded"] <= 4]
    chosen = (feasible.iloc[0] if not feasible.empty else table.iloc[-1]).to_dict()
    emp_power = simulated_power(p0, chosen["relative_mde"], int(chosen["n_per_arm"]), alpha)
    aa = RNG.binomial(int(chosen["n_per_arm"]), p0, (2000, 2))
    aa_fpr = float(np.mean([analyze(a, int(chosen["n_per_arm"]), b, int(chosen["n_per_arm"]), alpha)["p_value"] < alpha
                            for a, b in aa]))

    design = {"baseline_recovery_rate": p0, "avg_weekly_abandoning_users": weekly_users,
              "alpha": alpha, "power": power, "chosen_design": chosen,
              "simulated_power_at_chosen_n": emp_power, "aa_false_positive_rate": aa_fpr}

    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(config.OUTPUT_DIR / "experiment_power_table.csv", index=False)
    weekly.to_csv(config.OUTPUT_DIR / "experiment_weekly_baseline.csv", index=False)
    by_cat.to_csv(config.OUTPUT_DIR / "experiment_baseline_by_category.csv", index=False)
    (config.OUTPUT_DIR / "experiment_design.json").write_text(json.dumps(design, indent=2, default=float))

    weeks = int(chosen["weeks_needed_rounded"])
    plan = f"""# Experiment plan: cart-abandonment reminder email

## Hypothesis
Sending a reminder email 1 hour after a user abandons a cart increases the share of
abandoning users who purchase within {config.RECOVERY_WINDOW_DAYS} days.

## Design
| Item | Choice |
|---|---|
| Unit of randomization | User (enrolled at first cart abandonment during the test) |
| Split | 50% control (no email) / 50% treatment (email) |
| Primary metric | {config.RECOVERY_WINDOW_DAYS}-day purchase rate after abandonment |
| Baseline (control) rate | {p0:.2%} (measured from historical data) |
| Eligible users per week | ~{weekly_users:,.0f} |
| Significance level / power | {alpha:.0%} two-sided / {power:.0%} |
| Minimum detectable effect | {chosen['relative_mde']:.1%} relative ({p0:.2%} -> {chosen['treatment_rate']:.2%}) |
| Sample size | {int(chosen['n_per_arm']):,} users per arm ({int(chosen['total_users']):,} total) |
| Duration | {int(chosen['days_needed'])} days, run for {weeks} full week(s) to cover weekday effects |

## Guardrail metrics
- Unsubscribe and spam-complaint rate (must not rise meaningfully)
- Average order value of recovered purchases (no shift to discount-driven, low-value orders)
- Revenue per enrolled user (the business outcome, reported alongside the primary metric)

## Validity checks
- Sample ratio mismatch: chi-square test on the 50/50 split; alert if p < 0.001
- Simulated power at the chosen sample size: {emp_power:.1%} (target {power:.0%})
- A/A simulation false-positive rate: {aa_fpr:.1%} (target {alpha:.0%})
- No peeking: analyse once at the planned sample size (or use a sequential method)

## Decision rule
Ship if the primary metric improves with p < {alpha} and no guardrail is significantly worse.
If the effect is positive but smaller than the MDE, consider a longer test only if the
expected revenue gain justifies it.

## Power table
{_markdown_table(table)}
"""
    (config.OUTPUT_DIR / "experiment_plan.md").write_text(plan)
    print(f"[experiment] baseline 7-day recovery rate = {p0:.2%}, ~{weekly_users:,.0f} abandoning users/week")
    print(table.to_string(index=False))
    print(f"[experiment] chosen MDE {chosen['relative_mde']:.1%}: {int(chosen['n_per_arm']):,} per arm, "
          f"{weeks} week(s); simulated power {emp_power:.1%}; A/A false positives {aa_fpr:.1%}")


if __name__ == "__main__":
    run()
