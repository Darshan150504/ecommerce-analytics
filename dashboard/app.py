"""E-commerce Growth Analytics dashboard.

Run locally:   streamlit run dashboard/app.py
Sample data:   ECOM_ENV=sample streamlit run dashboard/app.py
Reads only the small files in dashboard/data/ (created by `python -m src.pipeline`),
so it can be deployed for free on Streamlit Community Cloud.
"""
import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

HERE = Path(__file__).parent
SAMPLE = os.environ.get("ECOM_ENV", "full").lower() == "sample"
DATA = HERE / ("data_sample" if SAMPLE else "data")
if not DATA.exists() and (HERE / "data_sample").exists():
    DATA, SAMPLE = HERE / "data_sample", True

st.set_page_config(page_title="E-commerce Growth Analytics", layout="wide")


@st.cache_data
def table(name: str) -> pd.DataFrame:
    return pd.read_parquet(DATA / f"{name}.parquet")


@st.cache_data
def csv(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / name)


def text(name: str) -> str:
    p = DATA / name
    return p.read_text() if p.exists() else f"_{name} not found - run the analysis step._"


def jsn(name: str) -> dict:
    p = DATA / name
    return json.loads(p.read_text()) if p.exists() else {}


def pct(x: float, d: int = 2) -> str:
    return f"{x:.{d}%}"


if not DATA.exists():
    st.error("No dashboard data found. Run `python -m src.pipeline` first.")
    st.stop()

st.title("E-commerce Growth Analytics")
st.caption("Clickstream from a multi-category online store (Oct-Nov 2019, Kaggle / REES46). "
           "Pipeline: DuckDB SQL (staging -> marts, tested) + Python models.")
if SAMPLE:
    st.warning("Showing SYNTHETIC sample data - numbers are fake and for testing only.")

tabs = st.tabs(["Overview", "Metric tree", "Funnel", "Retention", "Root cause",
                "Customer lifetime value", "Experiment design", "Recommendations"])

# ------------------------------------------------------------------ Overview
with tabs[0]:
    daily = table("mart_daily_kpis")
    c = st.columns(4)
    c[0].metric("Revenue", f"${daily['revenue'].sum():,.0f}")
    c[1].metric("Orders (purchase sessions)", f"{daily['purchase_sessions'].sum():,.0f}")
    c[2].metric("Session conversion", pct(daily["purchase_sessions"].sum() / daily["sessions"].sum()))
    c[3].metric("Average order value", f"${daily['revenue'].sum() / daily['purchase_sessions'].sum():,.2f}")

    metric = st.selectbox("Daily metric", ["revenue", "active_users", "sessions", "purchasers",
                                           "session_conversion", "aov"])
    st.plotly_chart(px.line(daily, x="date", y=metric, markers=True), width="stretch")

    with st.expander("Data cleaning log"):
        st.dataframe(table("stg_cleaning_log").T.rename(columns={0: "value"}))

# ------------------------------------------------------------------ Metric tree
with tabs[1]:
    tree = table("mart_weekly_metric_tree").sort_values("week")
    tree["week"] = pd.to_datetime(tree["week"]).dt.date
    full = tree[tree["is_full_week"]].reset_index(drop=True)
    st.markdown("**North Star: Weekly Purchasing Users (WPU)** = active users x cart rate x "
                "cart-to-purchase rate. Revenue = WPU x orders per purchaser x AOV.")
    if len(full) < 2:
        st.info("Need at least two full weeks.")
    else:
        wk = st.selectbox("Week", full["week"].tolist()[1:][::-1])
        i = full.index[full["week"] == wk][0]
        cur, prev = full.loc[i], full.loc[i - 1]

        def node(label, col, fmt):
            v, p = cur[col], prev[col]
            ch = (v / p - 1) if p else 0
            color = "#2e7d32" if ch >= 0 else "#c62828"
            return f'<{label}<BR/><B>{fmt(v)}</B><BR/><FONT COLOR="{color}">{ch:+.1%} WoW</FONT>>'

        n = lambda v: f"{v:,.0f}"
        r = lambda v: f"{v:.2%}"
        money = lambda v: f"${v:,.2f}"
        dot = f"""digraph {{
            rankdir=TB; node [shape=box, style="rounded,filled", fillcolor="#f5f7fb", fontname="Helvetica"];
            rev [label={node("Revenue", "revenue", lambda v: f"${v:,.0f}")}];
            wpu [label={node("Weekly purchasing users (North Star)", "purchasers", n)}, fillcolor="#e3ecff"];
            opp [label={node("Orders per purchaser", "orders_per_purchaser", lambda v: f"{v:.2f}")}];
            aov [label={node("Average order value", "aov", money)}];
            au  [label={node("Active users", "active_users", n)}];
            cr  [label={node("Cart rate", "cart_rate", r)}];
            c2p [label={node("Cart to purchase rate", "cart_to_purchase_rate", r)}];
            nu  [label={node("New users", "new_users", n)}];
            ru  [label={node("Returning users", "returning_users", n)}];
            rev -> wpu; rev -> opp; rev -> aov; wpu -> au; wpu -> cr; wpu -> c2p; au -> nu; au -> ru;
        }}"""
        st.graphviz_chart(dot, width="stretch")

    comp = st.selectbox("Trend of a tree component",
                        ["purchasers", "active_users", "cart_rate", "cart_to_purchase_rate",
                         "orders_per_purchaser", "aov", "revenue"])
    st.plotly_chart(px.bar(tree, x="week", y=comp, color="is_full_week",
                           color_discrete_map={True: "#3b6fd8", False: "#bbbbbb"}),
                    width="stretch")
    st.caption("Grey bars are partial weeks (data starts/ends mid-week) - don't compare them directly.")

# ------------------------------------------------------------------ Funnel
with tabs[2]:
    f = table("mart_funnel_by_segment")
    totals = f[f["dimension"] == "user_type"][["sessions", "cart_sessions", "purchase_sessions"]].sum()
    st.plotly_chart(go.Figure(go.Funnel(y=["Sessions", "Sessions with cart", "Sessions with purchase"],
                                        x=totals.tolist(), textinfo="value+percent initial")),
                    width="stretch")
    dim = st.radio("Segment by", ["category", "price_band", "user_type"], horizontal=True)
    d = f[f["dimension"] == dim].sort_values("sessions", ascending=False)
    rate = st.radio("Rate", ["session_conversion", "cart_rate", "cart_to_purchase_rate", "revenue_per_session"],
                    horizontal=True)
    st.plotly_chart(px.bar(d, x="segment", y=rate, hover_data=["sessions", "purchase_sessions"]),
                    width="stretch")
    st.dataframe(d.drop(columns="dimension"), width="stretch", hide_index=True)

# ------------------------------------------------------------------ Retention
with tabs[3]:
    coh = table("mart_cohort_retention")
    coh["cohort_week"] = pd.to_datetime(coh["cohort_week"]).dt.date.astype(str)
    which = st.radio("Retention type", ["retention_rate", "purchase_retention_rate"], horizontal=True)
    heat = coh.pivot(index="cohort_week", columns="weeks_since_first_seen", values=which)
    st.plotly_chart(px.imshow(heat, text_auto=".1%", aspect="auto", color_continuous_scale="Blues",
                              labels=dict(x="Weeks since first seen", y="Cohort (first week seen)")),
                    width="stretch")
    st.caption("Week 0 is the first week. Early cohorts include users who were active before the data starts.")

# ------------------------------------------------------------------ Root cause
with tabs[4]:
    if (DATA / "rca_decomposition.csv").exists():
        wc = csv("rca_weekly_conversion.csv")
        st.plotly_chart(px.line(wc, x="week", y="conversion", markers=True,
                                title="Weekly session conversion (full weeks)"), width="stretch")
        dec = csv("rca_decomposition.csv")
        dim = st.radio("Decompose by", sorted(dec["dimension"].unique()), horizontal=True, key="rca_dim")
        dd = dec[dec["dimension"] == dim].copy()
        long = dd.melt(id_vars="segment", value_vars=["mix_effect", "rate_effect"],
                       var_name="effect", value_name="pp")
        long["pp"] *= 100
        st.plotly_chart(px.bar(long, x="segment", y="pp", color="effect", barmode="relative",
                               title="Contribution to the conversion change (percentage points)"),
                        width="stretch")
    st.markdown(text("rca_summary.md"))

# ------------------------------------------------------------------ CLV
with tabs[5]:
    m = jsn("clv_metrics.json")
    if m:
        c = st.columns(4)
        c[0].metric("Holdout purchases: actual", f"{m['actual_holdout_purchases']:,.0f}")
        c[1].metric("BG/NBD prediction", f"{m['predicted_holdout_purchases']:,.0f}",
                    f"{m['aggregate_error_pct_model']:+.1%} error", delta_color="off")
        c[2].metric("Naive prediction", f"{m['naive_holdout_purchases']:,.0f}",
                    f"{m['aggregate_error_pct_naive']:+.1%} error", delta_color="off")
        c[3].metric(f"Top 10% share of {m['clv_horizon_days']}-day CLV", pct(m["top_decile_share_of_clv"], 1))
        hb = csv("clv_holdout_by_frequency.csv")
        st.plotly_chart(px.bar(hb.melt(id_vars=["freq_bucket", "customers"], var_name="series",
                                       value_name="avg holdout purchases"),
                               x="freq_bucket", y="avg holdout purchases", color="series", barmode="group",
                               labels={"freq_bucket": "Repeat purchases in calibration period"},
                               title="Holdout check: actual vs predicted purchases per customer"),
                        width="stretch")
        dc = csv("clv_deciles.csv")
        st.plotly_chart(px.bar(dc, x="clv_decile", y="share_of_total_clv",
                               title="Share of predicted CLV by customer decile (10 = most valuable)"),
                        width="stretch")
        st.caption(f"Per-customer MAE: model {m['mae_per_customer_model']:.3f} vs naive "
                   f"{m['mae_per_customer_naive']:.3f}. Frequency-spend correlation "
                   f"{m['freq_spend_correlation']:.3f} (Gamma-Gamma assumes ~0).")
    else:
        st.info("Run the analysis step to see CLV results.")

# ------------------------------------------------------------------ Experiment
with tabs[6]:
    e = jsn("experiment_design.json")
    if e:
        ch = e["chosen_design"]
        c = st.columns(4)
        c[0].metric("Baseline 7-day recovery", pct(e["baseline_recovery_rate"]))
        c[1].metric("Abandoning users / week", f"{e['avg_weekly_abandoning_users']:,.0f}")
        c[2].metric("Users per arm", f"{int(ch['n_per_arm']):,}")
        c[3].metric("Duration", f"{int(ch['weeks_needed_rounded'])} week(s)")
        pt = csv("experiment_power_table.csv")
        st.plotly_chart(px.line(pt, x="relative_mde", y="days_needed", markers=True, log_y=True,
                                title="Smaller effects need much longer tests"), width="stretch")
    st.markdown(text("experiment_plan.md"))

# ------------------------------------------------------------------ Recommendations
with tabs[7]:
    rec = HERE / "recommendations.md"
    st.markdown(rec.read_text() if rec.exists() else "_Write your recommendations in dashboard/recommendations.md_")
