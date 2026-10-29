-- description: every staged event has a positive price
-- severity: error
SELECT *
FROM stg_events
WHERE price IS NULL OR price <= 0
LIMIT 20
