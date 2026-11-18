"""Rolling, rate-limited global market research using free public symbol directories."""
import io
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
import numpy as np
import pandas as pd
import yfinance as yf
from pattern_discovery import discover_patterns

OUT = Path("background_results")
BATCH_SIZE = max(20, min(int(os.getenv("SCAN_BATCH_SIZE", "120")), 300))
MAX_RESULTS = 1500
# Starter symbols remain available if public directory downloads fail.
CORE = {
    "Stocks": ["AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","AMD","PLTR","AVGO","JPM","XOM","JNJ","WMT","LLY","COIN","MSTR","ARM","SHEL.L","AZN.L","HSBA.L","BP.L","RR.L","BARC.L","LLOY.L","VOD.L"],
    "Crypto": ["BTC-USD","ETH-USD","SOL-USD","XRP-USD","BNB-USD","ADA-USD","DOGE-USD","LINK-USD","AVAX-USD","LTC-USD","DOT-USD","TRX-USD","BCH-USD","XLM-USD","HBAR-USD","LTC-USD","UNI-USD","AAVE-USD","ETC-USD","ATOM-USD","NEAR-USD","APT-USD","ARB-USD","OP-USD","FIL-USD","ICP-USD","INJ-USD","SUI-USD","PEPE24478-USD","SHIB-USD"],
    "Commodities": ["GC=F","SI=F","PL=F","PA=F","HG=F","CL=F","BZ=F","NG=F","HO=F","RB=F","ZC=F","ZW=F","ZS=F","ZM=F","ZL=F","KC=F","SB=F","CC=F","CT=F","OJ=F","LE=F","GF=F","HE=F"],
}
COLUMNS = ["market","symbol","as_of","close","change_5d_pct","change_20d_pct","volume_ratio","support_20d","resistance_20d","signals","research_score","pattern_window","pattern_matches","pattern_similarity","pattern_historical_hit_pct","pattern_median_forward_pct","pattern_target_pct"]
DIRECTORIES = [
    ("nasdaqlisted", "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"),
    ("otherlisted", "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"),
]

def stock_universe():
    """Download US-listed stock directories; avoid test issues and unsupported symbols."""
    symbols = set(CORE["Stocks"])
    counts = {}
    for name, url in DIRECTORIES:
        try:
            req = Request(url, headers={"User-Agent":"Mozilla/5.0 (compatible; MarketResearch/1.0)"})
            with urlopen(req, timeout=20) as response:
                raw = response.read()
            df = pd.read_csv(io.BytesIO(raw), sep="|", dtype=str, on_bad_lines="skip")
            if name == "nasdaqlisted":
                df = df.loc[(df["Test Issue"] == "N") & (df["ETF"] == "N")]
                column = "Symbol"
            else:
                df = df.loc[(df["Test Issue"] == "N") & (df["ETF"] == "N")]
                column = "ACT Symbol"
            additions = 0
            for sym in df[column].dropna():
                sym = sym.strip().upper()
                # Yahoo uses '-' for some US class shares, but ambiguous exotic symbols are skipped.
                if sym and all(c.isalnum() or c in ".-" for c in sym) and len(sym) <= 12:
                    symbols.add(sym.replace(".", "-"))
                    additions += 1
            counts[name] = additions
        except Exception as exc:
            counts[name] = "unavailable: " + str(exc)[:100]
    return sorted(symbols), counts

def universe():
    stocks, sources = stock_universe()
    return [("Stocks", x) for x in stocks] + [("Crypto", x) for x in dict.fromkeys(CORE["Crypto"])] + [("Commodities", x) for x in CORE["Commodities"]], sources

def evaluate(frame, ticker, market):
    d = frame.dropna(subset=["Open","High","Low","Close"]).copy()
    if len(d) < 65: return None
    close, high, low, volume = [d[x].astype(float) for x in ("Close","High","Low","Volume")]
    if close.iloc[-1] <= 0: return None
    ret5 = close.iloc[-1]/close.iloc[-6]-1
    ret20 = close.iloc[-1]/close.iloc[-21]-1
    prior_high = high.iloc[-21:-1].max()
    prior_low = low.iloc[-21:-1].min()
    vmean = volume.iloc[-21:-1].mean()
    vr = float(volume.iloc[-1]/vmean) if vmean > 0 else None
    ma20 = close.iloc[-20:].mean()
    ma50 = close.iloc[-50:].mean()
    # Normalised 20-day shape, rough consolidation and breakout heuristics.
    width = (prior_high-prior_low)/close.iloc[-1]
    breakout = close.iloc[-1] > prior_high
    consolidation = width < .10
    momentum = close.iloc[-1] > ma20 > ma50
    surge = vr is not None and vr >= 1.8
    flags = [name for name, present in [("20-day breakout",breakout),("Tight consolidation",consolidation),("Uptrend",momentum),("Volume surge",surge),("5-day rise >= 5%",ret5>=.05),("20-day rise >= 5%",ret20>=.05)] if present]
    pattern = discover_patterns(close.to_numpy(), ohlc=d[["Open", "High", "Low", "Close"]].to_numpy())
    if pattern["pattern_matches"] >= 3 and pattern["pattern_similarity"] >= 75:
        flags.append(f'Historical {pattern["pattern_window"]}-day chart analogs')
    # Heuristic prioritisation only; not a probability or recommendation.
    score = 3*breakout + 2*surge + 2*momentum + consolidation + (ret5>=.05)
    return {"market":market,"symbol":ticker,"as_of":str(d.index[-1]),"close":round(float(close.iloc[-1]),5),"change_5d_pct":round(float(ret5*100),2),"change_20d_pct":round(float(ret20*100),2),"volume_ratio":round(vr,2) if vr is not None else None,"support_20d":round(float(prior_low),5),"resistance_20d":round(float(prior_high),5),"signals":", ".join(flags) or "None","research_score":int(score), **pattern}
def main():
    OUT.mkdir(exist_ok=True)
    all_symbols, sources = universe()
    if not all_symbols:
        raise RuntimeError("No symbols available")
    state_file = OUT / "scan_state.json"
    try:
        state = json.loads(state_file.read_text())
    except (OSError, ValueError):
        state = {}
    # A stable sorted directory ensures batches move through the entire available universe.
    offset = int(state.get("offset", 0)) % len(all_symbols)
    selected = [all_symbols[(offset+i) % len(all_symbols)] for i in range(min(BATCH_SIZE, len(all_symbols)))]
    rows, failures = [], []
    for market, ticker in selected:
        try:
            df = yf.Ticker(ticker).history(period="6mo", interval="1d", auto_adjust=True, timeout=12)
            if df.empty:
                raise ValueError("No history")
            result = evaluate(df, ticker, market)
            if result is None:
                raise ValueError("Insufficient candles")
            rows.append(result)
        except Exception as exc:
            failures.append({"market":market,"symbol":ticker,"error":str(exc)[:120]})
        time.sleep(0.12)
    path = OUT / "ranked_opportunities.csv"
    if path.exists():
        try:
            previous = pd.read_csv(path)
        except (OSError, ValueError, pd.errors.ParserError):
            previous = pd.DataFrame(columns=COLUMNS)
    else:
        previous = pd.DataFrame(columns=COLUMNS)
    fresh = pd.DataFrame(rows, columns=COLUMNS)
    # Retain earlier batches; newer scans replace stale rows for the same asset.
    combined = pd.concat([previous, fresh], ignore_index=True)
    combined = combined.drop_duplicates(subset=["market","symbol"], keep="last")
    for column in COLUMNS:
        if column not in combined.columns:
            combined[column] = None
    combined = combined.sort_values(["research_score","change_5d_pct"], ascending=[False,False]).head(MAX_RESULTS)
    combined.to_csv(path, index=False)
    new_offset = (offset + len(selected)) % len(all_symbols)
    state_file.write_text(json.dumps({"offset":new_offset, "universe_size":len(all_symbols)}, indent=2))
    summary = {
        "generated_utc":datetime.now(timezone.utc).isoformat(),
        "scope":"Rolling free-data scan: US-listed stock directories plus starter UK shares, crypto and commodity futures; NOT every exchange worldwide",
        "requested":len(all_symbols), "analysed":len(rows), "batch_requested":len(selected),
        "batch_failed":len(failures), "failed":failures[:30],
        "stored_assets":len(combined), "next_offset":new_offset,
        "directory_sources":sources,
        "method":"Descriptive heuristics plus exploratory historical whole-chart analog matching; no validated predictive edge",
    }
    (OUT / "scan_summary.json").write_text(json.dumps(summary,indent=2))
    print(f"Batch {offset}-{offset+len(selected)} of {len(all_symbols)}: {len(rows)} usable; {len(failures)} failures; {len(combined)} retained")
if __name__ == "__main__":
    main()
