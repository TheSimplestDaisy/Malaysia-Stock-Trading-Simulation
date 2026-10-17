from dataclasses import dataclass


@dataclass(frozen=True)
class Market:
    name: str
    currency: str
    lot: int
    symbols: tuple[str, ...]


MARKETS = {
    "Bursa Malaysia": Market("Bursa Malaysia", "MYR", 100, ("BURSA_A", "BURSA_B", "BURSA_C")),
    "US Stocks": Market("US Stocks", "USD", 1, ("US_A", "US_B", "US_C")),
}


@dataclass(frozen=True)
class Settings:
    initial_cash: float = 100_000
    fee_rate: float = 0.001
    minimum_fee: float = 1.0
    slippage: float = 0.001
    max_allocation: float = 0.25
    max_positions: int = 3
    daily_loss_limit: float = 0.03

    def __post_init__(self):
        import math
        if not all(math.isfinite(v) for v in (self.initial_cash, self.fee_rate, self.minimum_fee,
                                            self.slippage, self.max_allocation, self.daily_loss_limit)):
            raise ValueError("Settings must be finite")
        if self.initial_cash <= 0 or self.fee_rate < 0 or self.minimum_fee < 0:
            raise ValueError("Invalid cash or fees")
        if not 0 <= self.slippage < 1 or not 0 < self.max_allocation <= 1:
            raise ValueError("Invalid slippage or allocation")
        if not 0 < self.daily_loss_limit < 1 or self.max_positions < 1:
            raise ValueError("Invalid risk limits")
