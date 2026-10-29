-- CART ABANDONMENT: sessions with a cart but no purchase, and whether the user
-- came back and bought within 7 days ("natural recovery").
-- This natural recovery rate is the CONTROL baseline for the reminder-email experiment.
-- Sessions in the last 7 days of data are excluded because we can't observe their
-- full 7-day window (right-censoring).
CREATE OR REPLACE TABLE mart_cart_abandonment AS
WITH s AS (
    SELECT
        user_id,
        session_id,
        session_start,
        session_end,
        session_week,
        entry_category,
        has_cart,
        has_purchase,
        MIN(CASE WHEN has_purchase THEN session_start END) OVER (
            PARTITION BY user_id
            ORDER BY session_start
            ROWS BETWEEN 1 FOLLOWING AND UNBOUNDED FOLLOWING
        ) AS next_purchase_ts
    FROM fct_sessions
),
bounds AS (SELECT MAX(session_end) AS max_ts FROM fct_sessions)
SELECT
    s.user_id,
    s.session_id,
    s.session_start,
    s.session_end,
    s.session_week,
    s.entry_category,
    s.next_purchase_ts,
    (s.next_purchase_ts IS NOT NULL
        AND s.next_purchase_ts <= s.session_end + INTERVAL 7 DAY)      AS recovered_7d
FROM s, bounds b
WHERE s.has_cart
  AND NOT s.has_purchase
  AND s.session_end <= b.max_ts - INTERVAL 7 DAY;
