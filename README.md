# E-commerce Growth Analytics

> **[One-sentence headline finding with a number, e.g. "Cart-to-purchase conversion for electronics fell X% in week Y, costing ~$Z; a reminder-email test needs N users per arm to detect a 10% lift."]**

End-to-end product analytics on **[N]M clickstream events** (views, add-to-carts and purchases) from a
multi-category online store, October-November 2019. Built with DuckDB SQL and Python on a laptop.

**[Live dashboard](https://your-app.streamlit.app)** · **[One-page memo](reports/memo.md)**

![dashboard screenshot](reports/dashboard.png)

---

## Questions this project answers
1. **What is the North Star metric, and what drives it?** A metric tree breaks Weekly Purchasing Users into traffic, cart rate and cart-to-purchase rate.
2. **Conversion dropped in week [W]. Why?** A mix/rate decomposition separates "different users showed up" from "something broke in a segment."
3. **Which customers are worth the most?** BG/NBD + Gamma-Gamma models predict each customer's future purchases and value, validated on a holdout period.
4. **Would cart-reminder emails work, and how would we test it?** A powered A/B test design built from the measured baseline.

## Key results
_Fill in from `outputs/` after running on the real data._

| Area | Result |
|---|---|
| Data | [N] raw events -> [N] after cleaning ([X]% duplicates removed) |
| Funnel | [X]% of sessions add to cart; [Y]% of carting sessions purchase |
| Root cause | Week of [date]: conversion [-X]%; [segment] explains [Y] of [Z] pp |
| CLV | Holdout error [X]% (BG/NBD) vs [Y]% (naive); top 10% of customers hold [Z]% of 90-day CLV |
| Experiment | Baseline 7-day recovery [X]%; [N] users per arm to detect a [M]% lift in [W] weeks |

## Recommendations
1. **[Recommendation 1]** - [expected impact]
2. **[Recommendation 2]** - [expected impact]
3. **[Recommendation 3]** - [expected impact]

---

## How it works

```
Kaggle CSVs (~14 GB)
   │  src/load_data.py      -> compressed Parquet (~5-8x smaller)
   ▼
raw_events (view over Parquet)
   │  sql/staging/          -> dedupe, parse timestamps, drop invalid rows, derive segments
   ▼
stg_events  ──► sql/tests/  (10 data quality tests: uniqueness, valid prices, revenue reconciliation, ...)
   │  sql/marts/
   ▼
fct_sessions ─► daily KPIs · weekly metric tree · funnel by segment · cohort retention
             └► cart abandonment · user purchase log
   │  Python
   ▼
src/rca.py (root cause)  ·  src/clv.py (BG/NBD + Gamma-Gamma)  ·  src/experiment.py (power analysis)
   ▼
dashboard/app.py (Streamlit)
```

**Design choices**
- **DuckDB + Parquet**: processes 100M+ rows on an 8 GB laptop with no server and no cost.
- **Staging -> marts layers** (dbt-style): cleaning happens once; every analysis reads from tested tables.
- **SQL tests**: each test is a query returning rule-breaking rows; the pipeline stops if any `error` test fails.
- **CLV models written from the original papers** with scipy, and checked by simulation in `tests/` (they recover the known parameters).

## Run it yourself
```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Optional: 1-minute test run on synthetic data
ECOM_ENV=sample python -m src.make_sample_data
ECOM_ENV=sample python -m src.pipeline

# Real data: put 2019-Oct.csv and 2019-Nov.csv from Kaggle into data/raw/, then
python -m src.pipeline
streamlit run dashboard/app.py
```

## Repository layout
```
src/          pipeline steps and analyses (load, build, data_tests, rca, clv, experiment, export)
sql/staging/  cleaning layer
sql/marts/    analysis-ready tables
sql/tests/    data quality tests
tests/        model validation by simulation
dashboard/    Streamlit app + small exported data
outputs/      analysis results (markdown/CSV/JSON)
reports/      memo
```

## Limitations
- Two months of data: retention and CLV horizons are short, and early weeks overstate "new" users (left-censoring).
- Some purchases have no add-to-cart event, so cart-to-purchase is "purchasers per cart user," not a strict funnel step.
- Revenue = item price (no discounts, returns or margin data).
- The experiment is a **design**, not a result. It would need to be run to measure a real effect.

**Data:** [eCommerce behavior data from multi category store](https://www.kaggle.com/datasets/mkechinov/ecommerce-behavior-data-from-multi-category-store) (REES46 Open CDP), Kaggle.
