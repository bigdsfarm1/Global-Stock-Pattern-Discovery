import unittest
import numpy as np
import pandas as pd
from validation import holdout_test, technical_label


class ValidationTests(unittest.TestCase):
    def make_prices(self, n=300):
        rng = np.random.default_rng(42)
        close = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.015, n)))
        return pd.DataFrame({"Open": close*0.999, "High": close*1.01,
                             "Low": close*0.99, "Close": close,
                             "Volume": np.full(n, 100000)}, index=pd.bdate_range("2024-01-01", periods=n))

    def test_short_history_is_insufficient(self):
        self.assertEqual(holdout_test(self.make_prices(100))["status"], "insufficient")

    def test_holdout_uses_complete_nonoverlapping_windows(self):
        result = holdout_test(self.make_prices(), horizon=20)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(sum(v["count"] for v in result["results"].values()), result["observations"])
        self.assertTrue(all(x["signal"] in ("BUY", "WAIT", "SELL") for x in result["rows"]))
        self.assertLessEqual(result["observations"], 5)

    def test_label_uses_only_prior_prices(self):
        d = self.make_prices(200)
        from scanner import add_signals
        full = add_signals(d)
        self.assertEqual(technical_label(full.iloc[:120]), technical_label(add_signals(d.iloc[:120])))


if __name__ == "__main__":
    unittest.main()
