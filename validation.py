"""Historical holdout evaluation of a fixed technical rule, not a trading simulation."""
import numpy as np
import pandas as pd
from scanner import add_signals, recognise_chart_structure


def technical_label(history):
    """Only uses price history through the evaluation date."""
    if len(history) < 55:
        return "WAIT"
    d = history
    close = float(d["Close"].iloc[-1])
    ma20 = float(d["Close"].tail(20).mean())
    ma50 = float(d["Close"].tail(50).mean())
    volbase = float(d["Volume"].iloc[-21:-1].mean())
    volratio = float(d["Volume"].iloc[-1]) / volbase if volbase > 0 else 0
    breakout = bool(d["20-day breakout"].tail(3).any())
    direction = recognise_chart_structure(d.tail(30)).get("direction", "unknown")
    positive = sum([close > ma20, close > ma50, breakout, volratio >= 1.2 and close > ma20, direction == "bullish"])
    negative = sum([close < ma20, close < ma50, direction == "bearish"])
    if positive >= 4 and negative <= 1:
        return "BUY"
    if negative >= 3:
        return "SELL"
    return "WAIT"


def holdout_test(prices, horizon=30, test_fraction=0.30):
    """Chronological final 30% holdout; non-overlapping decision dates.

    Return measures close-to-close forward price changes, not executable profits.
    Does not include costs, slippage, dividends, shorts, or optimised thresholds.
    """
    d = add_signals(prices)
    n = len(d)
    split = max(60, int(n * (1 - test_fraction)))
    if n < 180 or split + horizon >= n:
        return {"status": "insufficient", "reason": "Need at least 180 daily observations and a complete holdout evaluation window."}
    rows = []
    # Test decision dates are spaced by horizon to avoid overlapping outcomes.
    for i in range(split, n - horizon, horizon):
        label = technical_label(d.iloc[:i+1])
        entry = float(d["Close"].iloc[i])
        exit_price = float(d["Close"].iloc[i+horizon])
        if entry <= 0 or not np.isfinite([entry, exit_price]).all():
            continue
        rows.append({"date": str(d.index[i].date()), "signal": label,
                     "forward_return": exit_price / entry - 1})
    if not rows:
        return {"status": "insufficient", "reason": "No complete test observations."}
    frame = pd.DataFrame(rows)
    results = {}
    for label in ["BUY", "WAIT", "SELL"]:
        subset = frame[frame.signal == label]
        results[label] = {"count": int(len(subset)),
                          "up_fraction": float((subset.forward_return > 0).mean()) if len(subset) else None,
                          "mean_return": float(subset.forward_return.mean()) if len(subset) else None}
    return {"status": "ok", "split_date": str(d.index[split].date()),
            "test_end": str(d.index[-1].date()), "observations": len(frame),
            "results": results, "baseline_up": float((frame.forward_return > 0).mean()),
            "baseline_mean": float(frame.forward_return.mean()),
            "rows": rows}
