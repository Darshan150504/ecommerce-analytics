-- description: key columns are never null
-- severity: error
SELECT *
FROM stg_events
WHERE event_ts IS NULL OR user_id IS NULL OR session_id IS NULL OR product_id IS NULL
LIMIT 20
