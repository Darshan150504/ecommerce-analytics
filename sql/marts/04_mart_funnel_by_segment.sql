-- SESSION FUNNEL by segment: view -> cart -> purchase.
-- Long format (dimension, segment) so the dashboard can switch dimension easily.
CREATE OR REPLACE TABLE mart_funnel_by_segment AS
WITH base AS (
    SELECT entry_category, entry_price_band, user_type, has_view, has_cart, has_purchase, revenue
    FROM fct_sessions
),
unioned AS (
    SELECT 'category'   AS dimension, entry_category   AS segment, * EXCLUDE (entry_category, entry_price_band, user_type) FROM base
    UNION ALL
    SELECT 'price_band' AS dimension, entry_price_band AS segment, * EXCLUDE (entry_category, entry_price_band, user_type) FROM base
    UNION ALL
    SELECT 'user_type'  AS dimension, user_type        AS segment, * EXCLUDE (entry_category, entry_price_band, user_type) FROM base
)
SELECT
    dimension,
    segment,
    COUNT(*)                                                       AS sessions,
    COUNT(*) FILTER (WHERE has_view)                               AS view_sessions,
    COUNT(*) FILTER (WHERE has_cart)                               AS cart_sessions,
    COUNT(*) FILTER (WHERE has_purchase)                           AS purchase_sessions,
    COUNT(*) FILTER (WHERE has_cart) * 1.0 / COUNT(*)              AS cart_rate,
    COUNT(*) FILTER (WHERE has_cart AND has_purchase) * 1.0
        / NULLIF(COUNT(*) FILTER (WHERE has_cart), 0)              AS cart_to_purchase_rate,
    COUNT(*) FILTER (WHERE has_purchase) * 1.0 / COUNT(*)          AS session_conversion,
    SUM(revenue)                                                   AS revenue,
    SUM(revenue) / COUNT(*)                                        AS revenue_per_session
FROM unioned
GROUP BY dimension, segment
ORDER BY dimension, sessions DESC;
