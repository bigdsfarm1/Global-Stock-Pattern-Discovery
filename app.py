import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from scanner import PATTERNS, add_signals, event_study

st.set_page_config(page_title="Global Pattern Scanner", page_icon="📈", layout="centered")
st.title("📈 Global Pattern Scanner")
st.caption("Search one stock or cryptocurrency at a time. Free historical research; not trading advice.")

market = st.radio("Choose a market", ["Stocks", "Crypto"], horizontal=True)
examples = {"Stocks": "AAPL", "Crypto": "BTC-USD"}
query = st.text_input("Search company, ticker or coin", placeholder="e.g. Apple, AAPL, Bitcoin, BTC", key="search")
@st.cache_data(ttl=3600, show_spinner=False)
def search_symbols(q):
    try:
        return yf.Search(q, max_results=12).quotes
    except Exception:
        return []

matches = search_symbols(query.strip()) if len(query.strip()) >= 2 else []
choices = []
for item in matches:
    symbol = item.get("symbol", "")
    if not symbol:
        continue
    is_crypto = item.get("quoteType", "").upper() == "CRYPTOCURRENCY" or symbol.endswith("-USD")
    if (market == "Crypto") != is_crypto:
        continue
    choices.append((symbol, item.get("shortname") or item.get("longname") or symbol, item.get("exchange", "")))
if choices:
    labels = [f"{name} ({symbol}) — {exchange}" for symbol, name, exchange in choices]
    chosen = st.selectbox("Select the correct listing", range(len(choices)), format_func=lambda i: labels[i])
    symbol = choices[chosen][0]
else:
    symbol = query.strip().upper()
    if query.strip():
        st.caption("No matching suggestions? Enter an exact Yahoo Finance ticker. Crypto tickers usually end in -USD.")
if not symbol:
    st.info("Start by searching for a company or cryptocurrency above.")
    st.stop()
with st.expander("Analysis settings"):
    period = st.selectbox("Historical data", ["1y", "2y", "5y"], index=1)
    horizon = st.selectbox("Evaluation window (days of price bars)", [5, 10, 20, 30, 60], index=3)
    target = st.slider("Target price rise (%)", 5, 100, 20, 5)

@st.cache_data(ttl=3600, show_spinner=False)
def prices_for(ticker, history):
    d = yf.Ticker(ticker).history(period=history, auto_adjust=True)
    return d[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Open", "High", "Low", "Close"]) if not d.empty else d

@st.cache_data(ttl=3600, show_spinner=False)
def news_for(ticker):
    try:
        return yf.Ticker(ticker).news or []
    except Exception:
        return []

if st.button("🔎 Analyse this investment", type="primary", use_container_width=True):
    st.session_state["selection"] = (symbol, period, horizon, target)
if "selection" not in st.session_state:
    st.stop()
symbol, period, horizon, target = st.session_state["selection"]
st.subheader(f"Analysis: {symbol}")
try:
    prices = prices_for(symbol, period)
except Exception as exc:
    st.error(f"Market data could not be loaded: {str(exc)[:180]}")
    st.stop()
if len(prices) < max(40, horizon + 21):
    st.error("Not enough reliable historical data for this symbol. Check the ticker or try another asset.")
    st.stop()
d = add_signals(prices)
close = float(d["Close"].iloc[-1])
st.metric("Latest available closing price (quote currency)", f"{close:,.5f}")
st.caption("May be delayed; the price is not a live executable quote.")
active = [p for p in PATTERNS if bool(d[p].iloc[-1])]
if active:
    st.success("Detected on latest price bar: " + ", ".join(active))
else:
    st.info("No monitored pattern detected on the latest price bar. This is not a buy signal.")
st.subheader("What did similar patterns do historically?")
for p in PATTERNS:
    stats = event_study(d, p, horizon, target / 100)
    with st.container(border=True):
        st.markdown(f"**{p}**")
        if stats["signals"]:
            st.write(f'{stats["hit_rate"]:.1%} reached +{target}% within {horizon} bars')
            st.caption(f'{stats["signals"]} historical occurrences. ' + ("Small sample; unreliable." if stats["signals"] < 30 else "Overlapping signals can exaggerate reliability."))
        else:
            st.caption("Not enough historical examples to calculate a hit rate.")
st.subheader("Price chart")
fig = go.Figure(data=[go.Candlestick(x=d.index, open=d.Open, high=d.High, low=d.Low, close=d.Close)])
fig.update_layout(height=420, xaxis_rangeslider_visible=False, margin=dict(l=5,r=5,t=20,b=10))
st.plotly_chart(fig, use_container_width=True)
st.subheader("Recent news")
news = news_for(symbol)[:6]
if not news:
    st.caption("No recent headlines available from this data source.")
for item in news:
    c = item.get("content", item)
    title = c.get("title", "Untitled")
    link = c.get("canonicalUrl", {})
    url = link.get("url") if isinstance(link, dict) else c.get("link")
    if url and str(url).startswith("https://"):
        st.markdown(f"- [{title}]({url})")
    else:
        st.write("• " + title)
st.warning("Research only. No reliable buy/sell price or confidence probability is calculated yet. Historical results may contain overlap and survivorship bias, and exclude costs, liquidity and delisted assets.")
