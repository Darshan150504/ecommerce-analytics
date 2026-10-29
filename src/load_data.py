"""Step 1: convert the raw Kaggle CSVs to compressed Parquet and expose them as `raw_events`.

Parquet is ~5-8x smaller than CSV and much faster to query. Once this has run
successfully you can delete the CSVs in data/raw/ to free disk space.
"""
from src import config
from src.db import connect

# Explicit types so DuckDB never guesses wrong on 100M+ rows.
# event_time is kept as text here and parsed in the staging layer.
CSV_COLUMNS = {
    "event_time": "VARCHAR",
    "event_type": "VARCHAR",
    "product_id": "BIGINT",
    "category_id": "BIGINT",
    "category_code": "VARCHAR",
    "brand": "VARCHAR",
    "price": "DOUBLE",
    "user_id": "BIGINT",
    "user_session": "VARCHAR",
}


def run() -> None:
    config.PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    con = connect()

    for month in config.MONTHS:
        csv_path = config.RAW_DIR / f"{month}.csv"
        pq_path = config.PARQUET_DIR / f"{month}.parquet"
        if pq_path.exists():
            print(f"[load] {pq_path.name} already exists - skipping")
            continue
        if not csv_path.exists():
            raise FileNotFoundError(
                f"Missing {csv_path}. Download it from Kaggle "
                "('eCommerce behavior data from multi category store') and put it in "
                f"{config.RAW_DIR}"
            )
        print(f"[load] converting {csv_path.name} -> {pq_path.name} (a few minutes for real data)...")
        con.execute(f"""
            COPY (
                SELECT * FROM read_csv('{csv_path.as_posix()}',
                                       header = true,
                                       columns = {CSV_COLUMNS})
            ) TO '{pq_path.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """)

    con.execute(f"""
        CREATE OR REPLACE VIEW raw_events AS
        SELECT * FROM read_parquet('{(config.PARQUET_DIR / "*.parquet").as_posix()}')
    """)
    print(con.execute("""
        SELECT event_type, COUNT(*) AS events, COUNT(DISTINCT user_id) AS users
        FROM raw_events GROUP BY 1 ORDER BY 2 DESC
    """).fetchdf().to_string(index=False))
    con.close()


if __name__ == "__main__":
    run()
