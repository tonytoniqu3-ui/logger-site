"""Même stratégie, MÊMES réglages que le robot or, sur les autres marchés du courtier (données MetaQuotes-Demo).
Règle fixée avant de regarder : retenu si positif sur les DEUX périodes ET t total >= 2."""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, ".")
from robot.simulateur import simuler  # noqa: E402
from robot.strategie import Config  # noqa: E402

POINT = {"XAUUSD": 0.01, "XAGUSD": 0.001, "US500": 0.01, "US30": 0.01, "USTEC": 0.01, "XPTUSD": 0.001,
         "XPDUSD": 0.001, "COPPER": 0.01, "UK100": 0.1}
SPLIT = pd.Timestamp("2026-03-01")
rows = []
for s, pt in POINT.items():
    d = pd.read_csv(f"data/metaquotes/{s}_M5.csv", parse_dates=["date"]).set_index("date").sort_index()
    d["spr"] = d["spread"] * pt
    tr, _ = simuler(d, Config(), solde=1e9, risque=0.01, risque_max=1.0, eurusd=1.0)  # solde énorme : pas de trade sauté
    a, b = tr[tr.t < SPLIT], tr[tr.t >= SPLIT]
    t = tr.r.mean() / (tr.r.std(ddof=1) / np.sqrt(len(tr)))
    ok = len(a) > 20 and len(b) > 20 and a.r.mean() > 0 and b.r.mean() > 0 and t >= 2
    rows.append({"marché": s, "début": d.index[0].date(), "trades": len(tr), "conception": a.r.mean(), "n_c": len(a),
                 "contrôle": b.r.mean(), "n_ctl": len(b), "total": tr.r.mean(), "t": t,
                 "spread_médian_en_%_du_range": (d.spr.median() / tr.w.median()) * 100, "retenu": ok})
r = pd.DataFrame(rows)
pd.set_option("display.width", 200)
print(r.round(3).to_string(index=False))
r.to_csv("recherche/autres_marches.csv", index=False)
