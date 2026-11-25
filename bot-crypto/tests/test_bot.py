import numpy as np
import pandas as pd
import pytest

from botcrypto import backtest as bt
from botcrypto import indicators as ind
from botcrypto.broker import PaperBroker
from botcrypto.data import drop_unclosed, synthetic_candles
from botcrypto.live import Bot
from botcrypto.strategies import STRATEGIES


@pytest.fixture
def df():
    return synthetic_candles(1500, seed=3)


@pytest.mark.parametrize("name", list(STRATEGIES))
def test_no_lookahead(df, name):
    """Le signal à t ne doit pas changer si on ajoute des bougies futures."""
    full = STRATEGIES[name](df)
    cut = STRATEGIES[name](df.iloc[:1000])
    assert (full.iloc[:1000] == cut).all()


def test_rsi_bounds(df):
    r = ind.rsi(df["close"]).dropna()
    assert r.between(0, 100).all()


def test_donchian_excludes_current_bar(df):
    up, _ = ind.donchian(df, 20)
    assert up.iloc[30] == df["high"].iloc[10:30].max()


def test_fees_cost_money(df):
    sig = STRATEGIES["ema_cross"](df)
    free = bt.run(df, sig, costs=bt.Costs(0, 0))
    paid = bt.run(df, sig, costs=bt.Costs())
    assert paid.metrics["rendement"] < free.metrics["rendement"]
    assert paid.metrics["frais_payes"] > 0


def test_flat_market_round_trip_loses_fees():
    idx = pd.date_range("2024", periods=50, freq="1h", tz="UTC")
    d = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1.0}, index=idx)
    sig = pd.Series([0] * 20 + [1] * 10 + [0] * 20, index=idx)
    r = bt.run(d, sig, costs=bt.Costs(fee=0.01, slippage=0), risk=bt.Risk(atr_stop=0))
    assert r.metrics["trades"] == 1
    assert r.equity.iloc[-1] == pytest.approx(100 * 0.99 * 0.99)


def test_atr_stop_and_kill_switch():
    idx = pd.date_range("2024", periods=60, freq="1h", tz="UTC")
    close = np.r_[np.full(30, 100.0), np.linspace(100, 40, 30)]
    d = pd.DataFrame({"open": close, "high": close + 0.5, "low": close - 0.5, "close": close, "volume": 1.0}, index=idx)
    sig = pd.Series(1, index=idx)
    with_stop = bt.run(d, sig, risk=bt.Risk(atr_stop=3, risk_per_trade=0.02, kill_drawdown=1))
    assert "stop" in set(with_stop.trades.reason)
    assert with_stop.metrics["max_drawdown"] > -0.06
    no_stop = bt.run(d, sig, risk=bt.Risk(atr_stop=0, kill_drawdown=0.2))
    assert no_stop.stopped and no_stop.metrics["max_drawdown"] >= -0.25


def test_monte_carlo_and_walk_forward(df):
    wf = bt.walk_forward(df, "donchian", {"entry": [20, 40]})
    assert wf["params"]["entry"] in (20, 40)
    assert isinstance(wf["valide"], bool)
    if len(wf["oos_result"].trades):
        assert 0 <= bt.monte_carlo(wf["oos_result"].trades)["proba_perte"] <= 1


def test_drop_unclosed():
    idx = pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC")
    d = pd.DataFrame({"open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}, index=idx)
    now = idx[-1].to_pydatetime() + pd.Timedelta(minutes=30)
    assert len(drop_unclosed(d, "1h", now)) == 2


RISK = {"atr_stop": 3, "risk_per_trade": 0.02, "max_position": 1, "kill_drawdown": 0.2}


def test_paper_bot_step(tmp_path, df):
    cfg = {"mode": "paper", "products": ["BTC-EUR"], "timeframe": "1h", "strategy": "buy_hold", "params": {},
           "min_order": 1, "risk": RISK}
    broker = PaperBroker("EUR", 100, path=str(tmp_path / "w.json"))
    bot = Bot(cfg, broker, state_dir=str(tmp_path))
    assert bot.step({"BTC-EUR": df.iloc[:300]})["BTC-EUR"] == "achat"
    assert bot.step({"BTC-EUR": df.iloc[:300]})["BTC-EUR"] == "rien de neuf"  # pas de double achat
    assert broker.balance("BTC") > 0 and broker.balance("EUR") < 100
    crash = df.iloc[:301].copy()
    crash.iloc[-1, crash.columns.get_loc("low")] = 1.0
    assert bot.step({"BTC-EUR": crash})["BTC-EUR"] == "stop touché"
    assert broker.balance("BTC") == 0


def test_two_products_share_capital(tmp_path):
    a, b = synthetic_candles(400, seed=1), synthetic_candles(400, seed=2, start_price=2000)
    cfg = {"mode": "paper", "products": ["BTC-EUR", "ETH-EUR"], "timeframe": "1h", "strategy": "buy_hold",
           "params": {}, "min_order": 1, "risk": {**RISK, "atr_stop": 0}}
    broker = PaperBroker("EUR", 100, fee=0, slippage=0, path=str(tmp_path / "w.json"))
    out = Bot(cfg, broker, state_dir=str(tmp_path)).step({"BTC-EUR": a, "ETH-EUR": b})
    assert out == {"BTC-EUR": "achat", "ETH-EUR": "achat"}
    # chaque paire reçoit au plus la moitié du capital
    assert broker.balance("BTC") * a["close"].iloc[-1] == pytest.approx(50)
    assert broker.balance("EUR") == pytest.approx(0)


def test_kill_switch_live(tmp_path):
    a = synthetic_candles(400, seed=1)
    cfg = {"mode": "paper", "products": ["BTC-EUR"], "timeframe": "1h", "strategy": "buy_hold", "params": {},
           "min_order": 1, "risk": {**RISK, "atr_stop": 0}}
    broker = PaperBroker("EUR", 100, fee=0, slippage=0, path=str(tmp_path / "w.json"))
    bot = Bot(cfg, broker, state_dir=str(tmp_path))
    bot.step({"BTC-EUR": a})
    crash = a.copy()
    crash.iloc[-1, crash.columns.get_loc("close")] *= 0.5
    assert "COUPE-CIRCUIT" in bot.step({"BTC-EUR": crash})["_"]
    assert broker.balance("BTC") == 0 and bot.state["halted"]
