import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
import scanner
from validation import holdout_test

PATTERNS = scanner.PATTERNS
add_signals = scanner.add_signals
event_study = scanner.event_study
chart_shape_matches = scanner.chart_shape_matches
recognise_chart_structure = getattr(scanner, "recognise_chart_structure", None)
if recognise_chart_structure is None:
    def recognise_chart_structure(prices):
        return {"name": "Chart structure unavailable", "explanation": "The chart-pattern module is updating; retry shortly.", "direction": "unknown"}

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
    horizon = st.selectbox("Evaluation window (days)", [5, 10, 20, 30, 60], index=3)
    st.caption("Daily charts: stock-market days exclude weekends and holidays; crypto days include weekends. Multiple upside targets are checked automatically.")

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
# Rule-based technical action labels, not personal investment instructions.
recent = d.tail(20)
support = float(recent["Low"].min())
resistance = float(recent["High"].max())
ma20 = float(d["Close"].tail(20).mean())
ma50 = float(d["Close"].tail(50).mean())
vol_baseline = float(d["Volume"].iloc[-21:-1].mean()) if len(d) > 20 else 0
vol_ratio = float(d["Volume"].iloc[-1]) / vol_baseline if vol_baseline > 0 else 0
recent_breakout = bool(d["20-day breakout"].tail(3).any())
shape = recognise_chart_structure(d.tail(30))
shape_direction = shape.get("direction", "unknown")
# Historical matches support context, but are too few and selected to be probabilities.
assessment_matches = chart_shape_matches(d, window=30, horizon=horizon, top_n=8)
match_count = len(assessment_matches)
up_count = sum(m["end_return"] > 0 for m in assessment_matches)
down_count = sum(m["end_return"] < 0 for m in assessment_matches)
historical_bias = ("up" if match_count >= 5 and up_count / match_count >= 0.7 else
                   "down" if match_count >= 5 and down_count / match_count >= 0.7 else "mixed")
positive_signals = [close > ma20, close > ma50, recent_breakout, vol_ratio >= 1.2 and close > ma20, shape_direction == "bullish"]
negative_signals = [close < ma20, close < ma50, shape_direction == "bearish"]
if sum(positive_signals) >= 4 and sum(negative_signals) <= 1 and historical_bias != "down":
    action = "BUY setup — investigate"
    explanation = "Several technical signals favour an upward move. Check valuation, news and risk before considering any purchase."
elif sum(negative_signals) >= 3 and historical_bias != "up":
    action = "SELL / avoid risk signal"
    explanation = "The technical picture is weak. This may justify reviewing exposure, but does not mean every existing holder should sell."
else:
    action = "HOLD / wait"
    explanation = "The technical evidence is mixed or insufficient for a clear directional setup. HOLD is a neutral research label, not a recommendation to retain a position."
st.subheader("Current assessment — Buy / Hold / Sell")
with st.container(border=True):
    st.markdown("### " + action)
    st.write(explanation)
    st.write(f"**Technical checks:** {sum(positive_signals)} of 5 bullish; {sum(negative_signals)} of 3 bearish.")
    if match_count:
        st.write(f"**Similar chart shapes:** {up_count} of {match_count} finished higher and {down_count} finished lower after {horizon} days.")
    else:
        st.write("**Similar chart shapes:** insufficient history for comparison.")
    validation = holdout_test(prices, horizon=horizon)
    if validation["status"] == "ok":
        current_label = "BUY" if action.startswith("BUY") else ("SELL" if action.startswith("SELL") else "WAIT")
        v = validation["results"][current_label]
        if v["count"] >= 20:
            st.caption(f'Historical evidence: {v["count"]} independent later-period examples; {v["up_fraction"]:.0%} finished higher. This is exploratory, not a reliable prediction.')
        else:
            st.caption("Pattern reliability: Insufficient evidence — too few independent historical examples to estimate reliable odds.")
    else:
        st.caption("Pattern reliability: Insufficient historical data for a meaningful test.")
    st.caption("Based on available delayed daily prices and patterns only. News, fundamentals, institutional filings, your entry price and personal risk tolerance are NOT included in this verdict.")
st.subheader("Price levels to watch")
a, b = st.columns(2)
a.metric("20-bar support (quote currency)", f"{support:,.5f}")
b.metric("20-bar resistance (quote currency)", f"{resistance:,.5f}")
st.caption("Support and resistance are recent observed extremes, NOT recommended buy/sell prices. Prices may break through either level.")
st.subheader("🔍 Pattern discovery — explained")
st.write("We compare the shape of today's chart with older sections of this same investment's chart.")
shape_window = st.select_slider("Pattern length (days)", options=[15, 30, 60, 90], value=30)
matches = chart_shape_matches(d, window=shape_window, horizon=horizon, top_n=8)

def describe_shape(prices):
    """Plain-language description of the path, not a textbook-pattern diagnosis."""
    start_price = float(prices.iloc[0])
    last_price = float(prices.iloc[-1])
    change = last_price / start_price - 1 if start_price else 0
    midpoint = float(prices.iloc[len(prices)//2])
    first_leg = midpoint / start_price - 1 if start_price else 0
    second_leg = last_price / midpoint - 1 if midpoint else 0
    if first_leg < -0.05 and second_leg > 0.05:
        return "Drop followed by a recovery"
    if first_leg > 0.05 and second_leg < -0.05:
        return "Rise followed by a pullback"
    if change > 0.08:
        return "Overall upward trend"
    if change < -0.08:
        return "Overall downward trend"
    return "Sideways or mixed movement"

current_structure = recognise_chart_structure(d.iloc[-shape_window:])
st.markdown("**Current chart formation: " + current_structure["name"] + "**")
st.write(current_structure["explanation"])
st.caption("Preliminary shape classification only. Not a confirmed textbook formation.")
st.markdown("**Pattern conclusion**")
if len(matches) >= 5:
    up_count = sum(m["end_return"] > 0 for m in matches)
    down_count = sum(m["end_return"] < 0 for m in matches)
    up_rate = up_count / len(matches)
    if up_rate >= 0.7:
        verdict = "Historically more often upward"
    elif up_rate <= 0.3:
        verdict = "Historically more often downward"
    else:
        verdict = "Mixed historical outcomes"
    st.write(f"**{verdict}** — {up_count} of {len(matches)} similar historical examples finished higher after {horizon} days ({up_rate:.0%}).")
    st.warning("Evidence strength: LOW. These are a few selected nearest matches from the same asset, not independently tested odds. Even a high percentage here cannot justify a high-confidence forecast.")
elif matches:
    st.write("**Insufficient evidence** — too few separate historical matches to assess direction reliably.")
else:
    st.write("**No conclusion** — not enough matching historical examples.")
selected_match = None
if matches:
    st.write(f"**{len(matches)} past chart shapes found** that resemble the latest {shape_window} days.")
    st.caption("These are similarities, not confirmed trading signals. Select a historical example to see the exact dates and highlighted chart.")
    match_labels = []
    for i, m in enumerate(matches):
        start_date = d.index[m["end"]-shape_window].strftime("%d %b %Y")
        end_date = d.index[m["end"]-1].strftime("%d %b %Y")
        match_labels.append(f"Match {i+1}: {start_date} – {end_date}")
    chosen_match = st.selectbox("Choose a matching pattern", range(len(matches)), format_func=lambda i: match_labels[i])
    selected_match = matches[chosen_match]
    past_end = selected_match["end"]
    past_start = past_end-shape_window
    historical = d.iloc[past_start:past_end]
    current = d.iloc[-shape_window:]
    st.markdown("**What pattern was found?**")
    past_structure = recognise_chart_structure(historical)
    st.write("**Historical formation:** " + past_structure["name"] + ". " + past_structure["explanation"])
    st.write("**General movement:** " + describe_shape(historical["Close"]) + ". The scanner found a similar overall price path in the latest chart.")
    left, right = st.columns(2)
    left.metric("Pattern started", historical.index[0].strftime("%d %b %Y"))
    right.metric("Pattern finished", historical.index[-1].strftime("%d %b %Y"))
    st.write(f'**What happened next?** Over the following {horizon} days, the closing price changed **{selected_match["end_return"]:+.1%}**. The highest price reached was **{selected_match["best_rise"]:+.1%}** above the pattern-end close, while the lowest was **{selected_match["worst_fall"]:+.1%}** relative to that close.')
    st.markdown("**See the two shapes side by side**")
    comparison = go.Figure()
    def relative_path(values):
        return (values / float(values.iloc[0]) - 1) * 100
    comparison.add_trace(go.Scatter(x=list(range(1,shape_window+1)), y=relative_path(historical["Close"]), name="Historical pattern", mode="lines"))
    comparison.add_trace(go.Scatter(x=list(range(1,shape_window+1)), y=relative_path(current["Close"]), name="Current chart", mode="lines"))
    comparison.update_layout(height=300, xaxis_title="Day of pattern", yaxis_title="Change from pattern start (%)", margin=dict(l=5,r=5,t=20,b=10))
    st.plotly_chart(comparison, use_container_width=True)
    st.caption("Both shapes are rebased to 0% at their starting day. Similarity is calculated using normalised daily closing-price paths; chart lines do not mean the prices were equal.")
    st.markdown("**Historical candlestick chart — highlighted pattern**")
    history_context = d.iloc[max(0,past_start-10):min(len(d),past_end+horizon+5)]
    history_fig = go.Figure(data=[go.Candlestick(x=history_context.index,open=history_context.Open,high=history_context.High,low=history_context.Low,close=history_context.Close,name="Historical prices")])
    history_fig.add_vrect(x0=historical.index[0], x1=historical.index[-1], fillcolor="RoyalBlue", opacity=0.18, line_width=0, annotation_text="Matched pattern", annotation_position="top left")
    history_fig.add_vline(x=historical.index[-1], line_dash="dash", annotation_text="Pattern finished")
    history_fig.update_layout(height=350, xaxis_rangeslider_visible=False, margin=dict(l=5,r=5,t=30,b=10))
    st.plotly_chart(history_fig, use_container_width=True)
    with st.expander("View all matching dates and results"):
        view = pd.DataFrame([{
            "Pattern start": d.index[m["end"]-shape_window].strftime("%d %b %Y"),
            "Pattern finish": d.index[m["end"]-1].strftime("%d %b %Y"),
            "Later closing change": f'{m["end_return"]:+.1%}',
            "Largest later rise": f'{m["best_rise"]:+.1%}',
            "Largest later fall": f'{m["worst_fall"]:+.1%}',
        } for m in matches])
        st.dataframe(view, hide_index=True, use_container_width=True)
else:
    st.info("Not enough separated historical patterns to compare. Try a longer history or shorter pattern length.")
st.caption("Pattern dates refer to the historical example. The current pattern is still developing. Matching historical shapes does not establish that a future move will repeat.")
st.subheader("Individual candle and breakout signals")
st.caption("Secondary signals; the whole-chart matching above is a separate analysis.")
st.subheader("Opportunity range from historical patterns")
st.caption(f"Automatically checks rises of 5%, 10%, 20%, 30%, 50% and 100% within {horizon} future days. A hit means the future HIGH touched that level, not that a trade would have earned it.")
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
fig.add_vrect(x0=d.index[-shape_window], x1=d.index[-1], fillcolor="RoyalBlue", opacity=0.12, line_width=0, annotation_text=current_structure["name"], annotation_position="top left")
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
