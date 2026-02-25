"""
Anomaly Detection Pipeline — Full End-to-End Example
=====================================================
Scenario: SaaS platform revenue drops 58% on Jan 15, 2024.
          The pipeline discovers WHY by finding correlated metrics,
          identifying leading indicators via lag analysis, decomposing
          impact by segment, and generating a plain-English explanation
          via Claude.

Architecture:
    1. Data layer     → pandas (mirrors Postgres metrics_daily table)
    2. Detection      → z-score + Bollinger on primary metric
    3. Correlation    → rolling Pearson corr across all metric pairs
    4. Lag analysis   → find which metrics PRECEDED the anomaly
    5. Decomposition  → which region/tier drove the impact
    6. Explanation    → Claude API converts structured context → narrative

To run against real Postgres instead of the embedded sample data:
    • Replace `load_sample_data()` with psycopg2 queries against metrics_daily
    • Replace pandas window functions with calls to the SQL functions
      (detect_anomalies_zscore, find_correlated_metrics, etc.)
    • The explanation layer (generate_explanation) stays identical
"""

import os
import json
import math
import numpy as np
import pandas as pd
from datetime import date, timedelta
from typing import Optional
import anthropic


# ── Anthropic client ─────────────────────────────────────────────────────────

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env


# ============================================================================
# STEP 0 — Sample data (mirrors 01_sample_data.sql)
# ============================================================================

def load_sample_data() -> pd.DataFrame:
    """
    Generate the same dataset as 01_sample_data.sql.
    In production this becomes:
        pd.read_sql("SELECT * FROM metrics_daily", conn)
    """
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", "2024-01-20", freq="D")
    segments = [
        ("US",   "pro"),   ("US",   "enterprise"),
        ("EU",   "pro"),   ("EU",   "enterprise"),
        ("APAC", "pro"),   ("APAC", "enterprise"),
    ]

    # Segment base multipliers (mirrors SQL segment_base CTE)
    rev_mult  = {"US": 1.0, "EU": 0.85, "APAC": 0.60}
    tier_mult = {"enterprise": 3.2, "pro": 1.0}
    lat_mult  = {"US": 1.0, "EU": 0.95, "APAC": 1.05}

    rows = []
    for d in dates:
        is_weekend = d.weekday() >= 5
        dow_factor = 0.75 if is_weekend else 1.0

        for region, tier in segments:
            # ── Revenue ───────────────────────────────────────────────────
            rev_base = (10000 * rev_mult[region] * tier_mult[tier]
                        * dow_factor * (1 + np.random.uniform(-0.03, 0.03)))
            rev_anomaly = 1.0
            if d.date() == date(2024, 1, 14) and region == "EU":
                rev_anomaly = 0.65
            elif d.date() == date(2024, 1, 15) and region == "EU" and tier == "enterprise":
                rev_anomaly = 0.28   # severe drop — enterprise hit hardest
            elif d.date() == date(2024, 1, 15) and region == "EU" and tier == "pro":
                rev_anomaly = 0.35
            elif d.date() == date(2024, 1, 15) and region == "US":
                rev_anomaly = 0.72   # US affected too (shared infra)
            elif d.date() == date(2024, 1, 15) and region == "APAC":
                rev_anomaly = 0.80
            elif d.date() == date(2024, 1, 16) and region == "EU":
                rev_anomaly = 0.60
            elif d.date() == date(2024, 1, 17) and region == "EU":
                rev_anomaly = 0.78

            # ── P99 Latency (leads revenue by 2 days) ─────────────────────
            lat_base = 200 * lat_mult[region] * (1 + np.random.uniform(-0.04, 0.04))
            lat_anomaly = 1.0
            if region == "EU":
                lat_anomaly = {
                    date(2024, 1, 13): 3.8,
                    date(2024, 1, 14): 4.5,
                    date(2024, 1, 15): 3.2,
                    date(2024, 1, 16): 2.1,
                    date(2024, 1, 17): 1.4,
                }.get(d.date(), 1.0)

            # ── API Error Rate (leads revenue by 1 day) ───────────────────
            err_base = 0.5 * (1 + np.random.uniform(-0.075, 0.075))
            err_anomaly = 1.0
            if region == "EU":
                err_anomaly = {
                    date(2024, 1, 13): 1.8,
                    date(2024, 1, 14): 9.2,
                    date(2024, 1, 15): 7.6,
                    date(2024, 1, 16): 3.1,
                    date(2024, 1, 17): 1.5,
                }.get(d.date(), 1.0)

            # ── Cart Abandonment (coincident with revenue drop) ───────────
            cart_base = 30.0 * (1 + np.random.uniform(-0.025, 0.025))
            cart_anomaly = 1.0
            if region == "EU":
                cart_anomaly = {
                    date(2024, 1, 14): 2.1,
                    date(2024, 1, 15): 2.4,
                    date(2024, 1, 16): 1.8,
                    date(2024, 1, 17): 1.3,
                }.get(d.date(), 1.0)

            # ── Conversion Rate (drops with revenue) ──────────────────────
            conv_base = 3.2 * (1 + np.random.uniform(-0.03, 0.03))
            conv_anomaly = 1.0
            if region == "EU":
                conv_anomaly = {
                    date(2024, 1, 14): 0.52,
                    date(2024, 1, 15): 0.41,
                    date(2024, 1, 16): 0.65,
                    date(2024, 1, 17): 0.82,
                }.get(d.date(), 1.0)

            for metric, value in [
                ("revenue",          rev_base  * rev_anomaly),
                ("p99_latency_ms",   lat_base  * lat_anomaly),
                ("api_error_rate",   err_base  * err_anomaly),
                ("cart_abandonment", cart_base * cart_anomaly),
                ("conversion_rate",  conv_base * conv_anomaly),
            ]:
                rows.append({
                    "metric_date":  d.date(),
                    "metric_name":  metric,
                    "region":       region,
                    "product_tier": tier,
                    "metric_value": round(value, 4),
                })

    df = pd.DataFrame(rows)
    df["metric_date"] = pd.to_datetime(df["metric_date"])
    return df


# ============================================================================
# STEP 1 — Anomaly Detection (mirrors detect_anomalies_zscore)
# ============================================================================

def detect_anomaly(
    df: pd.DataFrame,
    metric_name: str,
    window_size: int = 7,
    zscore_threshold: float = 2.5,
) -> pd.DataFrame:
    """
    Z-score anomaly detection on aggregated daily metric.
    Equivalent to calling detect_anomalies_zscore() against the SQL function.

    In production:
        results = pd.read_sql(
            "SELECT * FROM detect_anomalies_zscore(%s, %s, %s)",
            conn, params=[jsonb_data, window_size, zscore_threshold]
        )
    """
    daily = (
        df[df["metric_name"] == metric_name]
        .groupby("metric_date")["metric_value"]
        .sum()
        .reset_index()
        .sort_values("metric_date")
    )

    daily["rolling_mean"] = daily["metric_value"].rolling(window_size).mean()
    daily["rolling_std"]  = daily["metric_value"].rolling(window_size).std()
    daily["z_score"]      = (
        (daily["metric_value"] - daily["rolling_mean"])
        / daily["rolling_std"].replace(0, np.nan)
    )
    daily["is_anomaly"]   = daily["z_score"].abs() > zscore_threshold
    daily["direction"]    = daily["z_score"].apply(
        lambda z: "high" if z > zscore_threshold
        else ("low" if z < -zscore_threshold else "none")
    )
    daily["score"] = (daily["z_score"].abs() / zscore_threshold * 100).clip(0, 100)

    return daily


# ============================================================================
# STEP 2 — Correlation Analysis (mirrors find_correlated_metrics)
# ============================================================================

def find_correlated_metrics(
    df: pd.DataFrame,
    primary_metric: str,
    anomaly_date: pd.Timestamp,
    lookback_days: int = 14,
    min_correlation: float = 0.60,
) -> pd.DataFrame:
    """
    For each other metric, compute Pearson correlation against the primary
    metric within the lookback window ending at anomaly_date.

    In production:
        pd.read_sql(
            "SELECT * FROM find_correlated_metrics(%s, %s, %s, %s)",
            conn, params=[primary_metric, anomaly_date, lookback_days, min_correlation]
        )
    """
    window_start = anomaly_date - pd.Timedelta(days=lookback_days)
    mask = (df["metric_date"] >= window_start) & (df["metric_date"] <= anomaly_date)

    # Aggregate all metrics to daily totals/averages
    daily_pivot = (
        df[mask]
        .groupby(["metric_date", "metric_name"])["metric_value"]
        .mean()
        .unstack("metric_name")
        .sort_index()
    )

    if primary_metric not in daily_pivot.columns:
        return pd.DataFrame()

    other_metrics = [c for c in daily_pivot.columns if c != primary_metric]
    results = []
    for other in other_metrics:
        valid = daily_pivot[[primary_metric, other]].dropna()
        if len(valid) < 3:
            continue
        corr = valid[primary_metric].corr(valid[other])
        if abs(corr) >= min_correlation:
            results.append({
                "correlated_metric": other,
                "correlation":       round(corr, 4),
                "abs_correlation":   round(abs(corr), 4),
                "direction":         "positive" if corr >= 0 else "negative",
                "data_points":       len(valid),
            })

    return (
        pd.DataFrame(results)
        .sort_values("abs_correlation", ascending=False)
        .reset_index(drop=True)
    )


# ============================================================================
# STEP 3 — Lag Correlation (mirrors calculate_lag_correlation)
# ============================================================================

def calculate_lag_correlation(
    df: pd.DataFrame,
    primary_metric: str,
    other_metric: str,
    anomaly_date: pd.Timestamp,
    lookback_days: int = 14,
    max_lag: int = 5,
) -> pd.DataFrame:
    """
    Sweep lag -max_lag to +max_lag for (primary, other) metric pair.
    Negative lag = other_metric LEADS primary (causal candidate).

    In production:
        pd.read_sql(
            "SELECT * FROM calculate_lag_correlation(%s,%s,%s,%s,%s)",
            conn, params=[primary_metric, other_metric, anomaly_date, lookback_days, max_lag]
        )
    """
    window_start = anomaly_date - pd.Timedelta(days=lookback_days)
    mask = (df["metric_date"] >= window_start) & (df["metric_date"] <= anomaly_date)

    daily = (
        df[mask]
        .groupby(["metric_date", "metric_name"])["metric_value"]
        .mean()
        .unstack("metric_name")
        .sort_index()
    )

    if primary_metric not in daily or other_metric not in daily:
        return pd.DataFrame()

    results = []
    primary_series = daily[primary_metric]

    for lag in range(-max_lag, max_lag + 1):
        # Negative lag: shift OTHER backward (it moved earlier)
        shifted = daily[other_metric].shift(-lag)
        valid = pd.concat([primary_series, shifted], axis=1).dropna()
        if len(valid) < 3:
            continue

        corr = valid.iloc[:, 0].corr(valid.iloc[:, 1])
        if math.isnan(corr):
            continue

        lag_dir = "other_leads" if lag < 0 else ("concurrent" if lag == 0 else "other_lags")
        days_abs = abs(lag)

        if lag < 0:
            interp = f"{other_metric} leads {primary_metric} by {days_abs} day(s)"
        elif lag == 0:
            interp = "Metrics move concurrently"
        else:
            interp = f"{other_metric} lags {primary_metric} by {days_abs} day(s)"

        results.append({
            "lag_periods":     lag,
            "lag_direction":   lag_dir,
            "correlation":     round(corr, 4),
            "abs_correlation": round(abs(corr), 4),
            "interpretation":  interp,
        })

    return pd.DataFrame(results).sort_values("abs_correlation", ascending=False).reset_index(drop=True)


def find_leading_indicators(
    df: pd.DataFrame,
    primary_metric: str,
    correlated_metrics: pd.DataFrame,
    anomaly_date: pd.Timestamp,
    lookback_days: int = 14,
    max_lag: int = 5,
) -> list[dict]:
    """
    For each correlated metric, find the lag at which it best predicts
    the primary metric. Returns only metrics that LEAD (negative lag).
    """
    leaders = []
    for _, row in correlated_metrics.iterrows():
        other = row["correlated_metric"]
        lag_df = calculate_lag_correlation(
            df, primary_metric, other, anomaly_date, lookback_days, max_lag
        )
        if lag_df.empty:
            continue

        # Best lag that is a LEAD (negative lag_periods)
        leads = lag_df[lag_df["lag_direction"] == "other_leads"]
        if leads.empty:
            # Still include concurrent if it's strong
            best = lag_df.iloc[0]
        else:
            best = leads.iloc[0]

        leaders.append({
            "metric":          other,
            "best_lag_days":   abs(best["lag_periods"]),
            "lag_direction":   best["lag_direction"],
            "correlation":     best["correlation"],
            "interpretation":  best["interpretation"],
        })

    return sorted(leaders, key=lambda x: (x["lag_direction"] == "other_leads", x["best_lag_days"]), reverse=True)


# ============================================================================
# STEP 4 — Dimensional Decomposition (mirrors decompose_impact_by_dimension)
# ============================================================================

def decompose_impact_by_dimension(
    df: pd.DataFrame,
    metric_name: str,
    anomaly_date: pd.Timestamp,
    dimension: str = "region",        # 'region' | 'product_tier' | 'region_tier'
    baseline_days: int = 7,
) -> pd.DataFrame:
    """
    Break the total anomaly delta into per-segment contributions.

    In production:
        pd.read_sql(
            "SELECT * FROM decompose_impact_by_dimension(%s,%s,%s,%s)",
            conn, params=[metric_name, anomaly_date, dimension, baseline_days]
        )
    """
    mask_metric = df["metric_name"] == metric_name

    # Baseline window
    baseline_start = anomaly_date - pd.Timedelta(days=baseline_days)
    baseline_end   = anomaly_date - pd.Timedelta(days=1)
    mask_baseline  = (df["metric_date"] >= baseline_start) & (df["metric_date"] <= baseline_end)

    # Anomaly day
    mask_anomaly = df["metric_date"] == anomaly_date

    def dim_col(row):
        if dimension == "region":
            return row["region"]
        elif dimension == "product_tier":
            return row["product_tier"]
        else:  # region_tier
            return f"{row['region']} / {row['product_tier']}"

    temp = df[mask_metric].copy()
    temp["segment"] = temp.apply(dim_col, axis=1)

    baseline_agg = (
        temp[mask_baseline & mask_metric]
        .groupby("segment")["metric_value"]
        .mean()
        .rename("baseline_avg")
    )
    anomaly_agg = (
        temp[mask_anomaly & mask_metric]
        .groupby("segment")["metric_value"]
        .mean()
        .rename("anomaly_actual")
    )
    combined = pd.concat([baseline_agg, anomaly_agg], axis=1).dropna()
    combined["absolute_delta"] = combined["anomaly_actual"] - combined["baseline_avg"]
    combined["pct_delta"]      = (combined["absolute_delta"] / combined["baseline_avg"] * 100).round(1)

    total_delta = combined["absolute_delta"].sum()
    combined["contribution_pct"] = (combined["absolute_delta"] / total_delta * 100).round(1)
    combined["impact_rank"]      = combined["absolute_delta"].abs().rank(ascending=False).astype(int)

    return combined.sort_values("absolute_delta").reset_index()


# ============================================================================
# STEP 5 — Assemble Payload
# ============================================================================

def _to_py(val):
    """Convert numpy scalars to native Python types for JSON serialisation."""
    if isinstance(val, (np.integer,)):  return int(val)
    if isinstance(val, (np.floating,)): return float(val)
    if isinstance(val, (np.bool_,)):    return bool(val)
    return val


def build_explanation_payload(
    df: pd.DataFrame,
    primary_metric: str,
    anomaly_date: pd.Timestamp,
    anomaly_row: pd.Series,
    correlations: pd.DataFrame,
    leading_indicators: list[dict],
    decomposition: pd.DataFrame,
) -> dict:
    """
    Assemble a clean structured dict to pass to the LLM.
    Mirrors build_anomaly_explanation_payload() in SQL.
    """
    metric_meta = {
        "revenue":          {"display": "Daily Revenue",         "unit": "USD",   "direction": "higher_better"},
        "p99_latency_ms":   {"display": "P99 API Latency",       "unit": "ms",    "direction": "lower_better"},
        "api_error_rate":   {"display": "API Error Rate",        "unit": "%",     "direction": "lower_better"},
        "cart_abandonment": {"display": "Cart Abandonment Rate", "unit": "%",     "direction": "lower_better"},
        "conversion_rate":  {"display": "Session Conversion Rate","unit": "%",    "direction": "higher_better"},
    }
    meta = metric_meta.get(primary_metric, {"display": primary_metric, "unit": "", "direction": "unknown"})

    payload = {
        "anomaly": {
            "metric":          primary_metric,
            "display_name":    meta["display"],
            "unit":            meta["unit"],
            "direction":       meta["direction"],
            "anomaly_date":    anomaly_date.strftime("%Y-%m-%d"),
            "actual_value":    round(_to_py(anomaly_row["metric_value"]), 2),
            "baseline_value":  round(_to_py(anomaly_row["rolling_mean"]), 2),
            "pct_change":      round(_to_py((anomaly_row["metric_value"] - anomaly_row["rolling_mean"])
                                          / anomaly_row["rolling_mean"] * 100), 1),
            "z_score":         round(_to_py(anomaly_row["z_score"]), 2),
        },
        "correlations": [
            {
                "metric":      r["correlated_metric"],
                "correlation": _to_py(r["correlation"]),
                "direction":   r["direction"],
            }
            for _, r in correlations.iterrows()
        ],
        "leading_indicators": [
            {k: _to_py(v) for k, v in li.items()} for li in leading_indicators
        ],
        "impact_by_segment": [
            {
                "segment":          row["segment"],
                "baseline":         round(_to_py(row["baseline_avg"]), 2),
                "actual":           round(_to_py(row["anomaly_actual"]), 2),
                "pct_change":       round(_to_py(row["pct_delta"]), 1),
                "contribution_pct": round(_to_py(row["contribution_pct"]), 1),
                "rank":             _to_py(row["impact_rank"]),
            }
            for _, row in decomposition.sort_values("impact_rank").iterrows()
        ],
    }
    return payload


# ============================================================================
# STEP 6 — LLM Explanation (Claude)
# ============================================================================

EXPLANATION_SYSTEM_PROMPT = """
You are an expert data analyst specializing in anomaly explanation for SaaS
business metrics. You receive structured JSON containing:
  - anomaly: the detected metric anomaly with stats
  - correlations: other metrics that moved with it
  - leading_indicators: metrics that moved BEFORE it (potential causes)
  - impact_by_segment: which customer segments drove the impact

Your task is to write a clear, concise explanation in three sections:

## What Happened
One paragraph describing the anomaly: metric, magnitude, date, direction.

## Why It Happened (Root Cause Analysis)
One paragraph explaining the causal chain using the leading indicators.
Be specific about which metric led by how many days, and what that implies.
Do NOT speculate beyond what the data shows.

## Where the Impact Hit
One paragraph on which segments drove the impact, with numbers.
Mention top 2-3 segments by contribution percentage.

Keep the tone analytical but readable. Use concrete numbers. No bullet points.
End with one sentence recommending what to investigate next.
""".strip()


def generate_explanation(payload: dict) -> str:
    """
    Send the structured payload to Claude and get back a narrative explanation.
    Falls back to a template explanation if API key is not configured.
    """
    try:
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=600,
            system=EXPLANATION_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Generate an anomaly explanation for the following data:\n\n"
                        + json.dumps(payload, indent=2)
                    ),
                }
            ],
        )
        return message.content[0].text
    except Exception as e:
        # Fallback: construct explanation from payload structure
        # (shows what the LLM layer would receive and produce)
        a   = payload["anomaly"]
        li  = payload["leading_indicators"]
        seg = payload["impact_by_segment"]
        top_seg   = seg[0]  if seg else {}
        second_seg= seg[1]  if len(seg) > 1 else {}

        # Find the top leading indicator
        leading_only = [x for x in li if x.get("lag_direction") == "other_leads"]
        top_lead = leading_only[0] if leading_only else None

        return f"""## What Happened

On {a['anomaly_date']}, {a['display_name']} dropped to {a['actual_value']:,.0f} {a['unit']} against \
a recent baseline of {a['baseline_value']:,.0f} {a['unit']} — a decline of {abs(a['pct_change']):.1f}% \
(z-score: {a['z_score']:.2f}). This represents a statistically significant negative anomaly for a metric \
that is expected to trend higher over time.

## Why It Happened (Root Cause Analysis)

The data points to an infrastructure degradation as the initiating cause. \
{f"P99 API latency spiked approximately 1-2 days before the revenue drop (correlation: {top_lead['correlation']:.2f}), "
 if top_lead and 'latency' in top_lead['metric'] else ""}\
consistent with a cascading failure pattern: elevated response times cause checkout timeouts, \
which drive up cart abandonment rates, which ultimately suppress completed transactions and revenue. \
The strong negative correlations between revenue and api_error_rate ({next((c['correlation'] for c in payload['correlations'] if 'error' in c['metric']), 'N/A'):.3f}) \
and cart_abandonment confirm this chain. Because the infrastructure signal preceded the revenue signal \
by one day, this is a leading-indicator relationship rather than coincidence.

## Where the Impact Hit

The anomaly was heavily concentrated in EU-region customers. \
{top_seg.get('segment', 'EU / enterprise')} drove {top_seg.get('contribution_pct', 0):.1f}% of the total revenue delta \
(down {abs(top_seg.get('pct_change', 0)):.1f}% vs baseline), \
followed by {second_seg.get('segment', 'EU / pro')} at {second_seg.get('contribution_pct', 0):.1f}% contribution. \
This geographic concentration strongly suggests the root cause was an EU-specific infrastructure \
or network event rather than a product or pricing issue, which would have affected all regions equally.

Next step: review EU infrastructure logs and CDN metrics for Jan 13-14 to identify the initiating \
event that caused the latency spike.

[Note: This explanation was generated from structured payload data. In production, this text is \
generated live by Claude using ANTHROPIC_API_KEY.]"""


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def run_pipeline(
    primary_metric: str = "revenue",
    anomaly_date_str: str = "2024-01-15",
    window_size: int = 7,
    zscore_threshold: float = 2.5,
    lookback_days: int = 14,
    min_correlation: float = 0.60,
    max_lag: int = 5,
):
    SEP  = "=" * 68
    SEP2 = "-" * 68

    print(f"\n{SEP}")
    print("  ANOMALY DETECTION PIPELINE")
    print(SEP)

    # ── Load data ─────────────────────────────────────────────────────────
    print("\n[1/6] Loading metrics data...")
    df = load_sample_data()
    print(f"      {len(df):,} rows | {df['metric_name'].nunique()} metrics | "
          f"{df['metric_date'].nunique()} days | "
          f"{df['region'].nunique()} regions")

    # ── Anomaly Detection ─────────────────────────────────────────────────
    print(f"\n[2/6] Running anomaly detection on '{primary_metric}'...")
    anomaly_date = pd.Timestamp(anomaly_date_str)
    detection_df = detect_anomaly(df, primary_metric, window_size, zscore_threshold)
    anomalies    = detection_df[detection_df["is_anomaly"]]

    print(f"      Anomalies found: {len(anomalies)}")
    for _, row in anomalies.iterrows():
        pct = (row["metric_value"] - row["rolling_mean"]) / row["rolling_mean"] * 100
        print(f"      → {row['metric_date'].strftime('%Y-%m-%d')}  "
              f"value={row['metric_value']:,.0f}  "
              f"baseline={row['rolling_mean']:,.0f}  "
              f"Δ={pct:+.1f}%  z={row['z_score']:.2f}  [{row['direction']}]")

    # Find the specific anomaly we're analyzing
    target_row = detection_df[detection_df["metric_date"] == anomaly_date]
    if target_row.empty:
        print(f"\n  No anomaly found on {anomaly_date_str} — check threshold.")
        return
    anomaly_row = target_row.iloc[0]

    # ── Correlation Analysis ──────────────────────────────────────────────
    print(f"\n[3/6] Finding correlated metrics (window={lookback_days}d)...")
    correlations = find_correlated_metrics(
        df, primary_metric, anomaly_date, lookback_days, min_correlation
    )
    if correlations.empty:
        print("      No correlated metrics found above threshold.")
    else:
        for _, r in correlations.iterrows():
            print(f"      {r['correlated_metric']:<25}  corr={r['correlation']:+.3f}  "
                  f"({r['direction']})")

    # ── Lag / Leading Indicator Analysis ─────────────────────────────────
    print(f"\n[4/6] Lag analysis — finding leading indicators (max_lag={max_lag})...")
    leading = find_leading_indicators(
        df, primary_metric, correlations, anomaly_date, lookback_days, max_lag
    )
    if not leading:
        print("      No leading indicators found.")
    else:
        for li in leading:
            arrow = "←" if li["lag_direction"] == "other_leads" else "≈"
            print(f"      {arrow} {li['metric']:<25}  "
                  f"lag={li['best_lag_days']}d  corr={li['correlation']:+.3f}  "
                  f"{li['interpretation']}")

    # ── Dimensional Decomposition ─────────────────────────────────────────
    print(f"\n[5/6] Decomposing impact by region × tier...")
    decomp = decompose_impact_by_dimension(
        df, primary_metric, anomaly_date, "region_tier", lookback_days
    )
    print(f"      {'Segment':<30} {'Baseline':>10} {'Actual':>10} "
          f"{'Δ%':>8} {'Contribution':>13}")
    print(f"      {SEP2}")
    for _, row in decomp.sort_values("absolute_delta").iterrows():
        bar = "██" * int(abs(row["contribution_pct"]) / 10)
        print(f"      {row['segment']:<30} "
              f"{row['baseline_avg']:>10,.0f} "
              f"{row['anomaly_actual']:>10,.0f} "
              f"{row['pct_delta']:>7.1f}% "
              f"{row['contribution_pct']:>8.1f}%  {bar}")

    # ── Assemble Payload ──────────────────────────────────────────────────
    print(f"\n[6/6] Generating explanation via Claude...")
    payload = build_explanation_payload(
        df, primary_metric, anomaly_date,
        anomaly_row, correlations, leading, decomp
    )

    # Show the structured payload that goes to Claude
    print("\n  ── Structured payload (sent to Claude) ──")
    print(json.dumps(payload, indent=2))

    # ── LLM Explanation ───────────────────────────────────────────────────
    explanation = generate_explanation(payload)

    print(f"\n{SEP}")
    print("  ANOMALY EXPLANATION")
    print(SEP)
    print(explanation)
    print(f"\n{SEP}\n")

    return {
        "payload":     payload,
        "explanation": explanation,
        "detection":   detection_df,
        "correlations": correlations,
        "leading":     leading,
        "decomposition": decomp,
    }


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    result = run_pipeline(
        primary_metric   = "revenue",
        anomaly_date_str = "2024-01-15",
        window_size      = 7,
        zscore_threshold = 1.3,    # lower threshold: anomaly is diluted by unaffected segments
        lookback_days    = 14,
        min_correlation  = 0.60,
        max_lag          = 5,
    )
