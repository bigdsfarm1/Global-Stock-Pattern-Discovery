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
st.caption("Explore automatic pattern discoveries or analyse an individual investment. Free historical research; not trading advice.")

page = st.radio("Dashboard", ["Pattern opportunities", "Stock analysis"], horizontal=True, key="app_page")
st.caption("Pattern opportunities discovers matches across a watchlist. Stock analysis has its own separate search.")

@st.cache_data(ttl=3600, show_spinner=False)
def prices_for(ticker, history):
    d = yf.Ticker(ticker).history(period=history, auto_adjust=True)
    return d[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Open", "High", "Low", "Close"]) if not d.empty else d

@st.cache_data(ttl=45, show_spinner=False)
def recent_market_quote(ticker):
    """Latest available intraday observation, including extended hours when provided."""
    data = yf.Ticker(ticker).history(period="5d", interval="1m", prepost=True, auto_adjust=False)
    if data.empty or "Close" not in data:
        return None
    valid = data["Close"].dropna()
    if valid.empty:
        return None
    last = valid.index[-1]
    return {"price": float(valid.iloc[-1]), "timestamp": last, "currency": "quote currency"}


@st.cache_data(ttl=3600, show_spinner=False)
def news_for(ticker):
    try:
        return yf.Ticker(ticker).news or []
    except Exception:
        return []

if page == "Pattern opportunities":
    st.header("Pattern opportunities dashboard")
    st.write("Discover historical chart-shape matches across markets, or scan your own list of tickers.")
    st.write("Scan a starter watchlist for stocks whose **current chart shape** closely resembles earlier periods in their own history.")
    st.caption("Starter watchlist only, not every share worldwide. Free data can be delayed or incomplete. Results are research leads, not verified odds.")
    scan_universe = {
        "US shares": ["AAPL", "MSFT", "NVDA", "TSLA", "AMD", "PLTR"],
        "UK shares": ["BARC.L", "RR.L", "SHEL.L", "LLOY.L", "VOD.L", "BP.L"],
        "Crypto": ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD"],
    }
    scan_market = st.selectbox("Markets to scan", ["All starter markets", *scan_universe], key="discovery_market")
    custom_tickers = st.text_input(
        "Search specific shares or crypto (optional)",
        placeholder="e.g. FORG.L, NVDA, BTC-USD",
        key="discovery_tickers",
        help="Enter exact Yahoo Finance ticker symbols separated by commas. Leave blank to scan the chosen market.",
    )

    scan_days = st.selectbox("Match chart length (days)", [15, 30, 60], index=1, key="discovery_days")
    scan_horizon = st.selectbox("Check outcomes after (days)", [10, 20, 30, 60], index=2, key="discovery_horizon")

    @st.cache_data(ttl=3600, show_spinner=False)
    def discover_patterns(symbols, days, future_days):
        found = []
        errors = []
        for ticker in symbols:
            try:
                hist = prices_for(ticker, "5y")
                if len(hist) < days * 2 + future_days + 30:
                    errors.append(ticker)
                    continue
                candidates = chart_shape_matches(hist, window=days, horizon=future_days, top_n=8)
                if len(candidates) < 4:
                    continue
                similarity = float(candidates[0]["distance"])
                ups = sum(m["end_return"] > 0 for m in candidates)
                gains20 = sum(m["best_rise"] >= 0.20 for m in candidates)
                avg_change = sum(m["end_return"] for m in candidates) / len(candidates)
                found.append({
                    "Ticker": ticker, "Match score": similarity,
                    "Past matches": len(candidates),
                    "Finished higher": ups,
                    "Reached +20%": gains20,
                    "Average end change": avg_change,
                    "Latest close": float(hist["Close"].iloc[-1]),
                    "Match dates": ", ".join(m["date"] for m in candidates[:4]),
                })
            except Exception:
                errors.append(ticker)
        return found, errors

    if st.button("Scan for opportunities", type="primary", use_container_width=True):
        if custom_tickers.strip():
            symbols = tuple(dict.fromkeys(t.strip().upper() for t in custom_tickers.split(",") if t.strip()))[:20]
        else:
            symbols = tuple(t for group in (scan_universe.values() if scan_market == "All starter markets" else [scan_universe[scan_market]]) for t in group)
        with st.spinner(f"Comparing historical charts for {len(symbols)} assets..."):
            st.session_state["discovery_results"] = discover_patterns(symbols, scan_days, scan_horizon)
            st.session_state["discovery_settings"] = (scan_market, scan_days, scan_horizon, custom_tickers.strip().upper())
    if "discovery_results" in st.session_state:
        found, errors = st.session_state["discovery_results"]
        settings = st.session_state.get("discovery_settings")
        if settings != (scan_market, scan_days, scan_horizon, custom_tickers.strip().upper()):
            st.info("Settings changed. Run the scan again to update the results.")
        elif not found:
            st.info("No qualifying chart matches found in this sample. Try another market or chart length.")
        else:
            st.caption("Sorted by historical shape similarity (lower distance = closer shape). This is not a ranking of expected returns.")
            ranked = sorted(found, key=lambda x: x["Match score"])
            for result in ranked:
                with st.expander(f'{result["Ticker"]} — {result["Past matches"]} similar past charts'):
                    st.write(f'**Similarity distance:** {result["Match score"]:.2f} (lower means more similar)')
                    st.write(f'**Finished higher:** {result["Finished higher"]} of {result["Past matches"]} after {scan_horizon} days')
                    st.write(f'**Reached +20% at any point:** {result["Reached +20%"]} of {result["Past matches"]}')
                    st.write(f'**Average end change:** {result["Average end change"]:+.1%}')
                    st.write(f'**Historical match dates:** {result["Match dates"]}')
                    st.caption("These matches were selected because they resemble today's chart. The outcome frequencies are in-sample, based on very few examples, and are NOT reliable probabilities.")
                    if st.button(f'Analyse {result["Ticker"]}', key="discovery_select_" + result["Ticker"]):
                        st.session_state["selection"] = (result["Ticker"], "5y", scan_horizon)
                        st.rerun()
        if errors:
            st.caption(f"Skipped {len(errors)} assets because data was missing or unavailable.")
    st.divider()

    st.stop()

st.header("Stock analysis")
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
st.caption("The daily closing price above is used for historical patterns and statistics.")
if st.button("Refresh latest price (including extended hours)", key="refresh_quote"):
    recent_market_quote.clear()
try:
    quote = recent_market_quote(symbol)
    if quote:
        st.metric("Latest available intraday price (quote currency)", f'{quote["price"]:,.5f}')
        st.caption(f'Last price observation: {quote["timestamp"]}. Includes pre-market/after-hours data where the exchange and Yahoo provide it. It may be delayed, stale or unavailable; not a guaranteed live executable quote.')
        st.caption(f'Change versus daily close: {(quote["price"] / close - 1):+.2%}. This is not necessarily the official session change.')
    else:
        st.info("No intraday quote available for this symbol. The last daily close is shown above.")
except Exception:
    st.info("Intraday or extended-hours data is temporarily unavailable. Daily analysis remains available.")

active = [p for p in PATTERNS if bool(d[p].iloc[-1])]
if active:
    st.success("Detected on the latest trading day: " + ", ".join(active))
else:
    st.info("No monitored pattern detected on the latest trading day. This is not a buy signal.")
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
# Balanced directional assessment: trend is primary; breakouts and volume add context.
# Avoid requiring rare events for every BUY and avoid treating absent bullish signals as bearish.
ma20_previous = float(d["Close"].iloc[-25:-5].mean()) if len(d) >= 25 else ma20
ma20_rising = ma20 > ma20_previous * 1.002
ma20_falling = ma20 < ma20_previous * 0.998
bullish_checks = {
    "Price above 20-day average": close > ma20 * 1.005,
    "Price above 50-day average": close > ma50 * 1.005,
    "Short-term average rising": ma20_rising,
    "Bullish chart structure": shape_direction == "bullish",
    "Recent breakout or strong upward volume": recent_breakout or (vol_ratio >= 1.2 and close > ma20),
}
bearish_checks = {
    "Price below 20-day average": close < ma20 * 0.995,
    "Price below 50-day average": close < ma50 * 0.995,
    "Short-term average falling": ma20_falling,
    "Bearish chart structure": shape_direction == "bearish",
    "Weak price despite high volume": vol_ratio >= 1.2 and close < ma20,
}
bullish_score = sum(bullish_checks.values())
bearish_score = sum(bearish_checks.values())
# Three aligned trend indicators are enough for a directional setup; mixed signals stay neutral.
if bullish_score >= 3 and bullish_score >= bearish_score + 2:
    action = "BUY setup — investigate"
    explanation = "Several independent trend checks are bullish. This is a research signal, not a recommendation to buy."
elif bearish_score >= 3 and bearish_score >= bullish_score + 2:
    action = "SELL / avoid risk signal"
    explanation = "Several trend checks are bearish. This is a risk warning, not a recommendation that every holder should sell."
else:
    action = "HOLD / wait"
    explanation = "Bullish and bearish evidence is mixed or too weak to justify a directional signal. HOLD means no clear setup."
positive_signals = list(bullish_checks.values())
negative_signals = list(bearish_checks.values())
st.subheader("Market trend")
trend_span = st.segmented_control("Trend period", options=["Short term (20 days)", "Medium term (50 days)", "Long term (200 days)"], default="Medium term (50 days)", key="trend_span")
trend_days = 20 if trend_span.startswith("Short") else (50 if trend_span.startswith("Medium") else 200)
if len(d) < trend_days + 10:
    st.info("Not enough price history to assess this trend period. Try a shorter period or download more history.")
else:
    series = d["Close"].astype(float)
    avg = series.rolling(trend_days).mean()
    now_avg = float(avg.iloc[-1])
    previous_avg = float(avg.iloc[-min(11, len(avg))])
    slope = (now_avg / previous_avg - 1) if previous_avg > 0 else 0
    gap = (close / now_avg - 1) if now_avg > 0 else 0
    if gap > 0.01 and slope > 0.005:
        trend_label = "🟢 UPWARD TREND"
        trend_text = "Price is above its moving average and the average is rising."
    elif gap < -0.01 and slope < -0.005:
        trend_label = "🔴 DOWNWARD TREND"
        trend_text = "Price is below its moving average and the average is falling."
    else:
        trend_label = "🟡 SIDEWAYS / UNCLEAR"
        trend_text = "Price and moving-average direction do not agree strongly enough to confirm a trend."
    st.markdown("### " + trend_label)
    st.write(trend_text)
    st.caption(f"{trend_days}-day moving average: {now_avg:,.5f} (quote currency). Price relative to average: {gap:+.1%}. Trend is descriptive, not a forecast.")
st.subheader("Current assessment — Buy / Hold / Sell")
with st.container(border=True):
    st.markdown("### " + action)
    st.write(explanation)
    st.write(f"**Technical checks:** {bullish_score} of 5 bullish; {bearish_score} of 5 bearish.")
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
a.metric("20-day support (quote currency)", f"{support:,.5f}")
b.metric("20-day resistance (quote currency)", f"{resistance:,.5f}")
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
st.subheader("Possible rise from today's price")
st.write(f"Starting from the latest available price of **{close:,.5f}** (quote currency), these are example higher price levels over the next **{horizon} days**.")
st.caption("The figures below are historical frequencies for this asset, NOT predicted chances or guaranteed targets. They use closing prices, not candlestick signals or intraday highs.")
targets = [5, 10, 20, 30, 50, 100]
# Use non-overlapping completed forward periods to reduce repeated counting.
past_closes = d["Close"].astype(float)
sample_indices = list(range(0, len(d) - horizon, horizon))
forward_returns = []
for i in sample_indices:
    entry = float(past_closes.iloc[i])
    later = float(past_closes.iloc[i + horizon])
    if entry > 0 and pd.notna(entry) and pd.notna(later):
        forward_returns.append(later / entry - 1)
sample_count = len(forward_returns)
rows = []
for target in targets:
    hits = sum(r >= target / 100 for r in forward_returns)
    rows.append({
        "Rise from current": f"+{target}%",
        "Price level": f"{close * (1 + target / 100):,.5f}",
        "Past periods ending at/above": f"{hits} of {sample_count}" if sample_count else "No data",
        "Historical frequency": f"{hits / sample_count:.0%}" if sample_count else "N/A",
    })
st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
if sample_count < 20:
    st.warning(f"Only {sample_count} non-overlapping historical periods are available. Too few to estimate dependable chances.")
else:
    st.caption(f"Based on {sample_count} non-overlapping {horizon}-day periods. Market conditions change, and this sample may not represent the future.")
if sample_count:
    st.write(f"**Historical average change after {horizon} days:** {sum(forward_returns) / sample_count:+.1%}. This is a descriptive average, not a forecast.")
st.caption("Example: a 20% historical frequency means that 20% of the sampled past periods ended at least that much higher. It does NOT mean a 20% probability of that happening next.")
st.subheader("Past candlestick examples")
st.write("Separately, explore historical candlestick signals and see what happened after them. These examples do not determine the rise statistics above.")
ordered_patterns = [p for p in PATTERNS if p in active] + [p for p in PATTERNS if p not in active]
for p in ordered_patterns:
    with st.expander(("🟢 Active: " if p in active else "Past examples: ") + p, expanded=p in active):
        sample_count = int(event_study(d, p, horizon, 0.05)["signals"])
        if not sample_count:
            st.write("No completed past examples found for this signal.")
        if sample_count:
            st.markdown("**See the actual past examples on a candlestick chart**")
            valid_events = [i for i in range(len(d) - horizon) if bool(d[p].iloc[i]) and float(d["Close"].iloc[i]) > 0]
            if valid_events:
                example_options = list(reversed(valid_events[-20:]))
                selected_event = st.selectbox(
                    "Choose a past signal date",
                    options=example_options,
                    format_func=lambda i: str(d.index[i].date()),
                    key="past_event_" + p.replace(" ", "_"),
                )
                before = max(0, selected_event - 25)
                after = min(len(d), selected_event + horizon + 1)
                section = d.iloc[before:after]
                historical_chart = go.Figure(data=[go.Candlestick(
                    x=section.index, open=section["Open"], high=section["High"],
                    low=section["Low"], close=section["Close"], name="Daily prices"
                )])
                historical_chart.add_vline(x=d.index[selected_event], line_color="orange", line_width=2, line_dash="dash")
                historical_chart.add_vrect(x0=d.index[selected_event], x1=d.index[after - 1],
                                           fillcolor="LightGreen", opacity=0.12, line_width=0)
                historical_chart.update_layout(height=360, xaxis_rangeslider_visible=False,
                                               margin=dict(l=5, r=5, t=25, b=10),
                                               title="Past signal (orange line) and what happened next (shaded)")
                st.plotly_chart(historical_chart, use_container_width=True, key="historical_chart_" + p.replace(" ", "_"))
                start_close = float(d["Close"].iloc[selected_event])
                next_prices = d.iloc[selected_event + 1:selected_event + horizon + 1]
                max_gain = float(next_prices["High"].max() / start_close - 1)
                final_change = float(next_prices["Close"].iloc[-1] / start_close - 1)
                st.write(f"**This example:** highest rise in the following {horizon} days: {max_gain:+.1%}; change at the end: {final_change:+.1%}.")
                st.caption("Showing up to 20 most recent completed examples. The orange line marks the historical signal; the shaded area is later price movement. This is hindsight, not a forecast.")

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
