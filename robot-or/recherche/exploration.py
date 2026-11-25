"""EXPLORATOIRE (le contrôle a déjà été vu) : entrée au niveau par ordres en attente."""
import sys
import pandas as pd
sys.path.insert(0, "recherche")
from moteur import load, run, stats  # noqa: E402
d = load()
A, F = (60, 180, 21 * 60, "break"), (600, 900, 21 * 60, "break")
rows = []
for nm, win in (("Asie", [A]), ("New York", [F]), ("Asie + New York", [A, F])):
    for entry in ("cloture", "niveau"):
        for trend in (False, True):
            s = stats(run(d, {"windows": win, "stop": 1.0, "rr": 2.0, "trend": trend, "entry": entry}))
            rows.append({"séances": nm, "entrée": entry, "tendance": trend, "n": s["n"],
                         "concep": s["esp_concep"], "t_concep": s["t_concep"], "contrôle": s["esp_controle"],
                         "t_contrôle": s["t_controle"], "total": s["esp"], "t_total": s["t"]})
print(pd.DataFrame(rows).round(3).to_string(index=False))
