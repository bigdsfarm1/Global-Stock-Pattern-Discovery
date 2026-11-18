"""Historical whole-chart analog discovery; exploratory, not predictive validation."""
import numpy as np

WINDOWS = (1, 3, 5, 10, 20, 40)
HORIZON = 10

def discover_patterns_for_window(close, window, threshold=0.10, ohlc=None):
    """Evaluate exactly one window, using only earlier fully observed analog outcomes."""
    import numpy as np
    values = np.asarray(close, dtype=float)
    n = len(values)
    empty = {"pattern_window":window, "pattern_matches":0, "pattern_similarity":None,
             "pattern_historical_hit_pct":None, "pattern_median_forward_pct":None,
             "pattern_target_pct":round(threshold*100)}
    if n < 2*window + HORIZON + 10 or not np.isfinite(values).all() or np.any(values <= 0):
        return empty
    candles = np.asarray(ohlc, dtype=float) if ohlc is not None else None
    if window == 1 and (candles is None or candles.shape != (n, 4)):
        return empty
    def shape(end):
        if window == 1:
            op, hi, lo, cl = candles[end-1]
            span = max(hi-lo, 1e-12)
            return np.array([(cl-op)/span, (min(op,cl)-lo)/span,
                             (hi-max(op,cl))/span])
        segment = np.log(values[end-window:end]/values[end-window])
        return segment - np.linspace(0,1,window)*segment[-1]*0.25
    current = shape(n)
    candidates = []
    for end in range(window, n-HORIZON+1):
        past = shape(end)
        distance = float(np.sqrt(np.mean((current-past)**2)))
        outcome = float(values[end+HORIZON-1]/values[end-1]-1)
        candidates.append((distance,end,outcome))
    candidates.sort()
    matches = []
    for item in candidates:
        if all(abs(item[1]-m[1]) >= max(window,HORIZON) for m in matches):
            matches.append(item)
        if len(matches) == 5:
            break
    if len(matches) < 3:
        return empty
    examples = [{"end_index": int(x[1]), "return_pct": round(x[2]*100, 2),
                 "similarity_pct": round(float(np.exp(-x[0]*8)*100), 1)}
                for x in matches]
    return {"examples": examples, "positive_count": sum(x[2]>0 for x in matches),
            "negative_count": sum(x[2]<0 for x in matches),
            "unchanged_count": sum(x[2]==0 for x in matches),
            "best_return_pct": round(max(x[2] for x in matches)*100,2),
            "worst_return_pct": round(min(x[2] for x in matches)*100,2),
            "pattern_window":window, "pattern_matches":len(matches),
            "pattern_similarity":round(float(np.exp(-np.mean([x[0] for x in matches])*8)*100),1),
            "pattern_historical_hit_pct":round(100*sum(x[2]>=threshold for x in matches)/len(matches),1),
            "pattern_median_forward_pct":round(float(np.median([x[2] for x in matches])*100),2),
            "pattern_target_pct":round(threshold*100)}

def discover_patterns(close, threshold=0.10, ohlc=None):
    """Compare today's entire normalized price path with prior paths in the same asset.

    Historical outcomes are measured only AFTER each historical pattern ended.
    The current pattern's future is never used. Non-overlapping analogs reduce
    duplicates, but these are in-sample analogs, not out-of-sample predictions.
    """
    values = np.asarray(close, dtype=float)
    values = values[np.isfinite(values) & (values > 0)]
    n = len(values)
    best = None
    candles = None
    if ohlc is not None:
        candles = np.asarray(ohlc, dtype=float)
        if candles.shape != (n, 4):
            candles = None
    def candle_shape(index):
        op, hi, lo, cl = candles[index]
        span = max(hi - lo, 1e-12)
        return np.array([(cl - op) / span, (min(op, cl) - lo) / span,
                         (hi - max(op, cl)) / span])
    for window in WINDOWS:
        if n < 2 * window + HORIZON + 10:
            continue
        if window == 1:
            if candles is None:
                continue  # A single closing price has no shape; use OHLC candles.
            current = candle_shape(-1)
        else:
            current = np.log(values[-window:] / values[-window])
            current = current - np.linspace(0, 1, window) * current[-1] * 0.25
        candidates = []
        # End is exclusive; future outcomes must be fully observed.
        for end in range(window, n - HORIZON + 1):
            if window == 1:
                past = candle_shape(end - 1)
            else:
                past = np.log(values[end-window:end] / values[end-window])
                past = past - np.linspace(0, 1, window) * past[-1] * 0.25
            distance = float(np.sqrt(np.mean((current - past) ** 2)))
            future_return = float(values[end + HORIZON - 1] / values[end - 1] - 1)
            candidates.append((distance, end, future_return))
        candidates.sort()
        matches = []
        for candidate in candidates:
            if all(abs(candidate[1] - m[1]) >= max(window, HORIZON) for m in matches):
                matches.append(candidate)
            if len(matches) == 5:
                break
        if len(matches) < 3:
            continue
        distances = [m[0] for m in matches]
        outcomes = [m[2] for m in matches]
        hit_rate = sum(x >= threshold for x in outcomes) / len(outcomes)
        result = {
            "pattern_window": window,
            "pattern_matches": len(matches),
            "pattern_similarity": round(float(np.exp(-np.mean(distances) * 8) * 100), 1),
            "pattern_historical_hit_pct": round(hit_rate * 100, 1),
            "pattern_median_forward_pct": round(float(np.median(outcomes) * 100), 2),
            "pattern_target_pct": round(threshold * 100),
        }
        if best is None or (result["pattern_similarity"], len(matches)) > (best["pattern_similarity"], best["pattern_matches"]):
            best = result
    return best or {
        "pattern_window": None, "pattern_matches": 0,
        "pattern_similarity": None, "pattern_historical_hit_pct": None,
        "pattern_median_forward_pct": None, "pattern_target_pct": 10,
    }
