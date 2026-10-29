"""Step 5: export SMALL aggregated tables for the dashboard.

The full database is several GB and can't go on GitHub, but these summaries are
only a few MB, so the dashboard can be deployed for free on Streamlit Community Cloud.
"""
import shutil

from src import config
from src.db import connect

MART_TABLES = [
    "mart_daily_kpis",
    "mart_weekly_metric_tree",
    "mart_funnel_by_segment",
    "mart_weekly_segment_conversion",
    "mart_cohort_retention",
    "stg_cleaning_log",
]
OUTPUT_FILES = [
    "rca_summary.md", "rca_decomposition.csv", "rca_weekly_conversion.csv",
    "clv_metrics.json", "clv_holdout_by_frequency.csv", "clv_deciles.csv",
    "experiment_design.json", "experiment_power_table.csv", "experiment_plan.md",
    "experiment_baseline_by_category.csv",
]


def run() -> None:
    config.DASH_DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = connect(read_only=True)
    for t in MART_TABLES:
        out = config.DASH_DATA_DIR / f"{t}.parquet"
        con.execute(f"COPY {t} TO '{out.as_posix()}' (FORMAT PARQUET)")
        print(f"[export] {t} -> {out.relative_to(config.ROOT)}")
    con.close()
    for f in OUTPUT_FILES:
        src = config.OUTPUT_DIR / f
        if src.exists():
            shutil.copy(src, config.DASH_DATA_DIR / f)
        else:
            print(f"[export] (skipped {f}: run the analysis step first)")
    print(f"[export] done -> {config.DASH_DATA_DIR.relative_to(config.ROOT)}")


if __name__ == "__main__":
    run()
