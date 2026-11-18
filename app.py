import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from scanner import PATTERNS, add_signals, event_study

st.set_page_config(page_title="Global Stock Pattern Discovery", page_icon="📈", layout="wide")
st.title("📈 Global Stock Pattern Discovery")
st.caption("Free experimental candlestick research — delayed/incomplete market data; not financial advice.")
st.warning("Research prototype: scans only the tickers you enter, not every stock worldwide. Historical hit rates do not imply future returns.")

DEFAULT = "AAPL,MSFT,NVDA,AMD,TSLA,RR.L,FORG.L,BZT.L"
tickers_text = st.text_area("Watchlist — Yahoo Finance symbols, comma-separated", value=DEFAULT, height=80)
col1, col2, col3 = st.columns(3)
with col1:
    period = st.selectbox("History", ["1y", "2y", "5y"], index=1)
with col2:
    horizon = st.selectbox("Forward evaluation window (trading days)", [5, 10, 20, 30, 60], index=3)
with col3:
    threshold = st.slider("Target rise (%)", 5, 100, 20, 5)

@st.cache_data(ttl=3600, show_spinner=False)
def load_prices(symbol, period):
    frame = yf.Ticker(symbol).history(period=period, auto_adjust=True)
    if frame.empty:
        return frame
    return frame.loc[:, ["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Open", "High", "Low", "Close"])

@st.cache_data(ttl=3600, show_spinner=False)
def get_news(symbol):
    try:
        return yf.Ticker(symbol).news or []
    except Exception:
        return []

symbols = list(dict.fromkeys(s.strip().upper() for s in tickers_text.replace("\n", ",").split(",") if s.strip()))[:25]
if len([s for s in tickers_text.replace("\n", ",").split(",") if s.strip()]) > 25:
    st.info("Free prototype limit: first 25 tickers are scanned.")
if st.button("Run pattern scan", type="primary"):
    if not symbols:
        st.error("Enter at least one ticker.")
        st.stop()
    rows, data, errors = [], {}, []
    progress = st.progress(0)
    for idx, symbol in enumerate(symbols):
        try:
            prices = load_prices(symbol, period)
            if len(prices) < max(40, horizon + 21):
                errors.append(f"{symbol}: insufficient price history")
                continue
            d = add_signals(prices)
            data[symbol] = d
            recent = d.iloc[-1]
            active = [p for p in PATTERNS if bool(recent[p])]
            for pattern in PATTERNS:
                stats = event_study(d, pattern, horizon, threshold / 100)
                rows.append({"Ticker": symbol, "Pattern": pattern, "Signal today": bool(recent[pattern]),
                             "Historical signals": stats["signals"], "Historical hit rate": stats["hit_rate"],
                             "Median maximum forward rise": stats["median_max_gain"],
                             "Latest close": float(recent["Close"])})
        except Exception as exc:
            errors.append(f"{symbol}: {type(exc).__name__}: {str(exc)[:120]}")
        finally:
            progress.progress((idx + 1) / len(symbols))
    st.session_state["scan"] = (rows, data, errors)
if "scan" in st.session_state:
    rows, data, errors = st.session_state["scan"]
    if rows:
        result = pd.DataFrame(rows).sort_values(["Signal today", "Historical hit rate", "Historical signals"], ascending=[False, False, False])
        st.subheader("Pattern ranking")
        # Percentage columns must be scaled before display.
        display = result.copy()
        display["Historical hit rate"] *= 100
        display["Median maximum forward rise"] *= 100
        st.caption("Historical hit = price reached target at any future daily HIGH within the window; incomplete forward windows excluded. Signals may overlap.")
        st.dataframe(display, hide_index=True, use_container_width=True, column_config={
            "Historical hit rate": st.column_config.NumberColumn(format="%.1f%%"),
            "Median maximum forward rise": st.column_config.NumberColumn(format="%.1f%%"),
            "Latest close": st.column_config.NumberColumn(format="%.3f")})
        chosen = st.selectbox("Explore ticker", list(data))
        d = data[chosen]
        fig = go.Figure(data=[go.Candlestick(x=d.index, open=d.Open, high=d.High, low=d.Low, close=d.Close)])
        fig.update_layout(title=f"{chosen} candlesticks (adjusted)", xaxis_rangeslider_visible=False, height=480)
        st.plotly_chart(fig, use_container_width=True)
        st.subheader(f"Recent headlines: {chosen}")
        news = get_news(chosen)[:8]
        if not news:
            st.info("No news returned for this ticker. News availability varies by market.")
        for item in news:
            content = item.get("content", item)
            title = content.get("title") or "Untitled"
            url = (content.get("canonicalUrl") or {}).get("url") if isinstance(content.get("canonicalUrl"), dict) else content.get("link")
            if url and str(url).startswith("https://"):
                st.markdown(f"- [{title}]({url})")
            else:
                st.write("•", title)
    if errors:
        st.warning("Some tickers could not be scanned: " + "; ".join(errors))
st.caption("Caveats: survivorship bias, overlapping events, no costs, possible data corrections and missing delisted securities. News is contextual, not an early-warning predictive model.")
