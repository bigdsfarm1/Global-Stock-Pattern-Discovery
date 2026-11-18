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

    def test_rising_market_can_generate_buy(self):
        from scanner import add_signals
        close = np.linspace(60, 130, 240)
        d = pd.DataFrame({"Open": close * .999, "High": close * 1.01,
                          "Low": close * .99, "Close": close,
                          "Volume": np.full(240, 100000)},
                         index=pd.bdate_range("2024-01-01", periods=240))
        self.assertEqual(technical_label(add_signals(d)), "BUY")

    def test_falling_market_can_generate_sell(self):
        from scanner import add_signals
        close = np.linspace(130, 60, 240)
        d = pd.DataFrame({"Open": close * 1.001, "High": close * 1.01,
                          "Low": close * .99, "Close": close,
                          "Volume": np.full(240, 100000)},
                         index=pd.bdate_range("2024-01-01", periods=240))
        self.assertEqual(technical_label(add_signals(d)), "SELL")

    def test_holdout_does_not_look_into_future(self):
        from scanner import add_signals
        d = self.make_prices(320)
        altered = d.copy()
        altered.loc[altered.index[260]:, "Close"] *= 3
        self.assertEqual(technical_label(add_signals(d.iloc[:250])),
                         technical_label(add_signals(altered.iloc[:250])))

    def test_flat_market_does_not_force_a_trade(self):
        from scanner import add_signals
        close = np.full(240, 100.0)
        d = pd.DataFrame({"Open": close, "High": close * 1.001,
                          "Low": close * .999, "Close": close,
                          "Volume": np.full(240, 100000)},
                         index=pd.bdate_range("2024-01-01", periods=240))
        self.assertEqual(technical_label(add_signals(d)), "WAIT")

    def test_label_uses_only_prior_prices(self):
        d = self.make_prices(200)
        from scanner import add_signals
        full = add_signals(d)
        self.assertEqual(technical_label(full.iloc[:120]), technical_label(add_signals(d.iloc[:120])))


if __name__ == "__main__":
    unittest.main()
