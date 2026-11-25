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
           "capital": 100, "min_order": 1, "risk": RISK}
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
           "params": {}, "capital": 100, "min_order": 1, "risk": {**RISK, "atr_stop": 0}}
    broker = PaperBroker("EUR", 100, fee=0, slippage=0, path=str(tmp_path / "w.json"))
    out = Bot(cfg, broker, state_dir=str(tmp_path)).step({"BTC-EUR": a, "ETH-EUR": b})
    assert out == {"BTC-EUR": "achat", "ETH-EUR": "achat"}
    # chaque paire reçoit au plus la moitié du capital
    assert broker.balance("BTC") * a["close"].iloc[-1] == pytest.approx(50)
    assert broker.balance("EUR") == pytest.approx(0)


def test_bot_never_touches_other_funds(tmp_path):
    """Compte avec 1 000 € et 1 BTC personnels : le bot ne gère que ses 100 € et ce qu'il achète."""
    a = synthetic_candles(400, seed=1)
    cfg = {"mode": "paper", "products": ["BTC-EUR"], "timeframe": "1h", "strategy": "buy_hold", "params": {},
           "capital": 100, "min_order": 1, "risk": {**RISK, "atr_stop": 0}}
    broker = PaperBroker("EUR", 1000, fee=0, slippage=0, path=str(tmp_path / "w.json"))
    broker.wallet["BTC"] = 1.0
    bot = Bot(cfg, broker, state_dir=str(tmp_path))
    bot.step({"BTC-EUR": a})
    assert broker.balance("EUR") == pytest.approx(900)  # il n'a dépensé que son budget
    crash = a.copy()
    crash.iloc[-1, crash.columns.get_loc("close")] *= 0.5
    bot.step({"BTC-EUR": crash})  # coupe-circuit : il revend SEULEMENT ce qu'il a acheté
    assert broker.balance("BTC") == pytest.approx(1.0)
    assert bot.state["halted"]


def test_coinbase_broker_with_fake_client():
    from botcrypto.broker import CoinbaseBroker

    class Fake:
        def __init__(self):
            self.orders = []
        def get_product(self, p):
            return {"base_increment": "0.00000001", "quote_increment": "0.01"}
        def get_accounts(self, limit=250, cursor=None):
            return {"accounts": [{"currency": "BTC", "available_balance": {"value": "0.5"}}], "has_next": False}
        def market_order_buy(self, **k):
            self.orders.append(("buy", k))
            return {"success": True, "success_response": {"order_id": "1"}}
        def market_order_sell(self, **k):
            self.orders.append(("sell", k))
            return {"success": True, "success_response": {"order_id": "2"}}
        def get_order(self, oid):
            return {"order": {"status": "FILLED", "filled_size": "0.001", "filled_value": "50", "total_fees": "0.3",
                              "average_filled_price": "50000"}}

    f = Fake()
    b = CoinbaseBroker("EUR", ["BTC-EUR"], client=f)
    assert b.buy("BTC-EUR", 50.123, 50000)["qty"] == pytest.approx(0.001)
    assert f.orders[0][1]["quote_size"] == "50.12"
    r = b.sell("BTC-EUR", 0.001, 50000)
    assert r["proceeds"] == pytest.approx(49.7)
    assert f.orders[1][1]["base_size"] == "0.00100000"
    assert b.sell("BTC-EUR", 2.0, 50000) and f.orders[2][1]["base_size"] == "0.50000000"  # plafonné au solde


def test_kill_switch_live(tmp_path):
    a = synthetic_candles(400, seed=1)
    cfg = {"mode": "paper", "products": ["BTC-EUR"], "timeframe": "1h", "strategy": "buy_hold", "params": {},
           "capital": 100, "min_order": 1, "risk": {**RISK, "atr_stop": 0}}
    broker = PaperBroker("EUR", 100, fee=0, slippage=0, path=str(tmp_path / "w.json"))
    bot = Bot(cfg, broker, state_dir=str(tmp_path))
    bot.step({"BTC-EUR": a})
    crash = a.copy()
    crash.iloc[-1, crash.columns.get_loc("close")] *= 0.5
    assert "COUPE-CIRCUIT" in bot.step({"BTC-EUR": crash})["_"]
    assert broker.balance("BTC") == 0 and bot.state["halted"]


class FakeNotifier:
    def __init__(self):
        self.msgs = []

    def send(self, text):
        self.msgs.append(text)
        return True


def test_notifications(tmp_path):
    a = synthetic_candles(400, seed=1)
    cfg = {"mode": "paper", "products": ["BTC-EUR"], "timeframe": "1h", "strategy": "buy_hold", "params": {},
           "capital": 100, "min_order": 1, "risk": RISK}
    n = FakeNotifier()
    bot = Bot(cfg, PaperBroker("EUR", 100, path=str(tmp_path / "w.json")), state_dir=str(tmp_path), notifier=n)
    bot.step({"BTC-EUR": a})
    assert any("ACHAT BTC-EUR" in m and "SIMULATION" in m for m in n.msgs)
    assert sum("Bilan" in m for m in n.msgs) == 1
    bot.step({"BTC-EUR": a})
    assert sum("Bilan" in m for m in n.msgs) == 1  # un seul bilan par jour


def test_telegram_disabled_and_failing():
    from botcrypto.notify import Telegram
    assert Telegram(token="", chat_id="").send("x") is False

    class Boom:
        def post(self, *a, **k):
            raise ConnectionError("réseau coupé")
    assert Telegram(token="t", chat_id="1", session=Boom()).send("x") is False
