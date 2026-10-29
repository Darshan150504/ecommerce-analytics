-- description: conversion-type rates stay within [0, 1]
-- severity: error
SELECT dimension, segment, cart_rate, cart_to_purchase_rate, session_conversion
FROM mart_funnel_by_segment
WHERE cart_rate NOT BETWEEN 0 AND 1
   OR cart_to_purchase_rate NOT BETWEEN 0 AND 1
   OR session_conversion NOT BETWEEN 0 AND 1
