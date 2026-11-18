"""Scheduled Telegram price and candlestick alerts. Never log credentials."""
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd
import yfinance as yf

from scanner import PATTERNS, add_signals

STATE_PATH = Path("alert_state.json")
CONFIG_PATH = Path("alerts.json")


def send_message(token, chat_id, message):
    payload = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode()
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.status == 200


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def check_alerts(config, state, fetcher=None):
    """Return only newly triggered alerts; persist dedupe state separately."""
    if fetcher is None:
        fetcher = lambda ticker: yf.Ticker(ticker).history(period="3mo", auto_adjust=True)
    messages = []
    for item in config.get("watchlist", []):
        ticker = str(item.get("ticker", "")).strip().upper()
        if not ticker:
            continue
        try:
            history = fetcher(ticker)
            if history.empty or len(history) < 25:
                print(f"No sufficient history for {ticker}")
                continue
            data = add_signals(history)
            latest = data.iloc[-1]
            close = float(latest["Close"])
            date = str(data.index[-1].date())
            # Intraday price for thresholds; daily candles for confirmed patterns.
            try:
                intraday = yf.Ticker(ticker).history(period="1d", interval="1m", prepost=True)
                price = float(intraday["Close"].dropna().iloc[-1]) if not intraday.empty else close
            except Exception:
                price = close
            for threshold_type, target, triggered in (
                ("above", item.get("above"), lambda v: price >= v),
                ("below", item.get("below"), lambda v: price <= v),
            ):
                if target is None:
                    continue
                target = float(target)
                key = f"{ticker}:{threshold_type}:{target}"
                is_triggered = triggered(target)
                if is_triggered and not state.get(key, False):
                    messages.append(f"Price alert: {ticker} is {price:,.5f}, {threshold_type} {target:,.5f}. Yahoo quote may be delayed.")
                state[key] = is_triggered
            if item.get("patterns", True):
                for pattern in PATTERNS:
                    if not bool(latest[pattern]):
                        continue
                    key = f"{ticker}:pattern:{pattern}"
                    if state.get(key) != date:
                        messages.append(f"Candlestick alert: {ticker} — {pattern} detected on {date} daily candle. Research signal only.")
                        state[key] = date
        except Exception as exc:
            print(f"Unable to check {ticker}: {type(exc).__name__}")
    return messages, state


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID GitHub Actions secrets.")
    config = load_json(CONFIG_PATH, {"watchlist": []})
    state = load_json(STATE_PATH, {})
    messages, state = check_alerts(config, state)
    for message in messages:
        send_message(token, chat_id, message)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Sent {len(messages)} new Telegram alerts.")


if __name__ == "__main__":
    main()
