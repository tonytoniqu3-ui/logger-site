import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from robot.mt5_robot import Robot, Stop  # noqa: E402
from robot.simulateur import charger, simuler  # noqa: E402
from robot.strategie import Bar, Config, Strategie, taille_position  # noqa: E402
from tests.faux_mt5 import FauxMT5  # noqa: E402

D = charger(str(Path(__file__).resolve().parents[1] / "data" / "XAUUSD_M5.csv"))
CFG = {"symbole": "XAUUSD", "risque": 0.03, "risque_max": 0.05, "perte_max_jour": 0.10, "perte_max_semaine": 0.10,
       "objectif_semaine": None, "historique_bougies": 5000, "strategie": {}}


def test_taille_position():
    lots, why = taille_position(500, 2000, 0.03, 0.05)  # 0,01 lot = 20 € = 4 % : accepté (< 5 %)
    assert lots == 0.01 and "lot minimum" in why
    assert taille_position(5000, 1000, 0.03, 0.05)[0] == 0.15
    lots, why = taille_position(500, 3000, 0.03, 0.05)  # 0,01 lot = 30 € = 6 % > 5 %
    assert lots == 0 and "trop large" in why


def bars(jour, rows):
    return [Bar(datetime.fromisoformat(f"{jour} {t}"), o, h, l, c) for t, o, h, l, c in rows]


def test_strategie_arme_a_la_fin_du_range_et_ferme_a_21h():
    s = Strategie(Config(tendance=False, sessions=[("Asie", "01:00", "03:00")]))
    cmds = []
    t = pd.date_range("2026-01-05 01:00", "2026-01-05 21:00", freq="5min")
    for k, ts in enumerate(t):
        hi = 110 if ts.hour == 2 and ts.minute == 0 else 105
        lo = 95 if ts.hour == 1 and ts.minute == 30 else 100
        cmds += [(ts, c) for c in s.on_bar(Bar(ts.to_pydatetime(), 102, hi, lo, 103))]
    armer = [c for ts, c in cmds if c["type"] == "armer"]
    assert len(armer) == 1 and armer[0]["haut"] == 110 and armer[0]["bas"] == 95 and armer[0]["cotes"] == (1, -1)
    assert [ts for ts, c in cmds if c["type"] == "armer"][0] == pd.Timestamp("2026-01-05 02:55")
    assert [ts for ts, c in cmds if c["type"] == "fermer"][0] == pd.Timestamp("2026-01-05 20:55")


def test_filtre_de_tendance_un_seul_cote():
    s = Strategie(Config(tendance=True, ema_bougies=10, sessions=[("Asie", "01:00", "03:00")]))
    out = []
    for ts in pd.date_range("2026-01-05 01:00", "2026-01-05 03:00", freq="5min", inclusive="left"):
        p = 100 + (ts - pd.Timestamp("2026-01-05")).total_seconds() / 3600  # prix qui monte
        out += s.on_bar(Bar(ts.to_pydatetime(), p, p + 0.5, p - 0.5, p))
    assert out[0]["cotes"] == (1,)


def test_refuse_un_compte_reel(tmp_path):
    rb = Robot(CFG, FauxMT5(D, 6000, demo=False), dossier=str(tmp_path), log=lambda *a: None)
    with pytest.raises(Stop, match="PAS UN COMPTE DÉMO"):
        rb.connecter()


def test_refuse_si_le_compte_devient_reel_en_cours(tmp_path):
    fx = FauxMT5(D, 6000)
    rb = Robot(CFG, fx, dossier=str(tmp_path), log=lambda *a: None)
    rb.connecter(); rb.rechauffer(); rb.tour()
    fx.mode = fx.ACCOUNT_TRADE_MODE_REAL
    with pytest.raises(Stop):
        rb.tour()


def faire_tourner(tmp_path, i0, i1, cfg=CFG, avant_tour=None):
    fx = FauxMT5(D, i0)
    rb = Robot(cfg, fx, dossier=str(tmp_path), log=lambda *a: None)
    rb.connecter(); rb.rechauffer()
    while fx.i < i1:
        if avant_tour:
            avant_tour(fx, rb)
        rb.tour()
        fx.avancer()
    return fx, rb, pd.read_csv(tmp_path / "journal" / "journal.csv", sep=";")


def test_robot_identique_au_simulateur(tmp_path):
    i0, i1 = 8000, 20000
    fx, rb, j = faire_tourner(tmp_path, i0, i1)
    fer = j[j.evenement == "POSITION FERMÉE"].details.apply(json.loads)
    tr, _ = simuler(D.iloc[:i1], Config(), solde=500, risque=0.03, risque_max=0.05)
    tr = tr[tr.t >= D.index[i0]]
    assert len(fer) == len(tr) > 20
    assert fer.apply(lambda x: x["r"]).mean() == pytest.approx(tr.r.mean(), abs=0.01)


def test_jamais_de_position_apres_21h(tmp_path):
    i0, i1 = 8000, 14000
    vu = []

    def controle(fx, rb):
        t = pd.Timestamp(fx.T[fx.i], unit="s")
        if t.hour * 60 + t.minute >= 21 * 60 + 5 and fx.positions:
            vu.append(t)
    faire_tourner(tmp_path, i0, i1, avant_tour=controle)
    assert vu == []


def test_fichier_pause(tmp_path):
    (tmp_path / "PAUSE.flag").write_text("")
    fx, rb, j = faire_tourner(tmp_path, 8000, 11000)
    assert "POSITION OUVERTE" not in set(j.evenement)
    assert "PAUSE" in set(j.evenement)


def test_releve(tmp_path):
    import releve
    fx, rb, j = faire_tourner(tmp_path, 8000, 14000)
    txt = releve.releve(releve.lire_journal(tmp_path / "journal" / "journal.csv"))
    assert "Semaine" in txt and "R moyen" in txt
