"""Run with: python -m streamlit run app.py"""
import pandas as pd
import streamlit as st
from ai_trading_assistant.config import MARKETS, Settings
from ai_trading_assistant.data import generate_data
from ai_trading_assistant.engine import Simulation

st.set_page_config(page_title="AI Trading Assistant — Simulation", layout="wide")
st.title("AI Trading Assistant · Version 0.1")
st.warning("SYNTHETIC DATA — SIMULATION ONLY. All prices, trades, and money are simulated.")
st.caption("An educational rule-based scanner. No live market feed or broker connection.")
name = st.sidebar.selectbox("Market / separate portfolio", list(MARKETS))
market = MARKETS[name]
st.sidebar.write(f"Currency: **{market.currency}** · Order lot: **{market.lot} shares**")
with st.sidebar.form("settings"):
    seed = st.number_input("Synthetic data seed", min_value=0, max_value=999999, value=42)
    cash = st.number_input(f"Starting virtual cash ({market.currency})", min_value=1000, value=100000, step=1000)
    allocation = st.slider("Maximum allocation per position (%)", 5, 100, 25)
    count = st.slider("Maximum positions", 1, 3, 3)
    loss = st.slider("Daily equity loss limit (%)", 1, 20, 3)
    fee = st.number_input("Simulated transaction fee (%)", min_value=0.0, max_value=5.0, value=0.1)
    minimum = st.number_input(f"Minimum fee ({market.currency})", min_value=0.0, value=1.0)
    slip = st.number_input("Adverse slippage (%)", min_value=0.0, max_value=10.0, value=0.1)
    reset = st.form_submit_button("Create / reset this portfolio")
if "simulations" not in st.session_state:
    st.session_state.simulations = {}
if reset or name not in st.session_state.simulations:
    settings = Settings(float(cash), fee / 100, minimum, slip / 100, allocation / 100, count, loss / 100)
    st.session_state.simulations[name] = Simulation(market, settings, generate_data(market, int(seed)))
sim = st.session_state.simulations[name]
p = sim.portfolio
st.info("Start with ‘Next session’ or ‘Run remaining sessions’. Signals form at the close; eligible orders fill at the next session’s open. Settings apply when you create/reset this portfolio.")
c1, c2, c3, c4 = st.columns(4)
if c3.button("Emergency stop", type="primary"):
    sim.stop()
if c4.button("Reset emergency stop"):
    p.emergency_stop = False
if c1.button("Next session"):
    sim.step()
if c2.button("Run remaining sessions"):
    sim.run()
st.write(f"**{name} · {market.currency}** | Session {sim.cursor + 1}/{len(sim.dates)} | Emergency stop: {'ACTIVE' if p.emergency_stop else 'off'} | Daily entry lock: {'ACTIVE' if p.loss_locked else 'off'}")
if sim.history:
    h = sim.history[-1]
    cols = st.columns(4)
    cols[0].metric("Virtual equity", f"{market.currency} {h['equity']:,.2f}")
    cols[1].metric("Virtual cash", f"{market.currency} {p.cash:,.2f}")
    cols[2].metric("Total profit / loss", f"{market.currency} {h['equity'] - p.settings.initial_cash:,.2f}")
    cols[3].metric("Return", f"{(h['equity']/p.settings.initial_cash-1)*100:.2f}%")
    st.write(f"Simulated date: {h['date'].date()} · Realized P/L: {market.currency} {p.realized:,.2f} · Unrealized P/L: {market.currency} {h['unrealized_pnl']:,.2f}")
    st.subheader("Scanner and signal explanations")
    st.dataframe(pd.DataFrame(sim.signals), hide_index=True, width="stretch")
    symbol = st.selectbox("Synthetic symbol chart", market.symbols)
    st.line_chart(sim.data[symbol].iloc[:sim.cursor+1][["close", "ema9", "ema21"]], y_label=market.currency)
    st.subheader("Virtual portfolio performance")
    history = pd.DataFrame(sim.history).set_index("date")
    st.line_chart(history[["equity"]], y_label=market.currency)
    st.write(f"Maximum observed drawdown: {history.drawdown.min():.2%}")
    st.subheader("Positions")
    st.dataframe(pd.DataFrame([dict(symbol=s, shares=x.quantity, cost_including_fees=x.cost,
        market_value=x.quantity*float(sim.data[s].iloc[sim.cursor]['close']), currency=market.currency)
        for s, x in p.positions.items()]), hide_index=True)
    st.subheader("Filled simulated trades")
    st.dataframe(pd.DataFrame(p.trades), hide_index=True)
    st.subheader("Order audit (including rejected and cancelled orders)")
    st.dataframe(pd.DataFrame(p.orders), hide_index=True)
    st.subheader("Pending orders for next session")
    st.dataframe(pd.DataFrame(sim.pending, columns=["symbol", "side", "signal_date"]), hide_index=True)
with st.expander("How to read this simulator"):
    st.write("BUY: bullish EMA trend, RSI between 50 and 70, volume at least 1.2 times its previous 20-session average. SELL: an existing position has EMA9 below EMA21 or RSI at least 75. HOLD: keep an existing position. NO TRADE: no entry setup, insufficient history, or a risk block.")
    st.write("The daily loss limit uses marked-to-market equity versus the prior close and latches until the next session. Emergency stop blocks buys and cancels pending buys; exits remain enabled. It does not liquidate positions. Resetting it does not clear the daily loss limit.")
    st.write("Separate MYR and USD virtual accounts; no FX conversion. Weekdays are invented sessions, not exchange calendars. Fees, lot sizes, and slippage are simplified assumptions; prices are not rounded to exchange tick sizes. No dividends, corporate actions, taxes, intraday stops, short selling, or real fills. Open positions remain marked to the final close.")
