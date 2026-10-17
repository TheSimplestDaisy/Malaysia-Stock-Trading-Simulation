import numpy as np
import pandas as pd
import pytest
from ai_trading_assistant.config import MARKETS, Settings
from ai_trading_assistant.data import generate_data
from ai_trading_assistant.indicators import indicators
from ai_trading_assistant.scanner import scan
from ai_trading_assistant.portfolio import Portfolio
from ai_trading_assistant.engine import Simulation

M = MARKETS['US Stocks']
D0, D1, D2 = pd.to_datetime(['2025-01-01', '2025-01-02', '2025-01-03'])


def portfolio(**kwargs):
    return Portfolio(M, Settings(**kwargs))


def test_synthetic_reproducible_valid():
    a, b = generate_data(M), generate_data(M)
    for s, f in a.items():
        pd.testing.assert_frame_equal(f, b[s])
        assert (f.high >= f[['open', 'close']].max(axis=1)).all()
        assert (f.low <= f[['open', 'close']].min(axis=1)).all()
        assert (f.low > 0).all() and (f.volume > 0).all()


@pytest.mark.parametrize('movement,expected', [(1, 100), (-1, 0), (0, 50)])
def test_rsi_edges(movement, expected):
    f = pd.DataFrame({'close': 100 + np.arange(30)*movement, 'volume': 100})
    result = indicators(f)
    assert result.rsi14.iloc[:14].isna().all()
    assert result.rsi14.iloc[-1] == expected
    assert result.volume_ratio.iloc[-1] == 1


def test_indicators_do_not_read_future():
    f = generate_data(M)[M.symbols[0]]
    pd.testing.assert_frame_equal(indicators(f).iloc[:40], indicators(f.iloc[:40]))


@pytest.mark.parametrize('row,held,expected', [
    ((11,10,60,1.5),False,'BUY'), ((9,10,45,1),True,'SELL'),
    ((11,10,60,1),True,'HOLD'), ((11,10,60,1),False,'NO TRADE'),
    ((11,10,80,2),True,'SELL'), ((np.nan,10,60,2),False,'NO TRADE')])
def test_signals(row, held, expected):
    signal, reason = scan(dict(zip(('ema9','ema21','rsi14','volume_ratio'),row)), held)
    assert signal == expected and reason


def test_accounting_fees_slippage_partial_sale():
    p = portfolio(initial_cash=10000, max_allocation=1, fee_rate=.01, minimum_fee=1, slippage=.01)
    assert p.execute('US_A','BUY',10,D1,D0,{'US_A':100})
    assert p.cash == pytest.approx(8979.9)
    assert p.positions['US_A'].cost == pytest.approx(1020.1)
    assert p.execute('US_A','SELL',5,D2,D1,{'US_A':120})
    assert p.realized == pytest.approx(594-5.94-510.05)
    equity = p.equity({'US_A':120})
    unrealized = 600-p.positions['US_A'].cost
    assert equity-10000 == pytest.approx(p.realized+unrealized)


def test_timing_duplicate_and_no_short():
    p = portfolio()
    assert not p.execute('US_A','BUY',1,D0,D0,{'US_A':100})
    assert p.execute('US_A','BUY',1,D2,D1,{'US_A':100})
    cash = p.cash
    assert not p.execute('US_A','BUY',1,D2,D1,{'US_A':100})
    assert p.cash == cash and len(p.trades) == 1
    assert not p.execute('US_A','SELL',2,D2,D1,{'US_A':100})


def test_lot_cash_allocation_and_position_limits():
    p = Portfolio(MARKETS['Bursa Malaysia'], Settings())
    assert not p.execute('BURSA_A','BUY',1,D1,D0,{'BURSA_A':5})
    assert p.execute('BURSA_A','BUY',100,D2,D1,{'BURSA_A':5})
    p = portfolio(max_positions=1)
    assert p.execute('US_A','BUY',1,D1,D0,{'US_A':100})
    assert not p.execute('US_B','BUY',1,D2,D1,{'US_A':100,'US_B':100})
    p = portfolio(initial_cash=1000)
    assert not p.execute('US_A','BUY',3,D1,D0,{'US_A':100})
    p = portfolio(initial_cash=1000, max_allocation=1)
    assert not p.execute('US_A','BUY',10,D1,D0,{'US_A':100})


def test_daily_loss_latches_but_allows_exit_and_resets_next_day():
    p = portfolio(initial_cash=10000,max_allocation=1)
    p.begin_day(D1,10000)
    assert p.execute('US_A','BUY',50,D1,D0,{'US_A':100})
    assert p.check_loss({'US_A':90})
    assert p.check_loss({'US_A':110})
    assert not p.execute('US_B','BUY',1,D2,D1,{'US_A':110,'US_B':100})
    assert p.execute('US_A','SELL',50,D2,D1,{'US_A':110})
    p.begin_day(D2,p.cash)
    assert not p.loss_locked


def test_emergency_stop_blocks_entry_allows_exit():
    p = portfolio()
    assert p.execute('US_A','BUY',1,D1,D0,{'US_A':100})
    p.emergency_stop = True
    assert not p.execute('US_B','BUY',1,D2,D1,{'US_A':100,'US_B':100})
    assert p.execute('US_A','SELL',1,D2,D1,{'US_A':100})
    p.begin_day(D2,p.cash)
    assert p.emergency_stop


def test_engine_next_open_stop_and_end_idempotency():
    sim = Simulation(M, Settings(), generate_data(M))
    sim.step()
    # Controlled prior-close signal: next open differs from next close.
    sim.pending = [('US_A','BUY',sim.dates[0])]
    sim.step()
    trade = sim.portfolio.trades[0]
    assert trade['date'] == sim.dates[1]
    assert trade['fill_price'] == pytest.approx(sim.data['US_A'].iloc[1]['open']*1.001)
    sim.pending = [('US_B','BUY',sim.dates[1]),('US_A','SELL',sim.dates[1])]
    sim.stop()
    assert [o[1] for o in sim.pending] == ['SELL']
    assert sim.portfolio.orders[-1]['status'] == 'CANCELLED'
    sim.step()
    assert not sim.portfolio.positions
    sim.run()
    size = len(sim.history)
    assert not sim.step() and len(sim.history) == size


def test_market_isolation():
    a = Simulation(M,Settings(),generate_data(M))
    b = Simulation(MARKETS['Bursa Malaysia'],Settings(),generate_data(MARKETS['Bursa Malaysia']))
    a.run()
    assert b.portfolio.cash == 100000 and b.cursor == -1
    assert a.portfolio.market.currency == 'USD' and b.portfolio.market.currency == 'MYR'


def test_future_prices_cannot_change_past_trades():
    data = generate_data(M)
    altered = {s: f.copy() for s, f in data.items()}
    for f in altered.values():
        f.iloc[80:, f.columns.get_indexer(['open','high','low','close'])] *= 10
    a = Simulation(M, Settings(), data)
    b = Simulation(M, Settings(), altered)
    for _ in range(80):
        a.step()
        b.step()
    assert a.portfolio.trades == b.portfolio.trades
    assert a.history == b.history
    assert a.pending == b.pending


def test_minimum_fee_full_exit_and_sizing():
    p = portfolio(initial_cash=1000, max_allocation=1, fee_rate=0, minimum_fee=5, slippage=0)
    assert p.size('US_A', {'US_A':100}) == 9
    assert p.execute('US_A','BUY',9,D1,D0,{'US_A':100})
    assert p.execute('US_A','SELL',9,D2,D1,{'US_A':100})
    assert p.cash == 990 and p.realized == -10 and not p.positions


def test_gap_loss_rechecked_before_pending_buy():
    sim = Simulation(M, Settings(max_allocation=1), generate_data(M))
    sim.step()
    p = sim.portfolio
    assert p.execute('US_A','BUY',1000,D1,D0,{'US_A':50})
    sim.history[-1]['equity'] = p.equity({'US_A':50})
    date = sim.dates[1]
    sim.data['US_A'].loc[date, 'open'] = 40
    sim.pending = [('US_B','BUY',sim.dates[0])]
    sim.step()
    assert 'US_B' not in p.positions
    assert p.orders[-1]['reason'] == 'Daily equity loss limit reached'


def test_dashboard_smoke():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'app.py').run(timeout=30)
    assert not app.exception
    next(b for b in app.button if b.label == 'Next session').click().run(timeout=30)
    assert not app.exception
    next(b for b in app.button if b.label == 'Run remaining sessions').click().run(timeout=30)
    assert not app.exception
