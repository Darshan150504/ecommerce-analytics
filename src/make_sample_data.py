"""Generate a SMALL SYNTHETIC dataset in the exact format of the Kaggle CSVs.

Purpose: test the full pipeline in ~1 minute before working with 100M+ real rows.
The numbers it produces are fake - never report them as findings.
It deliberately includes duplicates, missing sessions and zero prices (to exercise
the cleaning rules) and a planted conversion drop (to check that the RCA finds it).

Usage:  ECOM_ENV=sample python -m src.make_sample_data
"""
import uuid

import numpy as np
import pandas as pd

from src import config

RNG = np.random.default_rng(42)
START, END = pd.Timestamp("2019-10-01"), pd.Timestamp("2019-12-01")
N_DAYS = (END - START).days

CATEGORIES = {  # name: (weight, median price, cart prob, purchase|cart prob)
    "electronics": (0.30, 220, 0.10, 0.45),
    "appliances": (0.15, 150, 0.08, 0.40),
    "computers": (0.10, 500, 0.06, 0.35),
    "apparel": (0.12, 40, 0.12, 0.30),
    "furniture": (0.08, 120, 0.05, 0.30),
    "construction": (0.07, 60, 0.07, 0.35),
    "kids": (0.06, 35, 0.09, 0.35),
    None: (0.12, 50, 0.07, 0.35),  # missing category_code, like the real data
}
SUBCATS = {"electronics": ["smartphone", "audio.headphone", "video.tv"], "appliances": ["kitchen.washer", "environment.vacuum"],
           "computers": ["notebook", "desktop"], "apparel": ["shoes", "costume"], "furniture": ["living_room.sofa"],
           "construction": ["tools.drill"], "kids": ["toys"]}
BRANDS = ["samsung", "apple", "xiaomi", "huawei", "lg", "lenovo", "acer", "bosch", None]

PLANTED_DROP_WEEK = pd.Timestamp("2019-11-11")   # electronics checkout breaks this week
CAT_NAMES = list(CATEGORIES)
CAT_W = np.array([v[0] for v in CATEGORIES.values()])


def _session_events(user_id: int, ts: pd.Timestamp, propensity: float) -> list:
    rows = []
    sid = str(uuid.UUID(int=int(RNG.integers(0, 2**63)) << 64 | int(RNG.integers(0, 2**63))))
    cat = CAT_NAMES[RNG.choice(len(CAT_NAMES), p=CAT_W / CAT_W.sum())]
    _, med_price, p_cart, p_buy = CATEGORIES[cat]
    code = f"{cat}.{RNG.choice(SUBCATS[cat])}" if cat else None
    brand = BRANDS[RNG.integers(len(BRANDS))]
    product_id = int(RNG.integers(1_000_000, 1_000_500))
    price = round(float(med_price * RNG.lognormal(0, 0.6)), 2)

    n_views = int(RNG.integers(1, 8))
    t = ts
    for _ in range(n_views):
        rows.append((t, "view", product_id, cat, code, brand, price, user_id, sid))
        t += pd.Timedelta(seconds=int(RNG.integers(5, 240)))

    p_cart_eff = min(0.9, p_cart * propensity)
    p_buy_eff = p_buy
    if cat == "electronics" and PLANTED_DROP_WEEK <= ts < PLANTED_DROP_WEEK + pd.Timedelta(days=7):
        p_buy_eff *= 0.45                      # the planted incident
    if pd.Timestamp("2019-11-29") <= ts < pd.Timestamp("2019-12-02"):
        p_cart_eff = min(0.9, p_cart_eff * 1.5)  # Black Friday bump

    if RNG.random() < p_cart_eff:
        rows.append((t, "cart", product_id, cat, code, brand, price, user_id, sid))
        t += pd.Timedelta(seconds=int(RNG.integers(20, 900)))
        if RNG.random() < p_buy_eff:
            rows.append((t, "purchase", product_id, cat, code, brand, price, user_id, sid))
    elif RNG.random() < 0.004 * propensity:      # purchases without a cart event exist in the real data
        rows.append((t, "purchase", product_id, cat, code, brand, price, user_id, sid))
    return rows


def generate(n_users: int = 30_000) -> pd.DataFrame:
    rows = []
    for user_id in range(500_000_000, 500_000_000 + n_users):
        first_day = int(RNG.integers(0, N_DAYS))
        lifetime = int(min(N_DAYS - first_day, RNG.exponential(25) + 1))   # users churn
        rate = RNG.gamma(0.6, 0.35)                                        # sessions per day
        propensity = RNG.gamma(2.0, 0.5)                                   # some users buy more
        n_sessions = max(1, RNG.poisson(rate * lifetime))
        days = first_day + RNG.integers(0, max(lifetime, 1), size=n_sessions)
        for d in days:
            ts = START + pd.Timedelta(days=int(d), seconds=int(RNG.integers(0, 86_400)))
            rows.extend(_session_events(user_id, ts, propensity))

    df = pd.DataFrame(rows, columns=["ts", "event_type", "product_id", "cat", "category_code",
                                     "brand", "price", "user_id", "user_session"])
    df["category_id"] = df["cat"].map({c: 2053013555631882000 + i for i, c in enumerate(CAT_NAMES)}).fillna(0).astype("int64")
    df = df[df["ts"] < END]

    # Inject data-quality problems the cleaning layer must handle
    dupes = df.sample(frac=0.01, random_state=1)
    df = pd.concat([df, dupes], ignore_index=True)
    df.loc[df.sample(frac=0.002, random_state=2).index, "user_session"] = None
    df.loc[df.sample(frac=0.001, random_state=3).index, "price"] = 0.0

    df["event_time"] = df["ts"].dt.strftime("%Y-%m-%d %H:%M:%S") + " UTC"
    df = df.sort_values("ts")
    return df[["event_time", "event_type", "product_id", "category_id", "category_code",
               "brand", "price", "user_id", "user_session", "ts"]]


def run() -> None:
    if not config.SAMPLE:
        raise SystemExit("Refusing to write synthetic data into the real data folder. "
                         "Run with ECOM_ENV=sample.")
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    df = generate()
    for month in config.MONTHS:                       # e.g. '2019-Oct'
        m = pd.Timestamp(f"{month}-01")
        part = df[(df["ts"] >= m) & (df["ts"] < m + pd.offsets.MonthBegin(1))].drop(columns="ts")
        out = config.RAW_DIR / f"{month}.csv"
        part.to_csv(out, index=False)
        print(f"[sample] wrote {len(part):,} rows -> {out}")


if __name__ == "__main__":
    run()
