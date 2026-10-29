-- description: timestamps fall inside a plausible range
-- severity: error
SELECT *
FROM stg_events
WHERE event_ts < TIMESTAMP '2019-01-01' OR event_ts > current_timestamp::TIMESTAMP
LIMIT 20
