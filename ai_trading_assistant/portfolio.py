from dataclasses import dataclass
import math
from .config import Market, Settings


@dataclass
class Position:
    quantity: int
    cost: float  # includes entry fees


class Portfolio:
    def __init__(self, market: Market, settings: Settings):
        self.market, self.settings = market, settings
        self.cash = settings.initial_cash
        self.positions: dict[str, Position] = {}
        self.trades: list[dict] = []
        self.orders: list[dict] = []
        self.processed: set[tuple] = set()
        self.realized = 0.0
        self.emergency_stop = False
        self.loss_locked = False
        self.day = None
        self.day_start_equity = settings.initial_cash

    def equity(self, prices):
        return self.cash + sum(p.quantity * prices[s] for s, p in self.positions.items())

    def begin_day(self, day, previous_equity):
        if day != self.day:
            self.day = day
            self.day_start_equity = previous_equity
            self.loss_locked = False

    def check_loss(self, prices):
        if self.equity(prices) <= self.day_start_equity * (1 - self.settings.daily_loss_limit):
            self.loss_locked = True
        return self.loss_locked

    def entry_block(self, symbol, prices):
        self.check_loss(prices)
        if self.emergency_stop:
            return "Emergency stop active"
        if self.loss_locked:
            return "Daily equity loss limit reached"
        if symbol in self.positions:
            return "Position already held; pyramiding disabled"
        if len(self.positions) >= self.settings.max_positions:
            return "Maximum number of positions reached"
        return ""

    def fee(self, notional):
        return max(self.settings.minimum_fee, notional * self.settings.fee_rate)

    def size(self, symbol, prices):
        price = prices[symbol] * (1 + self.settings.slippage)
        budget = min(self.cash, self.equity(prices) * self.settings.max_allocation)
        affordable = min(budget / (1 + self.settings.fee_rate), budget - self.settings.minimum_fee)
        return max(0, int(affordable / price / self.market.lot) * self.market.lot)

    def execute(self, symbol, side, quantity, day, signal_day, prices):
        key = (signal_day, symbol, side)
        if key in self.processed:
            return False  # idempotent: no second order or fill
        self.processed.add(key)
        reason = ""
        price = prices.get(symbol, float("nan"))
        if symbol not in self.market.symbols or side not in ("BUY", "SELL"):
            reason = "Unknown symbol or side"
        elif day <= signal_day:
            reason = "Execution must occur after signal session"
        elif not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0 or quantity % self.market.lot:
            reason = f"Quantity must be a positive multiple of {self.market.lot}"
        elif not math.isfinite(price) or price <= 0:
            reason = "Invalid execution price"
        elif side == "BUY":
            reason = self.entry_block(symbol, prices)
        elif symbol not in self.positions or quantity > self.positions[symbol].quantity:
            reason = "Insufficient shares; short selling disabled"
        fill = price * (1 + self.settings.slippage if side == "BUY" else 1 - self.settings.slippage)
        notional = quantity * fill
        fee = self.fee(notional)
        if not reason and side == "BUY":
            if notional + fee > self.cash + 1e-8:
                reason = "Insufficient virtual cash including fees"
            elif notional + fee > self.equity(prices) * self.settings.max_allocation + 1e-8:
                reason = "Maximum position allocation exceeded"
        record = dict(date=day, signal_date=signal_day, symbol=symbol, side=side,
                      quantity=quantity, status="REJECTED" if reason else "FILLED", reason=reason)
        self.orders.append(record)
        if reason:
            return False
        pnl = 0.0
        if side == "BUY":
            self.cash -= notional + fee
            self.positions[symbol] = Position(quantity, notional + fee)
        else:
            position = self.positions[symbol]
            cost = position.cost * quantity / position.quantity
            pnl = notional - fee - cost
            self.cash += notional - fee
            self.realized += pnl
            position.quantity -= quantity
            position.cost -= cost
            if not position.quantity:
                del self.positions[symbol]
        self.trades.append({**record, "fill_price": fill, "fee": fee, "realized_pnl": pnl})
        self.check_loss(prices)
        return True
