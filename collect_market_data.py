"""Free, bounded Yahoo daily OHLCV collector; saves per-symbol CSV files."""
import argparse
import csv
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
import yfinance as yf

COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", default="research_universe.txt")
    parser.add_argument("--output", default="research_data")
    parser.add_argument("--max-symbols", type=int, default=30)
    parser.add_argument("--period", default="5y")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    symbols = []
    for line in Path(args.universe).read_text().splitlines():
        symbol = line.strip().upper()
        if symbol and not symbol.startswith("#") and symbol not in symbols:
            symbols.append(symbol)
    successes, failures = [], []
    for ticker in symbols[:max(0, args.max_symbols)]:
        try:
            data = yf.Ticker(ticker).history(period=args.period, interval="1d", auto_adjust=True)
            if data.empty or len(data) < 80:
                raise ValueError("Insufficient daily history")
            data = data.reset_index()
            data["Date"] = data.iloc[:, 0].dt.strftime("%Y-%m-%d")
            data = data[COLUMNS].dropna(subset=["Open", "High", "Low", "Close"])
            filename = re.sub(r"[^A-Z0-9._-]", "_", ticker) + ".csv"
            data.to_csv(output / filename, index=False, float_format="%.8f")
            successes.append({"ticker": ticker, "rows": len(data), "file": filename})
            print(f"{ticker}: saved {len(data)} candles", flush=True)
        except Exception as exc:
            failures.append({"ticker": ticker, "reason": type(exc).__name__})
            print(f"{ticker}: skipped ({type(exc).__name__})", flush=True)
        time.sleep(1)
    (output / "manifest.json").write_text(json.dumps({
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "source": "Yahoo Finance via yfinance (unofficial; availability and delays vary)",
        "successes": successes, "failures": failures,
        "requested": len(symbols[:max(0, args.max_symbols)])
    }, indent=2))
    if not successes:
        raise SystemExit("No usable market data downloaded")

if __name__ == "__main__":
    main()
