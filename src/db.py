"""Small helper so every script opens DuckDB with the same settings."""
import duckdb

from src import config


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.TMP_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(config.DB_PATH), read_only=read_only)
    con.execute(f"SET memory_limit = '{config.DUCKDB_MEMORY_LIMIT}'")
    con.execute(f"SET threads = {config.DUCKDB_THREADS}")
    con.execute(f"SET temp_directory = '{config.TMP_DIR.as_posix()}'")
    con.execute("SET preserve_insertion_order = false")  # lower memory use
    return con
