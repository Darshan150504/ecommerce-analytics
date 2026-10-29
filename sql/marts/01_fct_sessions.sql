-- materialize: fct_sessions
-- chunk_users: 4
--
-- FACT TABLE: one row per session. Almost every analysis builds on this table.
-- "Entry" category / price band = what the user looked at first in the session,
-- which is how we segment sessions for funnels and root-cause analysis.
-- build.py runs this once per group of users (user_id % 4 = {part}) and appends the
-- results, so all of a user's sessions are processed together but memory stays small.
WITH session_agg AS (
    SELECT
        session_id,
        MIN(user_id)                                                     AS user_id,
        COUNT(DISTINCT user_id)                                          AS n_user_ids,  -- should be 1 (tested)
        MIN(event_ts)                                                    AS session_start,
        MAX(event_ts)                                                    AS session_end,
        arg_min(category_l1, event_ts)                                   AS entry_category,
        arg_min(price_band, event_ts)                                    AS entry_price_band,
        COUNT(*) FILTER (WHERE event_type = 'view')                      AS n_views,
        COUNT(*) FILTER (WHERE event_type = 'cart')                      AS n_carts,
        COUNT(*) FILTER (WHERE event_type = 'purchase')                  AS n_purchased_items,
        COALESCE(SUM(price) FILTER (WHERE event_type = 'purchase'), 0)   AS revenue,
        MIN(event_ts) FILTER (WHERE event_type = 'cart')                 AS first_cart_ts,
        MIN(event_ts) FILTER (WHERE event_type = 'purchase')             AS first_purchase_ts
    FROM stg_events
    WHERE user_id % {parts} = {part}
    GROUP BY session_id
),
user_first_seen AS (
    SELECT user_id, CAST(date_trunc('week', MIN(session_start)) AS DATE) AS first_seen_week
    FROM session_agg
    GROUP BY user_id
)
SELECT
    s.*,
    CAST(s.session_start AS DATE)                                  AS session_date,
    CAST(date_trunc('week', s.session_start) AS DATE)              AS session_week,
    s.n_views > 0                                                  AS has_view,
    s.n_carts > 0                                                  AS has_cart,
    s.n_purchased_items > 0                                        AS has_purchase,
    u.first_seen_week,
    -- 'new' = first week we ever saw this user. Note: the data starts on Oct 1,
    -- so early weeks overstate 'new' users (left-censoring) - mention this caveat.
    CASE WHEN CAST(date_trunc('week', s.session_start) AS DATE) = u.first_seen_week
         THEN 'new' ELSE 'returning' END                           AS user_type,
    date_diff('second', s.session_start, s.first_purchase_ts)      AS seconds_to_purchase
FROM session_agg s
JOIN user_first_seen u USING (user_id)
