# Global Stock Pattern Discovery

A free, experimental stock-market research dashboard built with Streamlit.

## Features
- Candlestick pattern scanner (bullish engulfing, hammer, breakout, volume surge)
- Forward historical event study for moves of **20% or more** over 5, 10, 20, 30, or 60 trading days
- Price charts, candidate ranking, and recent Yahoo Finance news headlines where available
- Free Yahoo Finance data via `yfinance` (unofficial; may be delayed, missing, or rate-limited)

**Important:** This is a research prototype, not an exhaustive worldwide stock scanner, a live trading feed, or an investment recommendation. The user supplies a watchlist of ticker symbols. Free data does not reliably cover every listed share, particularly illiquid AIM and small-cap names. Historical patterns are not predictive guarantees. The event study is descriptive and does not model trading costs, slippage, or delistings.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Free hosting
Deploy `app.py` on Streamlit Community Cloud by connecting this GitHub repository. Cloud deployment is separate from GitHub Actions and requires your approval.

## Research roadmap
1. Expand market coverage using exchange symbol lists and data-quality checks.
2. Build walk-forward testing, transaction-cost assumptions and delisting-aware data.
3. Add news feeds with timestamps and measure pre-move news catalysts without look-ahead bias.
4. Evaluate out-of-sample performance and false positives before interpreting rankings.

## Data and privacy
No broker connection, orders, paid API keys, or credentials required. Data is requested from third-party Yahoo Finance endpoints when scanning.
