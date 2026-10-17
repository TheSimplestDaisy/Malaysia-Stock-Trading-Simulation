import numpy as np
import pandas as pd
from .config import Market


def generate_data(market: Market, seed: int = 42, sessions: int = 180) -> dict[str, pd.DataFrame]:
    """Invented weekday OHLCV; not an exchange calendar or historical prices."""
    if sessions < 1:
        raise ValueError("sessions must be positive")
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-01-02", periods=sessions)
    result = {}
    for i, symbol in enumerate(market.symbols):
        base = (5 + i * 4) if market.currency == "MYR" else (50 + i * 70)
        close = base * np.exp(np.cumsum(rng.normal(0.0006, 0.018, sessions)))
        previous = np.r_[base, close[:-1]]
        opening = previous * np.exp(rng.normal(0, 0.004, sessions))
        spread = rng.uniform(0.002, 0.018, sessions)
        result[symbol] = pd.DataFrame({
            "open": opening, "high": np.maximum(opening, close) * (1 + spread),
            "low": np.minimum(opening, close) * (1 - spread), "close": close,
            "volume": rng.integers(100_000, 2_000_000, sessions),
        }, index=dates)
    return result
