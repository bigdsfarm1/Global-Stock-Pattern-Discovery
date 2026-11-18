"""Historical candlestick pattern outcome research, NOT predictive validation."""
import argparse
import csv
import json
from pathlib import Path
import pandas as pd
from scanner import PATTERNS, add_signals

TARGETS = (0.05, 0.10, 0.20, 0.50)
HORIZONS = (1, 5, 10, 20, 30)

def study(frame):
    d = add_signals(frame)
    rows = []
    for horizon in HORIZONS:
        # A rise is defined as a future HIGH touching a threshold above
        # the signal day's CLOSE. This is NOT a tradable close-to-close return.
        future_high = pd.concat([d["High"].shift(-step) for step in range(1, horizon + 1)], axis=1).max(axis=1)
        complete = d["High"].shift(-horizon).notna() & d["Close"].gt(0)
        for pattern in PATTERNS:
            selected = complete & d[pattern]
            baseline = complete
            for target in TARGETS:
                hits = future_high >= d["Close"] * (1 + target)
                rows.append({
                    "pattern": pattern, "horizon_days": horizon, "target_pct": int(target * 100),
                    "signals": int(selected.sum()),
                    "hits": int((hits & selected).sum()),
                    "baseline_days": int(baseline.sum()),
                    "baseline_hits": int((hits & baseline).sum())
                })
    return rows

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="research_data")
    parser.add_argument("--output", default="research_results")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    aggregated = {}
    processed = []
    for path in sorted(Path(args.input).glob("*.csv")):
        try:
            frame = pd.read_csv(path, parse_dates=["Date"]).set_index("Date")
            if len(frame) < 80:
                continue
            for row in study(frame):
                key = (row["pattern"], row["horizon_days"], row["target_pct"])
                if key not in aggregated:
                    aggregated[key] = dict(row)
                else:
                    for field in ("signals", "hits", "baseline_days", "baseline_hits"):
                        aggregated[key][field] += row[field]
            processed.append(path.stem)
        except Exception as exc:
            print(f"Skipped {path.name}: {type(exc).__name__}")
    if not processed:
        raise SystemExit("No valid input histories")
    records = []
    for key, row in sorted(aggregated.items()):
        n, base = row["signals"], row["baseline_days"]
        row["hit_rate"] = round(row["hits"] / n, 5) if n else None
        row["baseline_rate"] = round(row["baseline_hits"] / base, 5) if base else None
        records.append(row)
    with (output / "pattern_outcomes.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    (output / "summary.json").write_text(json.dumps({
        "assets_processed": processed, "target_percentages": [5, 10, 20, 50],
        "horizons_trading_days": list(HORIZONS),
        "warning": "Exploratory in-sample counts only. Overlapping windows, survivorship bias, and high-price touches inflate apparent opportunity. Not a forecast or validated trading strategy."
    }, indent=2))
    print(f"Studied {len(processed)} assets; wrote {len(records)} pattern/target/horizon rows.")

if __name__ == "__main__":
    main()
