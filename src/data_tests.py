"""Step 3: data quality tests.

Each file in sql/tests/ is a query that returns the rows that BREAK a rule.
Zero rows = pass. A failing 'error' test stops the pipeline; a 'warn' test
only prints a warning. (This is the same idea dbt uses for its tests.)
"""
import re
import sys

from src import config
from src.db import connect


def _meta(sql: str, key: str, default: str) -> str:
    m = re.search(rf"--\s*{key}:\s*(.+)", sql)
    return m.group(1).strip() if m else default


def run() -> bool:
    con = connect(read_only=True)
    n_err = n_warn = 0
    for sql_file in sorted((config.SQL_DIR / "tests").glob("*.sql")):
        sql = sql_file.read_text()
        severity = _meta(sql, "severity", "error")
        desc = _meta(sql, "description", sql_file.stem)
        failing = con.execute(f"SELECT COUNT(*) FROM ({sql})").fetchone()[0]
        if failing == 0:
            status = "PASS"
        elif severity == "warn":
            status, n_warn = "WARN", n_warn + 1
        else:
            status, n_err = "FAIL", n_err + 1
        print(f"[test] {status:<4} {desc}" + (f"  ({failing} failing rows)" if failing else ""))
    con.close()
    print(f"\n[test] {n_err} failed, {n_warn} warnings")
    return n_err == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
