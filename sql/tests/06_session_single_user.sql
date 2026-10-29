-- description: each session belongs to exactly one user
-- severity: warn
SELECT session_id, n_user_ids
FROM fct_sessions
WHERE n_user_ids > 1
LIMIT 20
