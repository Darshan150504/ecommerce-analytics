-- WEEKLY COHORT RETENTION: of users first seen in week W, what share came back in week W+k?
CREATE OR REPLACE TABLE mart_cohort_retention AS
WITH activity AS (
    SELECT DISTINCT user_id, first_seen_week AS cohort_week, session_week AS active_week, has_purchase
    FROM fct_sessions
),
user_week AS (
    SELECT user_id, cohort_week, active_week, BOOL_OR(has_purchase) AS purchased
    FROM activity
    GROUP BY ALL
),
cohort_size AS (
    SELECT cohort_week, COUNT(DISTINCT user_id) AS cohort_users
    FROM user_week
    GROUP BY cohort_week
)
SELECT
    uw.cohort_week,
    date_diff('week', uw.cohort_week, uw.active_week)                AS weeks_since_first_seen,
    cs.cohort_users,
    COUNT(DISTINCT uw.user_id)                                       AS active_users,
    COUNT(DISTINCT uw.user_id) FILTER (WHERE uw.purchased)           AS purchasing_users,
    COUNT(DISTINCT uw.user_id) * 1.0 / cs.cohort_users               AS retention_rate,
    COUNT(DISTINCT uw.user_id) FILTER (WHERE uw.purchased) * 1.0
        / cs.cohort_users                                            AS purchase_retention_rate
FROM user_week uw
JOIN cohort_size cs USING (cohort_week)
GROUP BY uw.cohort_week, weeks_since_first_seen, cs.cohort_users
ORDER BY uw.cohort_week, weeks_since_first_seen;
