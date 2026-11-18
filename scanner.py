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
    # A single close has no shape: compare the full OHLC candle instead.\n    def candle_features(i):\n        o, h, l, c = [float(d[k].iloc[i]) for k in ("Open", "High", "Low", "Close")]\n        span = h - l\n        return np.array([(c-o)/span, (min(o,c)-l)/span, (h-max(o,c))/span]) if span > 0 else np.zeros(3)\n    current = candle_features(-1) if window == 1 else normalise(close[-window:])
    if current is None:
        return []
    candidates = []
    # Last historical match must end before the present window begins.
    for end in range(window, n - window - horizon + 1):
        past = candle_features(end-1) if window == 1 else normalise(close[end-window:end])
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


def recognise_chart_structure(prices: pd.DataFrame) -> dict:
    """Exploratory geometric labels, not validated technical-pattern recognition."""
    import numpy as np
    c = prices["Close"].to_numpy(dtype=float)
    if len(c) < 15 or not np.isfinite(c).all() or np.min(c) <= 0:
        return {"name": "Unclassified chart shape", "explanation": "Not enough valid price history.", "direction": "unknown"}
    n = len(c)
    # Smooth noisy prices before finding broad turning points.
    smooth = pd.Series(c).rolling(max(3, n // 12), min_periods=1, center=True).mean().to_numpy()
    thirds = np.array_split(smooth, 3)
    first, middle, last = [float(np.mean(t)) for t in thirds]
    spread = (float(np.max(smooth)) - float(np.min(smooth))) / float(np.mean(smooth))
    change = c[-1] / c[0] - 1
    lows = []
    highs = []
    for i in range(2, n - 2):
        if smooth[i] <= min(smooth[i-2:i]) and smooth[i] <= min(smooth[i+1:i+3]):
            lows.append(i)
        if smooth[i] >= max(smooth[i-2:i]) and smooth[i] >= max(smooth[i+1:i+3]):
            highs.append(i)
    for j, a in enumerate(lows):
        for b in lows[j+1:]:
            if b-a < max(5, n//5):
                continue
            if abs(smooth[a] / smooth[b] - 1) < 0.045 and np.max(smooth[a:b+1]) > max(smooth[a], smooth[b])*1.055:
                return {"name":"Possible double bottom (W shape)","explanation":"Two separated lows at similar levels with a rebound between them. Confirmation would require a subsequent breakout.","direction":"bullish"}
    for j, a in enumerate(highs):
        for b in highs[j+1:]:
            if b-a < max(5, n//5):
                continue
            if abs(smooth[a] / smooth[b] - 1) < 0.045 and np.min(smooth[a:b+1]) < min(smooth[a], smooth[b])*0.945:
                return {"name":"Possible double top (M shape)","explanation":"Two separated highs at similar levels with a pullback between them. This can indicate resistance.","direction":"bearish"}
    if first > middle * 1.04 and last > middle * 1.04:
        return {"name":"Rounded recovery / possible base","explanation":"Prices fell into the middle of the period and subsequently recovered.","direction":"bullish"}
    if first < middle * 0.96 and last < middle * 0.96:
        return {"name":"Rounded peak / possible reversal","explanation":"Prices rose into the middle of the period and subsequently retreated.","direction":"bearish"}
    if spread < 0.07:
        return {"name":"Sideways consolidation","explanation":"Prices remained in a relatively narrow range, with no clear breakout yet.","direction":"neutral"}
    if change > 0.10:
        return {"name":"Upward trend","explanation":"Prices generally moved higher across the selected period.","direction":"bullish"}
    if change < -0.10:
        return {"name":"Downward trend","explanation":"Prices generally moved lower across the selected period.","direction":"bearish"}
    return {"name":"Mixed / irregular chart shape","explanation":"The price path does not clearly match the basic geometric structures currently checked.","direction":"neutral"}
