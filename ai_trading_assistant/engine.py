from .indicators import indicators
from .portfolio import Portfolio
from .scanner import scan


class Simulation:
    def __init__(self, market, settings, data):
        self.portfolio = Portfolio(market, settings)
        self.data = {s: indicators(f) for s, f in data.items()}
        self.dates = next(iter(data.values())).index
        self.cursor = -1
        self.pending = []
        self.signals = []
        self.history = []

    def stop(self):
        self.portfolio.emergency_stop = True
        retained = []
        for order in self.pending:
            if order[1] == "BUY":
                self.portfolio.orders.append(dict(date=self.dates[self.cursor], signal_date=order[2],
                    symbol=order[0], side="BUY", quantity=0, status="CANCELLED", reason="Emergency stop"))
            else:
                retained.append(order)
        self.pending = retained

    def step(self):
        if self.cursor + 1 >= len(self.dates):
            return False
        self.cursor += 1
        date = self.dates[self.cursor]
        p = self.portfolio
        opening = {s: float(f.loc[date, "open"]) for s, f in self.data.items()}
        closing = {s: float(f.loc[date, "close"]) for s, f in self.data.items()}
        previous = self.history[-1]["equity"] if self.history else p.settings.initial_cash
        p.begin_day(date, previous)
        p.check_loss(opening)
        # Exits first. Every fill uses only this session's open and prior signals.
        for symbol, side, signal_date in sorted(self.pending, key=lambda o: o[1] != "SELL"):
            quantity = p.positions[symbol].quantity if side == "SELL" and symbol in p.positions else p.size(symbol, opening)
            p.execute(symbol, side, quantity, date, signal_date, opening)
        self.pending = []
        p.check_loss(closing)
        self.signals = []
        for symbol, frame in self.data.items():
            row = frame.loc[date]
            signal, explanation = scan(row, symbol in p.positions)
            if signal == "BUY":
                reason = p.entry_block(symbol, closing)
                if reason:
                    signal, explanation = "NO TRADE", explanation + " Blocked: " + reason
            final = self.cursor == len(self.dates) - 1
            if signal in ("BUY", "SELL") and not final:
                self.pending.append((symbol, signal, date))
            if final and signal in ("BUY", "SELL"):
                explanation += " End of data: no next session available; no order queued."
            self.signals.append(dict(symbol=symbol, signal=signal, explanation=explanation,
                close=row["close"], ema9=row["ema9"], ema21=row["ema21"], rsi14=row["rsi14"], volume_ratio=row["volume_ratio"]))
        equity = p.equity(closing)
        peak = max([p.settings.initial_cash, equity] + [h["equity"] for h in self.history])
        self.history.append(dict(date=date, equity=equity, cash=p.cash,
            realized_pnl=p.realized, unrealized_pnl=equity-p.cash-sum(x.cost for x in p.positions.values()),
            drawdown=equity / peak - 1))
        return True

    def run(self):
        while self.step():
            pass
