"""Recherche n°2 : dimensionnement des positions. Choix sur l'ENTRAÎNEMENT (70 %), vérification unique hors échantillon."""
import itertools, warnings
import pandas as pd
from botcrypto import backtest as bt
from botcrypto.data import load_or_fetch
from botcrypto.strategies import STRATEGIES
warnings.filterwarnings("ignore")
RISKS = {
    "A_stop3ATR_2pct": bt.Risk(atr_stop=3, risk_per_trade=0.02, max_position=1, kill_drawdown=1),
    "B_stop3ATR_5pct": bt.Risk(atr_stop=3, risk_per_trade=0.05, max_position=1, kill_drawdown=1),
    "C_stop5ATR_5pct": bt.Risk(atr_stop=5, risk_per_trade=0.05, max_position=1, kill_drawdown=1),
    "D_sans_stop_100pct": bt.Risk(atr_stop=0, risk_per_trade=1, max_position=1, kill_drawdown=1),
}
GR = {"donchian": {"entry": [20, 40, 55], "exit": [10, 20]}, "ema_cross": {"fast": [10, 20, 30], "slow": [50, 100]},
      "trend": {"period": [100, 150, 200]}, "macd": {}}
rows = []
for tf, days in [("1d", 3400), ("6h", 1460)]:
    for pair in ["BTC-EUR", "ETH-EUR"]:
        df = load_or_fetch(pair, tf, days); cut = int(len(df) * 0.7)
        for (rname, risk), (s, grid) in itertools.product(RISKS.items(), GR.items()):
            best, bs = None, -9
            for combo in itertools.product(*grid.values()) if grid else [()]:
                prm = dict(zip(grid, combo)); sig = STRATEGIES[s](df, **prm)
                m = bt.run(df.iloc[:cut], sig.iloc[:cut], risk=risk, timeframe=tf).metrics
                sc = m["calmar"] if m["trades"] >= 5 else -9
                if sc > bs: best, bs, bm = prm, sc, m
            sig = STRATEGIES[s](df, **best)
            o = bt.run(df.iloc[cut:], sig.iloc[cut:], risk=risk, timeframe=tf).metrics
            rows.append(dict(tf=tf, pair=pair, risk=rname, strat=s, params=best, train=bm["rendement"], train_bh=bm["acheter_garder"],
                             train_calmar=bm["calmar"], train_dd=bm["max_drawdown"], oos=o["rendement"], oos_bh=o["acheter_garder"], oos_dd=o["max_drawdown"], oos_trades=o["trades"]))
r = pd.DataFrame(rows); r.to_csv("data/research2.csv", index=False)
pd.set_option("display.width", 220)
f = r.copy()
for c in ("train","train_bh","train_dd","oos","oos_bh","oos_dd"): f[c]=(f[c]*100).round(1)
f["train_calmar"]=f.train_calmar.round(2)
print("=== Classement sur l'ENTRAÎNEMENT (Calmar moyen) ===")
print(f.groupby(["tf","risk","strat"])[["train","train_calmar","train_dd"]].mean().round(2).sort_values("train_calmar",ascending=False).head(12))
print(f.to_string(index=False))
