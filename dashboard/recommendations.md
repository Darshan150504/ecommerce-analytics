## Recommendations

**1. Set up real-time alerts for purchase activity, and investigate the Nov 15 incident.**
On Nov 15, the first day of the store's biggest sale, traffic hit 762K sessions but only
1 purchase was recorded (a normal day has about 20K). If checkout was down, that is roughly
\$7M of a normal day's revenue at risk, and likely more on a sale day (Nov 16 brought in \$23M).
**Action:** alert the on-call team when hourly purchases fall far below the expected level,
and add a daily data-quality check for missing purchase events.
**Expected impact:** catch a similar incident within an hour instead of a day.

**2. Protect the top 10% of customers.**
The CLV model (3% holdout error vs 52% for a naive baseline) shows that the top 10% of
customers hold about 50% of predicted 90-day value.
**Action:** a VIP retention program (early sale access, loyalty perks) for top-decile
customers, prioritising those whose probability of still being active is dropping.
**Expected impact:** every 10% of top-decile value retained protects about 5% of total predicted CLV.

**3. Test cart-abandonment reminder emails before rolling them out.**
23.3% of the ≈111K weekly cart abandoners return to buy within 7 days without any nudge.
**Action:** run the A/B test in the Experiment tab: 83K users per group for 2 weeks,
designed to detect a 2.5% relative lift.
**Expected impact:** even a 2.5% lift would mean ≈650 extra purchasing users per week
(≈\$220K/week at a ≈\$340 average order); a 10% lift would mean ≈2,600 (≈\$880K/week).