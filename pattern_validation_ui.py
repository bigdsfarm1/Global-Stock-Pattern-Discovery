"""Plain-language hourly and daily chart-pattern exploration."""
import pandas as pd
import streamlit as st
import yfinance as yf
from pattern_discovery import WINDOWS, HORIZON, discover_patterns_for_window

@st.cache_data(ttl=900, show_spinner=False)
def fetch_candles(symbol, interval):
    d = yf.Ticker(symbol).history(
        period="60d" if interval == "Hourly" else "2y",
        interval="1h" if interval == "Hourly" else "1d",
        auto_adjust=True,
    )
    return d[["Open", "High", "Low", "Close"]].dropna() if not d.empty else d

def show_pattern_validation():
    st.subheader("🧪 Pattern Validation")
    st.write("See what happened after similar chart patterns in the past.")
    market = st.radio("Market", ["Stocks", "Crypto", "Commodities"], horizontal=True, key="validation_market")
    examples = {"Stocks":"AAPL", "Crypto":"BTC-USD", "Commodities":"GC=F"}
    if st.session_state.get("validation_last_market") != market:
        st.session_state["validation_ticker"] = examples[market]
        st.session_state["validation_last_market"] = market
    symbol = st.text_input("Ticker", key="validation_ticker").strip().upper()
    interval = st.radio("Chart type", ["Daily", "Hourly"], horizontal=True, key="validation_interval")
    window = st.select_slider("How many candles make up the pattern?", options=list(WINDOWS), value=5)
    threshold = st.select_slider("What size rise are you looking for?", options=[2,5,10,20,50], value=5)
    unit = "hours of trading" if interval == "Hourly" else "trading days"
    st.caption(f"Compare the latest {window} candles with older patterns; measure the next {HORIZON} candles ({unit}).")
    if not st.button("Check historical patterns", type="primary", disabled=not symbol):
        st.info("Choose a market, chart type and pattern length, then tap Check historical patterns.")
        return
    try:
        with st.spinner("Loading market history and checking chart patterns..."):
            d = fetch_candles(symbol, interval)
    except Exception as exc:
        st.error(f"Could not retrieve historical prices for {symbol}: {exc}")
        return
    if d.empty:
        st.warning("No prices returned. Check the ticker or try another market.")
        return
    st.caption(f"Data: {len(d)} candles, from {d.index[0].strftime('%d %b %Y')} to {d.index[-1].strftime('%d %b %Y')}.")
    if len(d) < 2*window+HORIZON+10:
        st.warning("There is not enough historical data to check this pattern. Try a shorter pattern or daily charts.")
        return
    st.write(f"**Latest {window}-candle price pattern**")
    st.line_chart(d["Close"].tail(max(window,2)), height=190)
    result = discover_patterns_for_window(
        d["Close"].to_numpy(),window,threshold=threshold/100,
        ohlc=d[["Open","High","Low","Close"]].to_numpy(),
    )
    n = result["pattern_matches"]
    if n < 3:
        st.warning("Fewer than three independent historical examples were found. There isn't enough evidence to assess this pattern.")
        return
    positive = result["positive_count"]
    negative = result["negative_count"]
    st.write(f"### What happened after {n} similar patterns?")
    a,b,c = st.columns(3)
    a.metric("Price rose", f"{positive} of {n}")
    b.metric("Price fell", f"{negative} of {n}")
    c.metric(f"Rose {threshold}%+", f'{result["pattern_historical_hit_pct"]:.0f}%')
    st.write(f"**Typical outcome:** {result['pattern_median_forward_pct']:+.2f}% after {HORIZON} candles.")
    st.write(f"**Best example:** {result['best_return_pct']:+.2f}% · **Worst example:** {result['worst_return_pct']:+.2f}%")
    st.write("### Actual historical examples")
    rows=[]
    for x in result["examples"]:
        index=d.index[x["end_index"]-1]
        rows.append({
            "Pattern ended":index.strftime("%d %b %Y %H:%M") if interval=="Hourly" else index.strftime("%d %b %Y"),
            "Chart similarity":f'{x["similarity_pct"]:.0f}%',
            f"Next {HORIZON} candles":f'{x["return_pct"]:+.2f}%',
            "Outcome":"Rose" if x["return_pct"]>0 else ("Fell" if x["return_pct"]<0 else "Flat"),
        })
    st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    st.info(f"**Evidence: limited.** These are just {n} selected past examples from one asset, not independent proof of a predictive pattern. Similarity measures shape, not the chance of a rise.")
    st.caption("Prices are measured from the pattern's closing price to the close 10 candles later, not the maximum price reached in between. Hourly candles are trading hours, not necessarily consecutive clock hours. Yahoo's free hourly history is limited. Results exclude trading costs and are not out-of-sample validated.")
