-- description: no calendar day is missing from the daily KPIs
-- severity: warn
WITH bounds AS (SELECT MIN(date) AS d0, MAX(date) AS d1 FROM mart_daily_kpis),
     cal AS (SELECT CAST(unnest(generate_series(d0, d1, INTERVAL 1 DAY)) AS DATE) AS date FROM bounds)
SELECT cal.date
FROM cal
LEFT JOIN mart_daily_kpis k USING (date)
WHERE k.date IS NULL
