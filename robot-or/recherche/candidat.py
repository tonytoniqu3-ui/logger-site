"""Candidat fixé AVANT le contrôle : Asie (1-3 h) + matinée de New York (10-15 h), cassure à la clôture,
stop = largeur du range, objectif = 2 x le risque, une position à la fois, tout fermé à 21 h."""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "recherche")
from moteur import load, run, stats, SPLIT  # noqa: E402

SPEC = {"windows": [(60, 180, 21 * 60, "break"), (600, 900, 21 * 60, "break")], "stop": 1.0, "rr": 2.0, "trend": False}
d = load()
t = run(d, SPEC)
s = stats(t)
print("CONCEPTION : n=%d  esp %+.3f R  t=%.2f" % (s["n_concep"], s["esp_concep"], s["t_concep"]))
print("CONTRÔLE   : n=%d  esp %+.3f R  t=%.2f" % (s["n_controle"], s["esp_controle"], s["t_controle"]))
print("TOTAL      : n=%d  esp %+.3f R  t=%.2f  réussite %.1f %%" % (s["n"], s["esp"], s["t"], 100 * s["reussite"]))
t.to_csv("recherche/candidat_trades.csv", index=False)
