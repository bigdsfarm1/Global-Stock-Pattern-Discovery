"""Offline smoke tests for the deployed app's pattern engine."""
import unittest
import numpy as np
import pandas as pd
from pattern_discovery import discover_patterns, discover_patterns_for_window
from background_scan import evaluate
from price_action_sequences import detect_sequences

class PatternTests(unittest.TestCase):
    def setUp(self):
        t = np.arange(180)
        close = 100 + 0.12*t + 3*np.sin(t/5)
        self.frame = pd.DataFrame({
            "Open": close-0.3, "High":close+0.8, "Low":close-0.9,
            "Close":close, "Volume":np.full(len(t),1000),
        })
    def test_all_windows(self):
        for w in (1,3,5,10,20,40):
            result = discover_patterns_for_window(
                self.frame.Close.to_numpy(),w,
                ohlc=self.frame[["Open","High","Low","Close"]].to_numpy())
            self.assertEqual(result["pattern_window"],w)
            self.assertGreaterEqual(result["pattern_matches"],3)
    def test_background_scan(self):
        result=evaluate(self.frame,"TEST","Stocks")
        self.assertIsNotNone(result)
        self.assertIn("pattern_window",result)
    def test_price_action_sequence_output(self):
        result=detect_sequences(self.frame)
        self.assertIn("sequence_stage",result)
        self.assertIn("sequence_support",result)
    def test_no_single_close_shape(self):
        result=discover_patterns_for_window(self.frame.Close.to_numpy(),1)
        self.assertEqual(result["pattern_matches"],0)
    def test_no_future_data(self):
        result=discover_patterns_for_window(self.frame.Close.to_numpy()[:15],5)
        self.assertEqual(result["pattern_matches"],0)

if __name__=="__main__":
    unittest.main()
