"""Recherche : toutes les stratégies x paires x tailles de bougies, jugées hors échantillon (30 % récents)."""
import sys
import warnings

import pandas as pd

from bot import GRIDS
from botcrypto import backtest as bt
from botcrypto.data import load_or_fetch

warnings.filterwarnings("ignore")
PAIRS = ["BTC-EUR", "ETH-EUR", "SOL-EUR", "XRP-EUR", "ADA-EUR", "DOGE-EUR"]
TF = {"1h": 730, "6h": 1460, "1d": 3400}
rows = []
for tf, days in TF.items():
    for p in PAIRS:
        df = load_or_fetch(p, tf, days)
        for s in GRIDS:
            wf = bt.walk_forward(df, s, GRIDS[s], timeframe=tf)
            m = wf["out_of_sample"]
            rows.append({"tf": tf, "paire": p, "strat": s, "params": wf["params"], "oos": m["rendement"],
                         "bh": m["acheter_garder"], "dd": m["max_drawdown"], "sharpe": m["sharpe"],
                         "trades": m["trades"], "pf": m.get("profit_factor", 0), "valide": wf["valide"]})
        print(tf, p, "ok", file=sys.stderr, flush=True)
r = pd.DataFrame(rows)
r.to_csv("data/research.csv", index=False)
pd.set_option("display.width", 200)
fmt = r.copy()
for c in ("oos", "bh", "dd"):
    fmt[c] = (fmt[c] * 100).round(1)
print(fmt.drop(columns="params").to_string(index=False))
print("\nMoyenne hors échantillon par stratégie et taille de bougie (%):")
print((r.groupby(["tf", "strat"])[["oos", "bh"]].mean() * 100).round(1).unstack(0))
print("\nValidées :", r.valide.sum(), "/", len(r))
