import numpy as np
import pandas as pd


def indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    close = out["close"]
    out["ema9"] = close.ewm(span=9, adjust=False, min_periods=9).mean()
    out["ema21"] = close.ewm(span=21, adjust=False, min_periods=21).mean()
    delta = close.diff()
    gains, losses = delta.clip(lower=0), -delta.clip(upper=0)
    rsi = pd.Series(np.nan, index=out.index)
    if len(out) > 14:
        gain, loss = gains.iloc[1:15].mean(), losses.iloc[1:15].mean()
        for i in range(14, len(out)):
            if i > 14:
                gain = (gain * 13 + gains.iloc[i]) / 14
                loss = (loss * 13 + losses.iloc[i]) / 14
            rsi.iloc[i] = 50 if gain == loss == 0 else (100 if loss == 0 else 100 - 100 / (1 + gain / loss))
    out["rsi14"] = rsi
    out["volume_average"] = out["volume"].shift(1).rolling(20).mean()
    out["volume_ratio"] = out["volume"] / out["volume_average"]
    return out
