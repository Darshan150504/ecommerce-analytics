-- description: stg_events has no duplicated events
-- severity: error
SELECT event_ts, event_type, product_id, user_id, session_id, price, COUNT(*) AS n
FROM stg_events
GROUP BY ALL
HAVING COUNT(*) > 1
