-- How many raw rows each cleaning rule removed. Put these numbers in your README:
-- documenting data quality decisions is exactly what reviewers look for.
-- (The invalid-row rules can overlap, so those three counts don't have to add up.)
CREATE OR REPLACE TABLE stg_cleaning_log AS
WITH raw_counts AS (
    SELECT
        COUNT(*)                                                         AS raw_rows,
        COUNT(*) FILTER (WHERE user_session IS NULL)                     AS null_session_rows,
        COUNT(*) FILTER (WHERE price IS NULL OR price <= 0)              AS non_positive_price_rows,
        COUNT(*) FILTER (WHERE event_type NOT IN ('view','cart','purchase')
                            OR event_type IS NULL)                       AS unknown_event_type_rows,
        COUNT(*) FILTER (WHERE user_session IS NOT NULL
                           AND price > 0
                           AND event_type IN ('view','cart','purchase')) AS valid_rows
    FROM raw_events
),
stg AS (
    SELECT COUNT(*) AS stg_rows FROM stg_events
)
SELECT
    r.raw_rows,
    r.null_session_rows,
    r.non_positive_price_rows,
    r.unknown_event_type_rows,
    r.valid_rows - s.stg_rows                         AS exact_duplicate_rows,   -- among valid rows
    s.stg_rows,
    ROUND(100.0 * s.stg_rows / r.raw_rows, 2)         AS pct_rows_kept
FROM raw_counts r, stg s;
