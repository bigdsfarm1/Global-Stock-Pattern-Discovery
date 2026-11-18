"""Explainable multi-candle price-action sequence detection (research heuristics)."""
import numpy as np
import pandas as pd

def detect_sequences(frame):
    """Detect a recent selloff, bounded bounces, lower highs and support breakdown.

    The sequence is assessed on the last 35 daily candles. No future prices are used.
    Thresholds are relative to price and recent volatility, not fixed dollar values.
    """
    d = frame[["Open","High","Low","Close"]].apply(pd.to_numeric, errors="coerce").dropna().tail(35)
    result = {"sequence_name":"None","sequence_stage":"None","sequence_strength":0,
              "sequence_support":None,"sequence_resistance":None}
    if len(d)<30 or (d["Close"]<=0).any():
        return result
    c=d.Close.to_numpy(dtype=float); h=d.High.to_numpy(dtype=float); l=d.Low.to_numpy(dtype=float)
    # Prior decline followed by a choppy range and (optionally) a recent breakdown.
    # Use range candles  -13 to -3, reserving two latest candles for confirmation.
    prior_peak=float(np.max(h[:16]))
    range_hi=float(np.max(h[-13:-2]))
    range_lo=float(np.min(l[-13:-2]))
    range_width=(range_hi-range_lo)/max(range_lo,1e-9)
    drop=(prior_peak-range_hi)/prior_peak
    if not (drop>=0.035 and 0.008<=range_width<=0.085):
        return result
    # Count alternating directional changes: avoid identifying a straight-line move as zigzag.
    dif=np.diff(c[-13:-2])
    significant=np.abs(dif)>=max(np.median(np.abs(dif))*0.5, c[-1]*0.0004)
    signs=np.sign(dif[significant])
    turns=int(np.sum(signs[1:]!=signs[:-1])) if len(signs)>1 else 0
    if turns<3:
        return result
    # Split the range to check that the second half struggles to make higher highs.
    first_hi=float(np.max(h[-13:-8]))
    second_hi=float(np.max(h[-8:-2]))
    lower_highs=second_hi <= first_hi*1.003
    if not lower_highs:
        return result
    confirmed=bool(c[-1]<range_lo*0.997 and c[-2]<range_lo*0.997)
    probing=bool(c[-1]<range_lo*0.997)
    stage="Confirmed breakdown" if confirmed else ("Possible breakdown" if probing else "Consolidating")
    strength=3+int(drop>=0.07)+int(turns>=5)+int(probing)+int(confirmed)
    return {"sequence_name":"Selloff → zigzag → weaker highs → breakdown",
            "sequence_stage":stage,"sequence_strength":strength,
            "sequence_support":round(range_lo,5),
            "sequence_resistance":round(range_hi,5)}
