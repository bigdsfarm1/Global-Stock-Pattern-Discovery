"""Display results from the scheduled GitHub Actions market scan."""
import io
import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen

import pandas as pd
import streamlit as st

BASE = "https://raw.githubusercontent.com/bigdsfarm1/Global-Stock-Pattern-Discovery/main/background_results/"

@st.cache_data(ttl=300, show_spinner=False)
def load_market_opportunities():
    """Read published scan outputs; never run a live market-wide scan in the UI."""
    def fetch(name):
        request = Request(BASE + name, headers={"User-Agent": "Global-Stock-Pattern-Discovery"})
        with urlopen(request, timeout=12) as response:
            return response.read()
    summary = json.loads(fetch("scan_summary.json"))
    data = pd.read_csv(io.BytesIO(fetch("ranked_opportunities.csv")))
    return summary, data

def show_market_opportunities():
    st.subheader("🌍 Market Opportunities")
    st.caption("Automatic background research, not a live feed or a buy recommendation. No Scan All button.")
    if st.button("Refresh published results", key="refresh_opportunities"):
        load_market_opportunities.clear()
    try:
        summary, data = load_market_opportunities()
    except Exception:
        st.info("The first published scan is not available yet. The next successful scheduled GitHub scan will populate this section.")
        st.link_button("View background scan status", "https://github.com/bigdsfarm1/Global-Stock-Pattern-Discovery/actions/workflows/background-market-scan.yml")
        return
    generated = pd.to_datetime(summary.get("generated_utc"), utc=True, errors="coerce")
    if pd.notna(generated):
        st.caption("Last completed scan: " + generated.strftime("%d %b %Y, %H:%M UTC"))
        age = (datetime.now(timezone.utc) - generated.to_pydatetime()).total_seconds() / 3600
        if age > 36:
            st.warning("Results are over 36 hours old. Check the scheduled workflow before using them.")
    st.caption(f"Latest batch: {summary.get('analysed', len(data))} usable of {summary.get('batch_requested', summary.get('requested', '?'))} attempted; {summary.get('stored_assets', len(data))} assets retained from rolling scans. Universe: {summary.get('requested', '?')} symbols.")
    st.caption("Coverage currently includes US-listed shares, selected UK shares, crypto and commodity futures. Global exchange coverage is not complete; earlier batch results may be older.")
    if data.empty:
        st.info("The scan returned no usable asset data.")
        return
    for col in ["research_score", "change_5d_pct", "change_20d_pct", "volume_ratio"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    for col in ["pattern_window", "pattern_matches", "pattern_similarity", "pattern_historical_hit_pct", "pattern_median_forward_pct"]:
        if col not in data.columns:
            data[col] = pd.NA
        data[col] = pd.to_numeric(data[col], errors="coerce")
    for col in ["sequence_name", "sequence_stage"]:
        if col not in data.columns:
            data[col] = "None"
        data[col] = data[col].fillna("None")
    market = st.selectbox("Market filter", ["All markets", "Stocks", "Crypto", "Commodities"], key="opportunities_market")
    sequence_only = st.checkbox("Only show zigzag / breakdown sequences", value=False, key="opportunities_sequences")
    signal_only = st.checkbox("Only show assets with detected signals", value=True, key="opportunities_signals")
    view = data.copy()
    if market != "All markets":
        view = view.loc[view["market"] == market]
    if sequence_only:
        view = view.loc[view["sequence_name"] != "None"]
    if signal_only:
        view = view.loc[view["signals"].fillna("None") != "None"]
    view = view.sort_values(["research_score", "change_5d_pct"], ascending=[False, False]).head(30)
    if view.empty:
        st.info("No matching opportunities in the latest scan. Try a different filter.")
        return
    display = view[["market", "symbol", "sequence_stage", "signals", "pattern_window", "pattern_similarity", "pattern_matches", "pattern_historical_hit_pct", "pattern_median_forward_pct", "research_score", "change_5d_pct", "change_20d_pct", "volume_ratio"]].rename(columns={
        "market": "Market", "symbol": "Ticker", "sequence_stage": "Price-action sequence", "signals": "Detected signals",
        "pattern_window": "Pattern days", "pattern_similarity": "Chart match %",
        "pattern_matches": "Past analogs", "pattern_historical_hit_pct": "Past +10% hits",
        "pattern_median_forward_pct": "Past 10d median %",
        "research_score": "Research score", "change_5d_pct": "5-day %", "change_20d_pct": "20-day %",
        "volume_ratio": "Volume / avg",
    })
    st.dataframe(display, hide_index=True, use_container_width=True)
    st.caption("Price-action sequences look for a sharp selloff, several zigzag turns, weaker highs and a possible or confirmed support breakdown. This is a rule-based research signal, not a proven trading edge. Older scans may not yet contain these fields.")
    st.caption("Chart matches compare full 10/20/40-day price paths against earlier shapes in the SAME asset. Past +10% hits count gains over the following 10 days; small samples are exploratory, not forecasts. Older results may have blank pattern fields until rescanned.")
    st.caption("Scores rank simple technical conditions; they are NOT probabilities, forecasts or validated trading edges. Daily candles can be stale before the market opens; futures volume can be distorted by contract rolls.")
    st.link_button("View GitHub scan runs", "https://github.com/bigdsfarm1/Global-Stock-Pattern-Discovery/actions/workflows/background-market-scan.yml")
