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


def chart_shape_matches(d: pd.DataFrame, window: int = 30, horizon: int = 30, top_n: int = 8) -> list:
    """Compare entire normalised closing-price paths, excluding future-leaking matches.

    Uses shape similarity only, not predictive modelling. Historical windows must
    have a complete future horizon and cannot overlap the current window.
    """
    close = pd.to_numeric(d["Close"], errors="coerce").to_numpy(dtype=float)
    high = pd.to_numeric(d["High"], errors="coerce").to_numpy(dtype=float)
    low = pd.to_numeric(d["Low"], errors="coerce").to_numpy(dtype=float)
    n = len(close)
    if n < window * 2 + horizon + 1:
        return []
    def normalise(x):
        if not np.isfinite(x).all() or (x <= 0).any():
            return None
        y = np.log(x / x[0])
        scale = np.std(np.diff(y))
        return y / max(scale, 0.002)
    current = normalise(close[-window:])
    if current is None:
        return []
    candidates = []
    # Last historical match must end before the present window begins.
    for end in range(window, n - window - horizon + 1):
        past = normalise(close[end-window:end])
        if past is None:
            continue
        distance = float(np.sqrt(np.mean((current - past) ** 2)))
        entry = close[end-1]
        future_hi = high[end:end+horizon]
        future_lo = low[end:end+horizon]
        if not np.isfinite(future_hi).all() or not np.isfinite(future_lo).all() or entry <= 0:
            continue
        candidates.append({
            "end": end, "distance": distance,
            "best_rise": float(np.max(future_hi) / entry - 1),
            "worst_fall": float(np.min(future_lo) / entry - 1),
            "end_return": float(close[end+horizon-1] / entry - 1),
        })
    candidates.sort(key=lambda r: r["distance"])
    matches = []
    for item in candidates:
        if all(abs(item["end"] - old["end"]) >= window + horizon for old in matches):
            item["date"] = str(d.index[item["end"] - 1].date())
            matches.append(item)
            if len(matches) >= top_n:
                break
    return matches
