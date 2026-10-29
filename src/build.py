"""Step 2: build the staging and mart tables by running the SQL files in order.

Most SQL files are plain CREATE statements. Two heavy files are instead a SELECT
with placeholders, run in pieces and appended to the table named in their header:
    -- materialize: <table>
    -- chunk_days: <N>     -> run once per N-day window      ({start}, {end})
    -- chunk_users: <N>    -> run once per group of users     ({part}, {parts}) That keeps heavy steps (like removing duplicates
from 100M+ rows) small enough for a laptop's memory and free disk space.
"""
import re
import shutil
import time
from datetime import datetime, timedelta

from src import config
from src.db import connect

LAYERS = ["staging", "marts"]


def _header(sql: str, key: str):
    m = re.search(rf"--\s*{key}:\s*(\S+)", sql)
    return m.group(1) if m else None


def _run_chunked(con, sql: str, table: str, chunk_days: int) -> None:
    lo, hi = con.execute("SELECT MIN(event_time), MAX(event_time) FROM raw_events").fetchone()
    day = datetime.strptime(lo[:10], "%Y-%m-%d")
    last = datetime.strptime(hi[:10], "%Y-%m-%d")
    first = True
    while day <= last:
        end = day + timedelta(days=chunk_days)
        query = sql.replace("{start}", day.strftime("%Y-%m-%d")).replace("{end}", end.strftime("%Y-%m-%d"))
        if first:
            con.execute(f"CREATE OR REPLACE TABLE {table} AS {query}")
            first = False
        else:
            con.execute(f"INSERT INTO {table} {query}")
        con.execute("CHECKPOINT")      # write to the database file and release temporary space
        print(f"          {day.date()} -> {end.date()} done", flush=True)
        day = end


def _run_user_parts(con, sql: str, table: str, parts: int) -> None:
    for part in range(parts):
        query = sql.replace("{parts}", str(parts)).replace("{part}", str(part))
        if part == 0:
            con.execute(f"CREATE OR REPLACE TABLE {table} AS {query}")
        else:
            con.execute(f"INSERT INTO {table} {query}")
        con.execute("CHECKPOINT")
        print(f"          user group {part + 1}/{parts} done", flush=True)


def run() -> None:
    # Leftover temporary files from a crashed run can be large: clear them first
    shutil.rmtree(config.TMP_DIR, ignore_errors=True)
    con = connect()
    for layer in LAYERS:
        for sql_file in sorted((config.SQL_DIR / layer).glob("*.sql")):
            t0 = time.time()
            sql = sql_file.read_text()
            table = _header(sql, "materialize")
            chunk_days, chunk_users = _header(sql, "chunk_days"), _header(sql, "chunk_users")
            if table and chunk_days:
                print(f"[build] {layer}/{sql_file.name} (in {chunk_days}-day chunks)", flush=True)
                _run_chunked(con, sql, table, int(chunk_days))
            elif table and chunk_users:
                print(f"[build] {layer}/{sql_file.name} (in {chunk_users} user groups)", flush=True)
                _run_user_parts(con, sql, table, int(chunk_users))
            else:
                con.execute(sql)
            con.execute("CHECKPOINT")
            print(f"[build] {layer}/{sql_file.name:<45} {time.time() - t0:6.1f}s", flush=True)

    print("\nCleaning log:")
    print(con.execute("SELECT * FROM stg_cleaning_log").fetchdf().T.to_string(header=False))
    con.close()
    shutil.rmtree(config.TMP_DIR, ignore_errors=True)


if __name__ == "__main__":
    run()
