"""Bounded, unattended multi-asset research scan. Not an exhaustive market feed."""
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf

UNIVERSE = {
    "Stocks": ["AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","AMD","PLTR","AVGO","JPM","XOM","JNJ","WMT","LLY","COIN","MSTR","ARM","SHEL.L","AZN.L","HSBA.L","BP.L","RR.L","BARC.L","LLOY.L","VOD.L"],
    "Crypto": ["BTC-USD","ETH-USD","SOL-USD","XRP-USD","BNB-USD","ADA-USD","DOGE-USD","LINK-USD","AVAX-USD","LTC-USD"],
    "Commodities": ["GC=F","SI=F","PL=F","PA=F","HG=F","CL=F","BZ=F","NG=F","HO=F","RB=F","ZC=F","ZW=F","ZS=F","ZM=F","ZL=F","KC=F","SB=F","CC=F","CT=F","OJ=F","LE=F","GF=F","HE=F"],
}
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
    # Heuristic prioritisation only; not a probability or recommendation.
    score = 3*breakout + 2*surge + 2*momentum + consolidation + (ret5>=.05)
    return {"market":market,"symbol":ticker,"as_of":str(d.index[-1]),"close":round(float(close.iloc[-1]),5),"change_5d_pct":round(float(ret5*100),2),"change_20d_pct":round(float(ret20*100),2),"volume_ratio":round(vr,2) if vr is not None else None,"support_20d":round(float(prior_low),5),"resistance_20d":round(float(prior_high),5),"signals":", ".join(flags) or "None","research_score":int(score)}
def main():
    rows=[]; failures=[]
    for market,tickers in UNIVERSE.items():
        for ticker in tickers:
            try:
                df=yf.Ticker(ticker).history(period="6mo",interval="1d",auto_adjust=True,timeout=15)
                if df.empty: raise ValueError("No history")
                result=evaluate(df,ticker,market)
                if result is None: raise ValueError("Insufficient candles")
                rows.append(result)
            except Exception as exc:
                failures.append({"market":market,"symbol":ticker,"error":str(exc)[:120]})
    out=Path("background_results");out.mkdir(exist_ok=True)
    columns=["market","symbol","as_of","close","change_5d_pct","change_20d_pct","volume_ratio","support_20d","resistance_20d","signals","research_score"]
    pd.DataFrame(rows,columns=columns).sort_values("research_score",ascending=False).to_csv(out/"ranked_opportunities.csv",index=False)
    (out/"scan_summary.json").write_text(json.dumps({"generated_utc":datetime.now(timezone.utc).isoformat(),"scope":"Curated free-data starter universe, not all listed assets","requested":sum(map(len,UNIVERSE.values())),"analysed":len(rows),"failed":failures,"method":"Descriptive heuristics, no verified predictive edge"},indent=2))
    print(f"Analysed {len(rows)} assets; {len(failures)} failures")
if __name__=="__main__": main()
