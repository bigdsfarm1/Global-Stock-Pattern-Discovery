"""Chronological out-of-sample signal audit. Run: python historical_audit.py"""
import csv
import json
from pathlib import Path

import yfinance as yf
from validation import holdout_test

ASSETS = [
    "AAPL", "MSFT", "NVDA", "TSLA", "AMD", "GOOGL", "AMZN", "META",
    "JPM", "XOM", "KO", "JNJ", "WMT", "DIS", "INTC", "BA",
    "BARC.L", "RR.L", "SHEL.L", "LLOY.L", "VOD.L", "BP.L",
    "BTC-USD", "ETH-USD",
]
HORIZON = 30
OUTPUT = Path("audit_results")
OUTPUT.mkdir(exist_ok=True)


def main():
    records = []
    skipped = []
    for ticker in ASSETS:
        try:
            history = yf.Ticker(ticker).history(period="5y", auto_adjust=True)
            if history.empty:
                skipped.append(f"{ticker}: empty history")
                continue
            result = holdout_test(history, horizon=HORIZON)
            if result["status"] != "ok":
                skipped.append(f"{ticker}: {result['reason']}")
                continue
            for row in result["rows"]:
                records.append({"ticker": ticker, **row})
            print(f"{ticker}: {len(result['rows'])} holdout observations", flush=True)
        except Exception as exc:
            skipped.append(f"{ticker}: {type(exc).__name__}: {str(exc)[:120]}")
    if not records:
        raise RuntimeError("No market histories could be tested; audit cannot claim success.")

    with (OUTPUT / "observations.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ticker", "date", "signal", "forward_return"])
        writer.writeheader()
        writer.writerows(records)

    summary = {}
    for label in ("BUY", "WAIT", "SELL", "ALL"):
        rows = [r for r in records if label == "ALL" or r["signal"] == label]
        count = len(rows)
        summary[label] = {
            "observations": count,
            "assets": len({r["ticker"] for r in rows}),
            "up_fraction": sum(r["forward_return"] > 0 for r in rows) / count if count else None,
            "average_forward_return": sum(r["forward_return"] for r in rows) / count if count else None,
        }
    with (OUTPUT / "summary.json").open("w") as handle:
        json.dump({"horizon_days": HORIZON, "summary": summary, "skipped": skipped,
                   "assets_requested": len(ASSETS)}, handle, indent=2)
    lines = [
        "# Historical signal audit",
        "",
        "Final 30% of each asset's five-year history, evaluated at non-overlapping 30-day intervals.",
        "Signals are computed using only information available on each decision date.",
        "This is a price-only research audit, not a trading backtest.",
        "",
        "| Signal | Observations | Assets | Finished higher | Average next-30-day change |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, values in summary.items():
        rate = f'{values["up_fraction"]:.1%}' if values["up_fraction"] is not None else "N/A"
        avg = f'{values["average_forward_return"]:+.1%}' if values["average_forward_return"] is not None else "N/A"
        lines.append(f'| {label} | {values["observations"]} | {values["assets"]} | {rate} | {avg} |')
    lines += [
        "",
        "Interpretation: BUY should outperform WAIT and the ALL baseline; SELL should underperform them.",
        "Correlated markets and small counts weaken confidence. No transaction costs, slippage,",
        "delistings, dividends, or intraday execution. The current rule thresholds were revised",
        "after earlier observations, so this is NOT an untouched independent validation.",
        "Historical outcomes cannot establish calibrated future probabilities.",
        "",
        f'Skipped assets: {len(skipped)}',
    ]
    lines.extend(f"- {reason}" for reason in skipped)
    report = "\n".join(lines) + "\n"
    (OUTPUT / "report.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
