# Memo: Growth opportunities from Oct-Nov 2019 clickstream

**To:** Head of E-commerce · **From:** Darshan Patel · **Data:** 110M events, 5.3M users, Oct 1 - Nov 30, 2019

## Bottom line
On the first day of our biggest sale (Nov 15), traffic reached 762K sessions but only **one purchase** was recorded,
and nobody was alerted. We should monitor purchases in real time, protect the 10% of customers who hold half of
our predicted future value, and test cart-reminder emails before rolling them out.

## What we measured
- A normal day: ~400K sessions, ~20K orders, ~$7M revenue, ~5% session conversion.
- Sale weekend (Nov 15-17): traffic up to ~2.5x normal; Nov 17 alone brought in $57.8M at 15.6% conversion.
- Before the sale, conversion slid from 5.9% to 4.2% (Nov 4-13) while traffic grew: shoppers browsed and waited.

## What we found
1. **A near-total loss of recorded purchases on Nov 15.** 762K sessions, 1 purchase. The automated week-over-week
   analysis first flagged the *following* week as an 18.6% drop. A daily drill-down showed that week was normal and
   the sale week was the anomaly. Whether checkout or purchase tracking failed, it went undetected for a full day.
2. **Value is concentrated.** A BG/NBD + Gamma-Gamma model (holdout error -3.0% vs +51.9% for a naive baseline,
   432K customers) shows the top 10% of customers hold 49.5% of predicted 90-day value.
3. **Many abandoned carts recover on their own.** 23.3% of the ~111K weekly cart abandoners buy within 7 days with
   no reminder. Any email program must beat that baseline, not zero.

## Recommendations
| # | Action | Expected impact | Confidence |
|---|---|---|---|
| 1 | Hourly alert when purchases fall far below the expected level; post-mortem on Nov 15 | Detect a similar failure within an hour instead of a day (a normal day is ~$7M) | High that monitoring is needed; cause of Nov 15 unknown |
| 2 | VIP retention program for top-decile customers with falling probability of being active | ~5% of total predicted CLV protected per 10% of top-decile value retained | Medium: model validated on holdout; program effect untested |
| 3 | A/B test reminder emails: 83K users per arm, 2 weeks, MDE 2.5% relative | ~650 extra purchasing users/week (~$220K/week) at the minimum detectable lift | Design ready; effect unknown until tested |

## Caveats
Two months of data; no cost, margin or returns data; impact figures assume average-sized orders.
Findings 1-2 are observational and should be confirmed (engineering logs for Nov 15; a test for the VIP program).
