"""Candlestick pattern research helpers. No trade recommendations."""
import numpy as np
import pandas as pd

PATTERNS = ["Bullish engulfing", "Hammer", "20-day breakout", "Volume surge"]

def add_signals(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy().sort_index()
    for name in ("Open", "High", "Low", "Close", "Volume"):
        d[name] = pd.to_numeric(d[name], errors="coerce")
    o, h, l, c, v = (d[x] for x in ("Open", "High", "Low", "Close", "Volume"))
    body = (c - o).abs()
    span = (h - l).replace(0, np.nan)
    lower = pd.concat([o, c], axis=1).min(axis=1) - l
    upper = h - pd.concat([o, c], axis=1).max(axis=1)
    d["Bullish engulfing"] = (c > o) & (c.shift(1) < o.shift(1)) & (o <= c.shift(1)) & (c >= o.shift(1))
    d["Hammer"] = (lower >= 2 * body) & (upper <= body) & (body / span >= 0.05)
    d["20-day breakout"] = c > h.shift(1).rolling(20, min_periods=20).max()
    d["Volume surge"] = v > 2 * v.shift(1).rolling(20, min_periods=20).mean()
    for pattern in PATTERNS:
        d[pattern] = d[pattern].fillna(False).astype(bool)
    return d

def event_study(d: pd.DataFrame, pattern: str, horizon: int, threshold: float = 0.20) -> dict:
    """Non-overlap not enforced; forward maximum HIGH measures whether target was touched."""
    future_highs = pd.concat([d["High"].shift(-i) for i in range(1, horizon + 1)], axis=1)
    future_max = future_highs.max(axis=1)
    complete = d["High"].shift(-horizon).notna()
    mask = d[pattern] & complete & d["Close"].gt(0)
    gains = future_max[mask] / d.loc[mask, "Close"] - 1
    count = int(len(gains))
    return {
        "signals": count,
        "hit_rate": float((gains >= threshold).mean()) if count else np.nan,
        "median_max_gain": float(gains.median()) if count else np.nan,
    }
