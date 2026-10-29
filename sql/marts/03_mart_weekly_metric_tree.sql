-- NORTH STAR METRIC TREE (weekly, user level)
--
-- North Star: Weekly Purchasing Users (WPU) = users with >= 1 purchase in the week.
--
--   WPU = active_users x cart_rate x cart_to_purchase_rate
--         where cart_rate             = cart_users / active_users
--               cart_to_purchase_rate = purchasers / cart_users
--   active_users = new_users + returning_users
--
--   Revenue = WPU x orders_per_purchaser x AOV       (orders = purchasing sessions)
--
-- Both are exact identities, so a change in the North Star can be attributed to
-- the branch that moved. Note: in this dataset some purchases have no cart event,
-- so cart_to_purchase_rate is "purchasers per cart user", not a strict funnel step;
-- purchasers_without_cart shows how big that effect is.
CREATE OR REPLACE TABLE mart_weekly_metric_tree AS
WITH user_week AS (
    SELECT
        session_week                                   AS week,
        user_id,
        ANY_VALUE(user_type)                           AS user_type,
        BOOL_OR(has_cart)                              AS carted,
        BOOL_OR(has_purchase)                          AS purchased,
        COUNT(*) FILTER (WHERE has_purchase)           AS orders,
        SUM(revenue)                                   AS revenue
    FROM fct_sessions
    GROUP BY session_week, user_id
),
week_days AS (
    SELECT session_week AS week, COUNT(DISTINCT session_date) AS n_days
    FROM fct_sessions
    GROUP BY session_week
)
SELECT
    uw.week,
    wd.n_days,
    wd.n_days = 7                                                         AS is_full_week,
    COUNT(*)                                                              AS active_users,
    COUNT(*) FILTER (WHERE user_type = 'new')                             AS new_users,
    COUNT(*) FILTER (WHERE user_type = 'returning')                       AS returning_users,
    COUNT(*) FILTER (WHERE carted)                                        AS cart_users,
    COUNT(*) FILTER (WHERE purchased)                                     AS purchasers,          -- North Star
    COUNT(*) FILTER (WHERE purchased AND NOT carted)                      AS purchasers_without_cart,
    SUM(orders)                                                           AS orders,
    SUM(revenue)                                                          AS revenue,
    COUNT(*) FILTER (WHERE carted) * 1.0 / COUNT(*)                       AS cart_rate,
    COUNT(*) FILTER (WHERE purchased) * 1.0
        / NULLIF(COUNT(*) FILTER (WHERE carted), 0)                       AS cart_to_purchase_rate,
    COUNT(*) FILTER (WHERE purchased) * 1.0 / COUNT(*)                    AS purchase_rate,
    SUM(orders) * 1.0 / NULLIF(COUNT(*) FILTER (WHERE purchased), 0)      AS orders_per_purchaser,
    SUM(revenue) / NULLIF(SUM(orders), 0)                                 AS aov,
    SUM(revenue) / COUNT(*)                                               AS revenue_per_active_user
FROM user_week uw
JOIN week_days wd USING (week)
GROUP BY uw.week, wd.n_days
ORDER BY uw.week;
