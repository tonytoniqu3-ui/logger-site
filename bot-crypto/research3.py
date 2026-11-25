"""Recherche n°3 : portefeuille BTC + ETH (50/50), bougies journalières. Choix sur l'entraînement, vérification hors échantillon."""
import itertools, warnings
import numpy as np, pandas as pd
from botcrypto import backtest as bt
from botcrypto.data import load_or_fetch
from botcrypto.strategies import STRATEGIES
warnings.filterwarnings("ignore")
D = {p: load_or_fetch(p, "1d", 3400) for p in ("BTC-EUR", "ETH-EUR")}
idx = D["BTC-EUR"].index.intersection(D["ETH-EUR"].index)
D = {p: d.loc[idx] for p, d in D.items()}
cut = int(len(idx) * 0.7)
print("entraînement :", idx[0].date(), "->", idx[cut-1].date(), "| caché :", idx[cut].date(), "->", idx[-1].date())
def port(sl, strat, prm, risk):
    eqs, trades = [], []
    for p, d in D.items():
        sig = STRATEGIES[strat](d, **prm)
        r = bt.run(d.iloc[sl], sig.iloc[sl], capital=50, risk=risk, timeframe="1d")
        eqs.append(r.equity); trades.append(r.trades)
    eq = sum(eqs); tr = pd.concat(trades)
    bh = sum(50 * d["close"].iloc[sl] / d["close"].iloc[sl].iloc[0] for d in D.values())
    m = bt.metrics(eq, tr, pd.DataFrame({"close": bh}), "1d")
    return m, tr, eq
rows = []
cands = [("donchian", {"entry": e, "exit": x}) for e, x in [(20, 10), (40, 20), (55, 20)]] + \
        [("ema_cross", {"fast": f, "slow": s}) for f, s in [(20, 50), (30, 100)]]
for (s, prm), rp in itertools.product(cands, [0.02, 0.03, 0.05]):
    risk = bt.Risk(atr_stop=3, risk_per_trade=rp, max_position=1, kill_drawdown=1)
    tm, _, _ = port(slice(0, cut), s, prm, risk)
    om, otr, _ = port(slice(cut, None), s, prm, risk)
    rows.append(dict(strat=s, params=str(prm), risk=rp, train=tm["rendement"], train_dd=tm["max_drawdown"], train_calmar=tm["calmar"],
                     oos=om["rendement"], oos_bh=om["acheter_garder"], oos_dd=om["max_drawdown"], oos_sharpe=om["sharpe"], oos_trades=om["trades"],
                     mc_p5=bt.monte_carlo(otr)["rendement_p5"]))
r = pd.DataFrame(rows).sort_values("train_calmar", ascending=False)
f = r.copy()
for c in ("train","train_dd","oos","oos_bh","oos_dd","mc_p5"): f[c] = (f[c]*100).round(1)
pd.set_option("display.width", 220)
print(f.round(2).to_string(index=False))
