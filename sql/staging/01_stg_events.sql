-- materialize: stg_events
-- chunk_days: 3
--
-- STAGING LAYER: one clean row per real event.
-- build.py runs this query once per 3-day window ({start} to {end}) and appends the
-- results. Removing duplicates chunk by chunk keeps memory and temporary disk use
-- small on a laptop. Duplicates can't cross chunks: a duplicate has the same timestamp.
--
-- Cleaning rules (counted in stg_cleaning_log):
--   1. drop events with no session id (can't be placed in a funnel)
--   2. drop events with price <= 0 (bad records; would distort revenue)
--   3. keep only the three known event types
--   4. drop exact duplicate rows (the raw data contains repeated events)
WITH deduped AS (
    SELECT DISTINCT *
    FROM raw_events
    WHERE event_time >= '{start}' AND event_time < '{end}'   -- text compare works for 'YYYY-MM-DD ...'
      AND user_session IS NOT NULL
      AND price > 0
      AND event_type IN ('view', 'cart', 'purchase')
),
parsed AS (
    SELECT
        strptime(event_time, '%Y-%m-%d %H:%M:%S UTC')       AS event_ts,
        event_type,
        product_id,
        category_id,
        NULLIF(TRIM(category_code), '')                      AS category_code,
        NULLIF(TRIM(brand), '')                              AS brand,
        price,
        user_id,
        hash(user_session)                                   AS session_id
    FROM deduped
)
SELECT
    event_ts,
    CAST(event_ts AS DATE)                                   AS event_date,
    CAST(date_trunc('week', event_ts) AS DATE)               AS event_week,   -- weeks start Monday
    event_type,
    product_id,
    COALESCE(category_code, 'unknown')                       AS category_code,
    COALESCE(split_part(category_code, '.', 1), 'unknown')   AS category_l1,  -- e.g. 'electronics'
    COALESCE(brand, 'unknown')                               AS brand,
    price,
    CASE
        WHEN price < 25   THEN '1: <$25'
        WHEN price < 100  THEN '2: $25-100'
        WHEN price < 300  THEN '3: $100-300'
        WHEN price < 1000 THEN '4: $300-1000'
        ELSE                   '5: $1000+'
    END                                                      AS price_band,
    user_id,
    session_id   -- 64-bit hash of the session text id: same grouping, ~1/4 of the disk space
FROM parsed
