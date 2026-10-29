-- description: only view / cart / purchase events in staging
-- severity: error
SELECT event_type, COUNT(*) AS n
FROM stg_events
WHERE event_type NOT IN ('view', 'cart', 'purchase') OR event_type IS NULL
GROUP BY event_type
