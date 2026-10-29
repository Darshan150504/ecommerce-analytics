-- Daily business KPIs for the dashboard's overview page.
CREATE OR REPLACE TABLE mart_daily_kpis AS
SELECT
    session_date                                                 AS date,
    COUNT(DISTINCT user_id)                                      AS active_users,
    COUNT(*)                                                     AS sessions,
    COUNT(*) FILTER (WHERE has_cart)                             AS cart_sessions,
    COUNT(*) FILTER (WHERE has_purchase)                         AS purchase_sessions,   -- = orders
    COUNT(DISTINCT user_id) FILTER (WHERE has_purchase)          AS purchasers,
    SUM(revenue)                                                 AS revenue,
    COUNT(*) FILTER (WHERE has_purchase) * 1.0 / COUNT(*)        AS session_conversion,
    SUM(revenue) / NULLIF(COUNT(*) FILTER (WHERE has_purchase), 0) AS aov
FROM fct_sessions
GROUP BY session_date
ORDER BY session_date;
