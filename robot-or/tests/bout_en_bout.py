"""Fait tourner le VRAI robot MT5 sur le faux MT5 pendant ~3 mois et compare au simulateur."""
import sys, tempfile, time
sys.path.insert(0, ".")
import pandas as pd
from robot.mt5_robot import Robot, MAGIC
from robot.simulateur import charger, simuler
from robot.strategie import Config
from tests.faux_mt5 import FauxMT5

d = charger("data/XAUUSD_M5.csv")
i0, i1 = int(sys.argv[1]) if len(sys.argv) > 1 else 8000, int(sys.argv[2]) if len(sys.argv) > 2 else 26000
CFG = {"symbole": "XAUUSD", "risque": 0.03, "risque_max": 0.05, "perte_max_jour": 0.10, "perte_max_semaine": 0.10,
       "objectif_semaine": None, "historique_bougies": 5000, "strategie": {}}
fx = FauxMT5(d, i0)
with tempfile.TemporaryDirectory() as tmp:
    rb = Robot(CFG, fx, dossier=tmp, log=lambda *a: None)
    rb.connecter(); rb.rechauffer()
    t0 = time.time()
    while fx.i < i1:
        rb.tour()
        fx.avancer()
    j = pd.read_csv(f"{tmp}/journal/journal.csv", sep=";")
print("durée %.0f s" % (time.time() - t0))
ouv = j[j.evenement == "POSITION OUVERTE"]
fer = j[j.evenement == "POSITION FERMÉE"]
print(j.evenement.value_counts().to_dict())
r_robot = fer.details.apply(lambda x: pd.read_json(pd.io.common.StringIO(x), typ="series")["r"])
# simulateur sur la même période (historique complet pour la tendance)
tr, _ = simuler(d.iloc[:i1], Config(), solde=500, risque=0.03, risque_max=0.05)
tr = tr[tr.t >= d.index[i0]]
print("ROBOT      : %d trades, R moyen %+.3f, solde final %.2f €" % (len(r_robot), r_robot.mean(), fx.solde))
print("SIMULATEUR : %d trades, R moyen %+.3f" % (len(tr), tr.r.mean()))
ent_robot = set(pd.to_datetime(ouv.heure_serveur).dt.floor("5min") - pd.Timedelta(minutes=5))
ent_sim = set(tr.t)
commun = len(ent_robot & ent_sim)
print("entrées communes : %d (robot %d, simulateur %d)" % (commun, len(ent_robot), len(ent_sim)))
