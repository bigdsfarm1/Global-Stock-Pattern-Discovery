"""Historical whole-chart analog discovery; exploratory, not predictive validation."""
import numpy as np

WINDOWS = (10, 20, 40)
HORIZON = 10

def discover_patterns(close, threshold=0.10):
    """Compare today's entire normalized price path with prior paths in the same asset.

    Historical outcomes are measured only AFTER each historical pattern ended.
    The current pattern's future is never used. Non-overlapping analogs reduce
    duplicates, but these are in-sample analogs, not out-of-sample predictions.
    """
    values = np.asarray(close, dtype=float)
    values = values[np.isfinite(values) & (values > 0)]
    n = len(values)
    best = None
    for window in WINDOWS:
        if n < 2 * window + HORIZON + 10:
            continue
        current = np.log(values[-window:] / values[-window])
        current = current - np.linspace(0, 1, window) * current[-1] * 0.25
        candidates = []
        # End is exclusive; future outcomes must be fully observed.
        for end in range(window, n - HORIZON + 1):
            past = np.log(values[end-window:end] / values[end-window])
            past = past - np.linspace(0, 1, window) * past[-1] * 0.25
            distance = float(np.sqrt(np.mean((current - past) ** 2)))
            future_return = float(values[end + HORIZON - 1] / values[end - 1] - 1)
            candidates.append((distance, end, future_return))
        candidates.sort()
        matches = []
        for candidate in candidates:
            if all(abs(candidate[1] - m[1]) >= window for m in matches):
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
