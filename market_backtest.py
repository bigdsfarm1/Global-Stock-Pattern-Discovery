"""Optional research backtest across a fixed sample of markets; no trading simulation."""
import yfinance as yf
from validation import holdout_test

SYMBOLS = ["AAPL", "MSFT", "NVDA", "TSLA", "BARC.L", "RR.L", "BTC-USD", "ETH-USD"]

def main():
    total = {"BUY": [0, 0, 0.0], "WAIT": [0, 0, 0.0], "SELL": [0, 0, 0.0]}
    for symbol in SYMBOLS:
        try:
            d = yf.Ticker(symbol).history(period="5y", auto_adjust=True)
            if d.empty:
                print(f"{symbol}: no data")
                continue
            result = holdout_test(d, horizon=30)
            if result["status"] != "ok":
                print(f"{symbol}: {result['reason']}")
                continue
            counts = {k: v["count"] for k, v in result["results"].items()}
            print(f"{symbol}: {result['observations']} nonoverlapping dates; signals {counts}; baseline up {result['baseline_up']:.1%}; baseline return {result['baseline_mean']:+.1%}")
            for row in result["rows"]:
                label = row["signal"]
                total[label][0] += 1
                total[label][1] += int(row["forward_return"] > 0)
                total[label][2] += row["forward_return"]
        except Exception as exc:
            print(f"{symbol}: data error {exc}")
    print("COMBINED (not independent across correlated assets)")
    for label, (n, wins, sum_returns) in total.items():
        print(f"{label}: n={n}; up-rate={wins/n:.1%}; average 30-day return={sum_returns/n:+.1%}" if n else f"{label}: no examples")
    print("Research only: no costs, delistings, shorts, slippage or dividends; thresholds not proven out of sample.")

if __name__ == "__main__":
    main()
