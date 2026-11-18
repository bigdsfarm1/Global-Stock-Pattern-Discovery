"""Unsupervised multi-candle sequence search: no named formations or direction rules."""
import numpy as np

WINDOWS=(3,5,8,13,20,30,40)
HORIZON=10

def _features(candles):
    """Normalize candle bodies, wicks and close-to-close path for scale-free comparison."""
    x=np.asarray(candles,dtype=float)
    if len(x)<2 or not np.isfinite(x).all() or np.any(x<=0):
        return None
    o,h,l,c=x.T
    scale=max(float(np.median((h-l)/c)),0.001)
    body=np.clip((c-o)/c/scale,-5,5)
    upper=np.clip((h-np.maximum(o,c))/c/scale,0,5)
    lower=np.clip((np.minimum(o,c)-l)/c/scale,0,5)
    change=np.clip(np.diff(np.log(c),prepend=np.log(o[0]))/scale,-5,5)
    return np.column_stack((body,upper,lower,change)).ravel()

def find_repeating_sequences(ohlc, windows=WINDOWS, horizon=HORIZON, matches=8):
    """Find nearest past whole-candle sequences with observed future outcomes.

    This is descriptive matching, NOT a trained or independently validated forecast.
    """
    x=np.asarray(ohlc,dtype=float)
    if x.ndim!=2 or x.shape[1]!=4 or not np.isfinite(x).all() or np.any(x<=0):
        return []
    n=len(x)
    findings=[]
    for w in windows:
        if n < 2*w+horizon+10:
            continue
        now=_features(x[-w:])
        if now is None:
            continue
        options=[]
        # Earlier sequences and their future must be fully known before the latest window.
        for end in range(w,n-max(w,horizon)+1):
            past=_features(x[end-w:end])
            if past is None:
                continue
            dist=float(np.sqrt(np.mean((now-past)**2)))
            future=float(x[end+horizon-1,3]/x[end-1,3]-1)
            options.append((dist,end,future))
        options.sort(key=lambda t:t[0])
        selected=[]
        for item in options:
            if all(abs(item[1]-other[1])>=max(w,horizon) for other in selected):
                selected.append(item)
            if len(selected)>=matches:
                break
        if len(selected)<3:
            continue
        outcomes=np.array([v[2] for v in selected])
        findings.append({
            "window":w,"matches":len(selected),
            "similarity_pct":round(float(100*np.exp(-np.mean([v[0] for v in selected])/2)),1),
            "positive_pct":round(float(100*np.mean(outcomes>0)),1),
            "negative_pct":round(float(100*np.mean(outcomes<0)),1),
            "median_forward_pct":round(float(100*np.median(outcomes)),2),
            "historical_up_5pct":round(float(100*np.mean(outcomes>=0.05)),1),
            "historical_down_5pct":round(float(100*np.mean(outcomes<=-0.05)),1),
        })
    return findings
