-- One row per user per purchase day: the transaction log used by the CLV models.
-- A "transaction" = a day with >= 1 purchase (standard for BG/NBD with daily data).
CREATE OR REPLACE TABLE mart_user_daily_purchases AS
SELECT
    user_id,
    event_date        AS purchase_date,
    COUNT(*)          AS items,
    SUM(price)        AS revenue
FROM stg_events
WHERE event_type = 'purchase'
GROUP BY user_id, event_date
ORDER BY user_id, purchase_date;
