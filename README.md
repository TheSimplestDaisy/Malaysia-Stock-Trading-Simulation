# AI Trading Assistant 0.1

**SYNTHETIC DATA — SIMULATION ONLY.** This application invents market prices and
uses virtual cash. It has no broker integration, live data feed, or live orders.
The scanner is deterministic and rule based, not a trained AI model.

## Windows PowerShell setup

Python 3.13 was used for development. Open PowerShell and run:

```powershell
Set-Location C:\Users\zzulk\Codex-Learning\AITradingAssistant
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

The local `.venv` is already created after initial implementation. On subsequent
runs, only the last command is needed. Open http://localhost:8501 if your browser
does not open automatically. Press Ctrl+C in PowerShell to stop the server.
Explicitly calling the environment's Python avoids activation-policy issues.
If your PowerShell profile reports a missing Anaconda executable, start
`powershell -NoProfile` and use the same commands.

## Using the dashboard

1. Select Bursa Malaysia (MYR) or US Stocks (USD). Each has an independent virtual
   account, initially 100,000 in its own currency. No currency conversion occurs.
2. Adjust optional simulation assumptions and click **Create / reset this portfolio**.
   Reset affects only the selected market. These fees are illustrative, not broker tariffs.
3. Click **Next session** to advance one invented weekday or **Run remaining sessions**.
4. Read scanner explanations, pending orders, filled trades, rejected orders,
   positions, and virtual equity. Charts only reveal sessions already processed.
5. **Emergency stop** cancels pending buys and blocks new entries. It remains
   active across sessions until reset; existing positions can still exit.

State is held in the Streamlit session: refreshing/restarting can reset it. No
portfolio persistence is promised. Market symbols are fictional, including those
with Bursa/US labels. A reproducible seed generates 180 invented weekday sessions
starting January 2025, without exchange holidays or real historical prices.

## Signal and execution rules

- EMA9/EMA21 use exponential smoothing with a 9/21-session warmup.
- RSI14 uses Wilder smoothing seeded with the first 14 price changes; flat prices
  produce RSI 50. At least 21 observations are needed for all scanner inputs.
- Volume ratio divides current volume by the **previous** 20-session mean.
- BUY: no position, EMA9 > EMA21, RSI 50–70 inclusive, volume ratio >= 1.2.
- SELL: an existing position has EMA9 < EMA21 or RSI >= 75.
- HOLD: an existing position has no exit condition.
- NO TRADE: no entry setup, missing history, or a blocked entry.

Signals use the current close and earlier data only. Orders execute at the **next
available session's open**, with adverse slippage (higher buys, lower sells).
Final-session signals cannot execute. The engine advances monotonically and
deduplicates orders by signal session, symbol, and side. Exits execute before
entries; entry sizing is calculated at the execution open, including fees.
Rejected orders are not retried. Only one position per symbol is allowed.

Bursa orders require multiples of 100 shares; US orders require whole shares.
These are simplified regular-lot assumptions: odd lots, fractional shares,
exchange tick rounding, corporate actions, dividends, taxes, borrow, liquidity,
partial fills, and intraday execution are outside Version 0.1.

## Accounting and risk

Default costs: 0.1% each side, minimum fee 1 currency unit, 0.1% adverse slippage.
Buy costs include fees; selling proportionally releases cost basis and deducts
exit fees. Equity = cash + current marked position value. Total P/L equals realized
plus unrealized P/L; returns use initial cash. Drawdown compares equity to its
running peak, including initial cash. Remaining positions stay open at the final close.

Default limits: three positions, 25% of current equity per new position including
entry fees, and a 3% daily equity loss limit. Limits are rechecked at execution.
Existing holdings can exceed the allocation through price movement. The daily
loss reference is prior-close equity (initial cash on day one), checked at the
open, after fills, and at close. Once breached it blocks entries for that session,
even if equity recovers. It resets next session; the emergency stop does not.
These are entry controls, not guaranteed loss caps or forced liquidation rules.
Gaps can exceed loss thresholds. Exit orders remain available under both stops.

## Project layout and tests

`ai_trading_assistant/` contains config, synthetic data, indicators, scanner,
portfolio accounting/risk controls, and the session engine. `app.py` is the
Streamlit interface. `tests/test_simulation.py` covers reproducibility, OHLCV,
RSI edges, signal rules, history-only indicators, lot validation, fees/slippage,
cash, allocation/position limits, daily loss latching, emergency stop, order
deduplication, next-open timing, market isolation, and dashboard interaction.

Run all checks with `.\.venv\Scripts\python.exe -m pytest -q`.
