-- description: metric tree multiplies out exactly (WPU = active x cart_rate x cart_to_purchase)
-- severity: error
SELECT week, purchasers, active_users * cart_rate * cart_to_purchase_rate AS reconstructed
FROM mart_weekly_metric_tree
WHERE cart_users > 0
  AND ABS(purchasers - active_users * cart_rate * cart_to_purchase_rate) > 1e-6
