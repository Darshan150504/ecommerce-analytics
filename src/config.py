"""Central configuration: paths, dates and DuckDB settings.

Set the environment variable ECOM_ENV=sample to run the whole project on the
small synthetic dataset (useful for testing before downloading the real data).
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = os.environ.get("ECOM_ENV", "full").lower() == "sample"

DATA_DIR = ROOT / ("data/sample" if SAMPLE else "data")
RAW_DIR = DATA_DIR / "raw"            # Kaggle CSVs go here
PARQUET_DIR = DATA_DIR / "parquet"    # compressed copies (created by load step)
TMP_DIR = DATA_DIR / "tmp"            # DuckDB spill-to-disk folder
DB_PATH = DATA_DIR / "ecom.duckdb"

SQL_DIR = ROOT / "sql"
OUTPUT_DIR = ROOT / ("outputs/sample" if SAMPLE else "outputs")
DASH_DATA_DIR = ROOT / "dashboard" / ("data_sample" if SAMPLE else "data")

# Monthly files from the Kaggle dataset you want to use (file names without .csv)
MONTHS = ["2019-Oct", "2019-Nov"]

# Laptop-friendly DuckDB settings (an 8 GB M1 is fine with 4GB here)
DUCKDB_MEMORY_LIMIT = os.environ.get("ECOM_MEMORY_LIMIT", "4GB")
DUCKDB_THREADS = int(os.environ.get("ECOM_THREADS", "4"))

# CLV: fit on purchases before CALIBRATION_END, test on [CALIBRATION_END, HOLDOUT_END)
CLV_CALIBRATION_END = "2019-11-10"
CLV_HOLDOUT_END = "2019-12-01"
CLV_HORIZON_DAYS = 90        # how far ahead to project CLV
CLV_MARGIN = 1.0             # set e.g. 0.3 to turn revenue CLV into profit CLV

# Experiment design defaults
EXPERIMENT_ALPHA = 0.05
EXPERIMENT_POWER = 0.80
EXPERIMENT_RELATIVE_MDES = [0.025, 0.05, 0.10, 0.15, 0.20]
RECOVERY_WINDOW_DAYS = 7     # must match the interval in sql/marts/07_mart_cart_abandonment.sql
