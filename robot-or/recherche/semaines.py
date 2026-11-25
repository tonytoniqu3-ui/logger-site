"""Répartition des résultats par semaine (500 € de départ chaque semaine, en %), et effet d'un objectif hebdomadaire."""
import pandas as pd
import sys; sys.path.insert(0, ".")
from robot.simulateur import charger, simuler
from robot.strategie import Config

d = charger("data/XAUUSD_M5.csv")
rows = []
for obj in (None, 0.03, 0.05, 0.10):
    for risque in (0.02, 0.03):
        tr, wk = simuler(d, Config(), solde=500, risque=risque, risque_max=0.05, objectif_hebdo=obj, perte_max_hebdo=0.10)
        for per, w in (("tout", wk), ("contrôle", wk[wk.semaine >= "2026-S10"])):
            w = w[w.trades > 0]
            rows.append({"objectif": f"{obj:.0%}" if obj else "aucun", "risque": f"{risque:.0%}", "période": per,
                         "semaines": len(w), "gagnantes": f"{(w.pct > 0).mean():.0%}",
                         "moyenne": f"{w.pct.mean():+.1%}", "médiane": f"{w.pct.median():+.1%}",
                         "pire": f"{w.pct.min():+.1%}", "meilleure": f"{w.pct.max():+.1%}",
                         "solde_final": round(tr.solde.iloc[-1])})
print(pd.DataFrame(rows).to_string(index=False))
