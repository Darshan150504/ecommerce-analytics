-- description: session revenue adds up to staged purchase revenue
-- severity: error
WITH a AS (SELECT SUM(price) AS stg_revenue FROM stg_events WHERE event_type = 'purchase'),
     b AS (SELECT SUM(revenue) AS session_revenue FROM fct_sessions),
     c AS (SELECT SUM(revenue) AS daily_revenue FROM mart_daily_kpis)
SELECT *
FROM a, b, c
WHERE ABS(stg_revenue - session_revenue) > 0.01 OR ABS(stg_revenue - daily_revenue) > 0.01
