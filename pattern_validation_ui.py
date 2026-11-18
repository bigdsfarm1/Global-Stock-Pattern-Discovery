"""Simple, on-demand historical chart-pattern check for hourly and daily candles."""
import pandas as pd
import streamlit as st
import yfinance as yf
from pattern_discovery import discover_patterns

@st.cache_data(ttl=900, show_spinner=False)
def fetch_candles(symbol, interval):
    period = "60d" if interval == "Hourly" else "2y"
    granularity = "1h" if interval == "Hourly" else "1d"
    d = yf.Ticker(symbol).history(period=period, interval=granularity, auto_adjust=True)
    if d.empty:
        return d
    return d[["Open", "High", "Low", "Close"]].dropna()

def show_pattern_validation():
    st.subheader("🧪 Pattern Validation")
    st.write("Find similar chart shapes from the past and see what happened next.")
    market = st.radio("Market", ["Stocks", "Crypto", "Commodities"], horizontal=True, key="validation_market")
    symbol = st.text_input("Yahoo Finance ticker", value="AAPL" if market == "Stocks" else ("BTC-USD" if market == "Crypto" else "GC=F"), key="validation_ticker").strip().upper()
    interval = st.radio("Chart type", ["Daily", "Hourly"], horizontal=True, key="validation_interval")
    st.caption("Hourly comparisons use 1-hour candles, not calendar hours. Free Yahoo hourly history is usually limited to approximately 60 days.")
    if not st.button("Check historical patterns", type="primary", disabled=not symbol):
        st.info("Enter a ticker and tap Check historical patterns.")
        return
    with st.spinner("Comparing past chart formations..."):
        try:
            d = fetch_candles(symbol, interval)
        except Exception as exc:
            st.error(f"Price history unavailable: {exc}")
            return
    if d.empty or len(d) < 65:
        st.warning("Not enough historical candles to compare patterns for this ticker and interval.")
        return
    from pattern_discovery import WINDOWS
    st.line_chart(d["Close"].tail(40))
    results = []
    for window in WINDOWS:
        # Restrict the discovery engine to each individual pattern length for a fair comparison.
        from pattern_discovery import discover_patterns_for_window
        result = discover_patterns_for_window(d["Close"].to_numpy(), window, ohlc=d[["Open","High","Low","Close"]].to_numpy())
        if result["pattern_matches"] >= 3:
            results.append(result)
    if not results:
        st.warning("Not enough distinct historical matches. No reliable conclusion can be drawn.")
        return
    st.write("**What happened after similar patterns?**")
    for r in results:
        with st.container(border=True):
            st.write(f'**{r["pattern_window"]}-candle pattern** · {r["pattern_matches"]} historical examples')
            a,b,c = st.columns(3)
            a.metric("Chart similarity", f'{r["pattern_similarity"]}%')
            b.metric("Rose 10%+ afterward", f'{r["pattern_historical_hit_pct"]}%')
            c.metric("Median next 10 candles", f'{r["pattern_median_forward_pct"]:+.1f}%')
    st.warning("These are in-sample historical comparisons, not validated forecasts. Hourly tests cover only the available short history, and market closures/gaps matter. A separate out-of-sample and cost-adjusted test is needed before calling a pattern reliable.")
