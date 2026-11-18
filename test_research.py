"""Deterministic checks for candlestick research without network access."""
import unittest
import numpy as np
import pandas as pd
from discover_patterns import study, TARGETS, HORIZONS
from scanner import PATTERNS, add_signals

class ResearchTests(unittest.TestCase):
    def frame(self, n=100):
        dates = pd.bdate_range("2024-01-01", periods=n)
        close = np.full(n, 100.0)
        return pd.DataFrame({"Open": close.copy(), "High": close + 1,
                             "Low": close - 1, "Close": close.copy(),
                             "Volume": np.full(n, 1000)}, index=dates)

    def test_every_target_and_horizon_is_present(self):
        rows = study(self.frame())
        self.assertEqual(len(rows), len(PATTERNS) * len(TARGETS) * len(HORIZONS))
        self.assertEqual({r["target_pct"] for r in rows}, {5, 10, 20, 50})
        self.assertEqual({r["horizon_days"] for r in rows}, {1, 5, 10, 20, 30})

    def test_future_candles_not_used_when_incomplete(self):
        rows = study(self.frame())
        for row in rows:
            self.assertEqual(row["baseline_days"], 100 - row["horizon_days"])
            self.assertEqual(row["baseline_hits"], 0)

    def test_future_high_touch_counted_not_close(self):
        frame = self.frame()
        frame.iloc[60, frame.columns.get_loc("High")] = 106.0
        rows = study(frame)
        item = next(r for r in rows if r["horizon_days"] == 5
                    and r["target_pct"] == 5 and r["pattern"] == PATTERNS[0])
        self.assertEqual(item["baseline_hits"], 5)

    def test_no_future_leak_in_signals(self):
        frame = self.frame()
        first = add_signals(frame.iloc[:70])
        frame.iloc[80, frame.columns.get_loc("Close")] = 200
        later = add_signals(frame)
        for pattern in PATTERNS:
            self.assertTrue(first[pattern].equals(later[pattern].iloc[:70]))

if __name__ == "__main__":
    unittest.main()
