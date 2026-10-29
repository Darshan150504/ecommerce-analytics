-- Weekly session conversion by segment: the input for root-cause analysis (src/rca.py).
CREATE OR REPLACE TABLE mart_weekly_segment_conversion AS
WITH base AS (
    SELECT session_week AS week, entry_category, entry_price_band, user_type, has_purchase, revenue
    FROM fct_sessions
),
unioned AS (
    SELECT week, 'category'   AS dimension, entry_category   AS segment, has_purchase, revenue FROM base
    UNION ALL
    SELECT week, 'price_band' AS dimension, entry_price_band AS segment, has_purchase, revenue FROM base
    UNION ALL
    SELECT week, 'user_type'  AS dimension, user_type        AS segment, has_purchase, revenue FROM base
)
SELECT
    week,
    dimension,
    segment,
    COUNT(*)                                   AS sessions,
    COUNT(*) FILTER (WHERE has_purchase)       AS purchase_sessions,
    SUM(revenue)                               AS revenue
FROM unioned
GROUP BY week, dimension, segment
ORDER BY week, dimension, segment;
