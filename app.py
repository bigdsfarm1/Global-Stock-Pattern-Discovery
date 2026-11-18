import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from scanner import PATTERNS, add_signals, event_study, chart_shape_matches

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
    st.caption("The scanner automatically checks multiple upside targets — no target to choose.")

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
    st.session_state["selection"] = (symbol, period, horizon)
if "selection" not in st.session_state:
    st.stop()
symbol, period, horizon = st.session_state["selection"]
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
# Descriptive assessment, not a probability or trade recommendation.
recent = d.tail(20)
support = float(recent["Low"].min())
resistance = float(recent["High"].max())
ma20 = float(d["Close"].tail(20).mean())
vol_baseline = float(d["Volume"].iloc[-21:-1].mean()) if len(d) > 20 else 0
vol_ratio = float(d["Volume"].iloc[-1]) / vol_baseline if vol_baseline > 0 else 0
bullish = bool(active) and close > ma20 and vol_ratio >= 1.2
caution = close < ma20 and not active
assessment = "Favourable setup to investigate" if bullish else ("Caution" if caution else "Wait / mixed evidence")
st.subheader("Current assessment")
with st.container(border=True):
    st.markdown("**" + assessment + "**")
    if bullish:
        st.write("A monitored candlestick pattern is present, price is above its 20-bar average and volume is elevated. This does not guarantee a rise.")
    elif caution:
        st.write("Price is below its 20-bar average and no monitored bullish pattern is active. Consider waiting for stronger evidence.")
    else:
        st.write("The available signals are mixed or incomplete. There is no clear statistical entry signal.")
    st.caption("Rule-based research summary; not a validated predictive score.")
st.subheader("Price levels to watch")
a, b = st.columns(2)
a.metric("20-bar support (quote currency)", f"{support:,.5f}")
b.metric("20-bar resistance (quote currency)", f"{resistance:,.5f}")
st.caption("Support and resistance are recent observed extremes, NOT recommended buy/sell prices. Prices may break through either level.")
st.subheader("Whole-chart pattern discovery")
st.caption("Compares the shape of the most recent price movement against past multi-candle chart shapes, rather than checking individual candles.")
shape_window = st.select_slider("Chart shape length (price bars)", options=[15, 30, 60, 90], value=30)
matches = chart_shape_matches(d, window=shape_window, horizon=horizon, top_n=8)
if matches:
    sample = pd.DataFrame(matches)
    positive = int((sample["end_return"] > 0).sum())
    st.write(f"Found {len(matches)} separated historical chart shapes. {positive} finished higher after {horizon} bars; {len(matches)-positive} finished lower.")
    st.caption("Closest historical shapes are NOT forecasts. This is exploratory matching, not independently backtested or statistically calibrated.")
    view = pd.DataFrame([{
        "Past pattern ended": m["date"],
        "Shape difference (lower = closer)": round(m["distance"], 2),
        "Later closing change": f'{m["end_return"]:+.1%}',
        "Largest later rise": f'{m["best_rise"]:+.1%}',
        "Largest later fall": f'{m["worst_fall"]:+.1%}',
    } for m in matches])
    st.dataframe(view, hide_index=True, use_container_width=True)
else:
    st.info("Not enough separated historical chart shapes for this window. Try more historical data or a shorter chart shape.")
st.subheader("Individual candle and breakout signals")
st.caption("Secondary signals; the whole-chart matching above is a separate analysis.")
st.subheader("Opportunity range from historical patterns")
st.caption(f"Automatically checks rises of 5%, 10%, 20%, 30%, 50% and 100% within {horizon} future price bars. A hit means the future HIGH touched that level, not that a trade would have earned it.")
targets = [5, 10, 20, 30, 50, 100]
for p in PATTERNS:
    with st.expander(f"{'🟢 ' if p in active else ''}{p}" + (" — active now" if p in active else " — historical reference"), expanded=p in active):
        results = []
        for target in targets:
            stats = event_study(d, p, horizon, target / 100)
            results.append({"Rise": f"+{target}%", "Historical hit rate": f'{stats["hit_rate"]:.1%}' if pd.notna(stats["hit_rate"]) else "N/A", "Occurrences": stats["signals"]})
        st.dataframe(pd.DataFrame(results), hide_index=True, use_container_width=True)
        st.caption("These are overlapping historical observations, not independent probabilities or future price targets. Larger rises are generally less common.")
st.subheader("Price chart")
fig = go.Figure(data=[go.Candlestick(x=d.index, open=d.Open, high=d.High, low=d.Low, close=d.Close)])
fig.add_hline(y=support, line_dash="dot", annotation_text="Recent support")
fig.add_hline(y=resistance, line_dash="dot", annotation_text="Recent resistance")
fig.update_layout(height=420, xaxis_rangeslider_visible=False, margin=dict(l=5,r=5,t=20,b=10))
st.plotly_chart(fig, use_container_width=True)
st.subheader("Smart Money Tracker")
with st.container(border=True):
    if symbol.endswith("-USD"):
        st.write("Crypto: large wallet transfers may be observable, but they do not prove an institution bought or sold. Verified institutional transaction data is not connected yet.")
    else:
        st.write("Institutional ownership changes are not available from the current price-data feed.")
        st.write("For US securities, SEC 13F filings report holdings quarterly and are typically delayed up to 45 days after quarter end. Changes in reported holdings do not reveal exact trade dates.")
        st.link_button("Explore SEC institutional filings", "https://www.sec.gov/edgar/search/")
        st.write("For UK securities, check company RNS/TR-1 major-shareholding announcements. Filings may reflect threshold crossings rather than every trade.")
    st.caption("No institution-level buy/sell figures are shown until a verifiable filings feed is integrated.")
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
