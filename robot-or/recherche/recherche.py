"""8 schémas connus x 2 tailles de stop x avec/sans filtre de tendance = 32 configurations, fixées AVANT de regarder.
Sélection sur la conception (juin 2025 -> février 2026). Le contrôle (mars -> novembre 2026) n'est lu qu'à la fin."""
import itertools
import sys

import pandas as pd

sys.path.insert(0, "recherche")
from moteur import load, run, stats  # noqa: E402

H = lambda hh, mm=0: hh * 60 + mm  # noqa: E731
PATTERNS = {
    "A_asie_cassure":        [(H(1), H(3), H(21), "break")],
    "B_asie_avant_londres":  [(H(1), H(3), H(10), "break")],
    "C_londres_1h":          [(H(10), H(11), H(21), "break")],
    "D_newyork_30min":       [(H(16, 30), H(17), H(21), "break")],
    "E_preouverture_londres":[(H(3), H(10), H(21), "break")],
    "F_matinee_ny":          [(H(10), H(15), H(21), "break")],
    "G_veille_haut_bas":     [(0, H(3), H(21), "pdhl")],
    "H_faux_depart_asie":    [(H(1), H(3), H(15), "fade")],
}
STOPS = {"stop_range": (1.0, 2.0), "stop_demi": (0.5, 2.0)}
d = load()
rows = []
for (pn, win), (sn, (st, rr)), trend in itertools.product(PATTERNS.items(), STOPS.items(), (False, True)):
    t = run(d, {"windows": win, "stop": st, "rr": rr, "trend": trend})
    s = stats(t)
    rows.append({"schema": pn, "stop": sn, "tendance": trend, **s})
r = pd.DataFrame(rows)
r.to_csv("recherche/resultats_32.csv", index=False)
pd.set_option("display.width", 200)
cols = ["schema", "stop", "tendance", "n_concep", "esp_concep", "t_concep"]
print("=== CONCEPTION SEULE (juin 2025 -> février 2026) ===")
print(r[cols].round(3).sort_values("t_concep", ascending=False).to_string(index=False))
