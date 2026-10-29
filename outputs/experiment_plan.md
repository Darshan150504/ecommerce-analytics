# Experiment plan: cart-abandonment reminder email

## Hypothesis
Sending a reminder email 1 hour after a user abandons a cart increases the share of
abandoning users who purchase within 7 days.

## Design
| Item | Choice |
|---|---|
| Unit of randomization | User (enrolled at first cart abandonment during the test) |
| Split | 50% control (no email) / 50% treatment (email) |
| Primary metric | 7-day purchase rate after abandonment |
| Baseline (control) rate | 23.32% (measured from historical data) |
| Eligible users per week | ~111,194 |
| Significance level / power | 5% two-sided / 80% |
| Minimum detectable effect | 2.5% relative (23.32% -> 23.91%) |
| Sample size | 83,289 users per arm (166,578 total) |
| Duration | 11 days, run for 2 full week(s) to cover weekday effects |

## Guardrail metrics
- Unsubscribe and spam-complaint rate (must not rise meaningfully)
- Average order value of recovered purchases (no shift to discount-driven, low-value orders)
- Revenue per enrolled user (the business outcome, reported alongside the primary metric)

## Validity checks
- Sample ratio mismatch: chi-square test on the 50/50 split; alert if p < 0.001
- Simulated power at the chosen sample size: 79.4% (target 80%)
- A/A simulation false-positive rate: 4.5% (target 5%)
- No peeking: analyse once at the planned sample size (or use a sequential method)

## Decision rule
Ship if the primary metric improves with p < 0.05 and no guardrail is significantly worse.
If the effect is positive but smaller than the MDE, consider a longer test only if the
expected revenue gain justifies it.

## Power table
| relative_mde | treatment_rate | n_per_arm | total_users | days_needed | weeks_needed_rounded |
|---|---|---|---|---|---|
| 0.0250 | 0.2391 | 83,289 | 166,578 | 11 | 2 |
| 0.0500 | 0.2449 | 20,998 | 41,996 | 3 | 1 |
| 0.1000 | 0.2565 | 5,336 | 10,672 | 1 | 1 |
| 0.1500 | 0.2682 | 2,409 | 4,818 | 1 | 1 |
| 0.2000 | 0.2799 | 1,375 | 2,750 | 1 | 1 |
