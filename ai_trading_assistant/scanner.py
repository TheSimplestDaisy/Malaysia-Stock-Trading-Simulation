import math


def scan(row, held: bool = False) -> tuple[str, str]:
    keys = ("ema9", "ema21", "rsi14", "volume_ratio")
    if not all(math.isfinite(float(row[k])) for k in keys):
        return "NO TRADE", "Insufficient indicator history (at least 21 sessions needed)."
    fast, slow, rsi, volume = (float(row[k]) for k in keys)
    detail = f"EMA9 {fast:.2f}, EMA21 {slow:.2f}, RSI14 {rsi:.1f}, volume {volume:.2f}x prior 20-session average."
    if held:
        if fast < slow or rsi >= 75:
            return "SELL", detail + " Bearish trend or RSI at least 75: exit position."
        return "HOLD", detail + " No exit condition."
    if fast > slow and 50 <= rsi <= 70 and volume >= 1.2:
        return "BUY", detail + " Bullish trend, RSI 50–70, and volume at least 1.2x."
    return "NO TRADE", detail + " Entry requires EMA9 > EMA21, RSI 50–70, and volume >= 1.2x."
