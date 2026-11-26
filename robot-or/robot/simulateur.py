"""Simulateur : rejoue l'historique M5 avec EXACTEMENT la stratégie et les règles d'ordres du robot MT5.

Exécution réaliste : prix des bougies = bid ; un achat se fait au ask (bid + spread).
Ordre stop d'achat déclenché quand le ask touche le niveau, ordre stop de vente quand le bid le touche.
Si l'ouverture saute le niveau, on est exécuté à l'ouverture (pire prix). Stop prioritaire sur l'objectif.
"""
from __future__ import annotations

import pandas as pd

from .strategie import Bar, Config, Strategie, taille_position

CONTRAT = 100.0  # onces par lot sur XAUUSD


def charger(path: str) -> pd.DataFrame:
    d = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    d["spr"] = d["spread"] * 0.01
    return d


def simuler(d: pd.DataFrame, cfg: Config, solde: float = 500.0, risque: float = 0.03, risque_max: float = 0.05,
            eurusd: float = 1.15, objectif_hebdo: float | None = None, perte_max_hebdo: float | None = None,
            perte_max_jour: float = 0.10) -> tuple[pd.DataFrame, pd.DataFrame]:
    strat = Strategie(cfg)
    flat = strat.flat
    attente = {}      # session -> ordre en attente {"cotes","haut","bas","w"}
    pos = None        # position ouverte
    trades, semaines = [], {}
    solde0_semaine = solde0_jour = solde
    semaine = jour = None
    pause_semaine = pause_jour = False
    O, H, L, C, S = (d[k].values for k in ("open", "high", "low", "close", "spr"))
    T = d.index
    for i in range(len(d)):
        t = T[i]
        m = t.hour * 60 + t.minute
        wk = t.isocalendar()[:2]
        if wk != semaine:
            if semaine is not None:
                semaines[semaine]["fin"] = solde
            semaine, solde0_semaine, pause_semaine = wk, solde, False
            semaines[wk] = {"debut": solde, "fin": solde, "trades": 0}
        if t.date() != jour:
            jour, solde0_jour, pause_jour = t.date(), solde, False
        o, h, l, c, s = O[i], H[i], L[i], C[i], S[i]

        # 1) la position ouverte : 21:00, stop, objectif
        vient_de_fermer = False
        if pos is not None:
            px = None
            if m >= flat:
                px = o if pos["cote"] == 1 else o + s
                why = "fermeture 21h"
            else:
                lo, hi = (l, h) if pos["cote"] == 1 else (l + s, h + s)
                if (pos["cote"] == 1 and lo <= pos["sl"]) or (pos["cote"] == -1 and hi >= pos["sl"]):
                    px, why = pos["sl"], "stop"
                elif i > pos["i"] and ((pos["cote"] == 1 and hi >= pos["tp"]) or (pos["cote"] == -1 and lo <= pos["tp"])):
                    px, why = pos["tp"], "objectif"
            if px is not None:
                r = pos["cote"] * (px - pos["entree"]) / pos["risque_prix"]
                eur = pos["cote"] * (px - pos["entree"]) * pos["lots"] * CONTRAT / eurusd
                solde += eur
                trades.append({**{k: pos[k] for k in ("t", "session", "cote", "entree", "lots", "w")},
                               "sortie": t, "prix_sortie": px, "raison": why, "r": r, "eur": eur, "solde": solde})
                semaines[semaine]["trades"] += 1
                pos, vient_de_fermer = None, True
                if solde <= solde0_jour * (1 - perte_max_jour):
                    pause_jour, attente = True, {}
                if objectif_hebdo is not None and solde >= solde0_semaine * (1 + objectif_hebdo):
                    pause_semaine, attente = True, {}
                if perte_max_hebdo is not None and solde <= solde0_semaine * (1 - perte_max_hebdo):
                    pause_semaine, attente = True, {}

        # 2) les ordres en attente (seulement sans position, avant 21:00)
        if pos is None and attente and m < flat and not vient_de_fermer:
            for nom in list(attente):
                od = attente[nom]
                up, dn = h + s >= od["haut"], l <= od["bas"]
                if not (up or dn):
                    continue
                if up and dn:
                    del attente[nom]          # bougie ambiguë : on s'abstient
                    continue
                cote = 1 if up else -1
                if cote not in od["cotes"]:
                    del attente[nom]          # cassure du mauvais côté : séance annulée
                    continue
                niveau = od["haut"] if up else od["bas"]
                fill = max(niveau, o + s) if up else min(niveau, o)
                del attente[nom]
                if not strat.prix_entree_ok(cote, niveau, fill, od["w"]):
                    continue
                perte_lot = od["w"] * CONTRAT / eurusd
                lots, _ = taille_position(solde, perte_lot, risque, risque_max)
                if lots <= 0:
                    continue
                pos = {"t": t, "i": i, "session": nom, "cote": cote, "entree": fill, "w": od["w"], "lots": lots,
                       "risque_prix": od["w"], "sl": fill - cote * od["w"], "tp": fill + cote * cfg.rr * od["w"]}
                # la bougie de déclenchement peut déjà toucher le stop
                lo, hi = (l, h) if cote == 1 else (l + s, h + s)
                if (cote == 1 and lo <= pos["sl"]) or (cote == -1 and hi >= pos["sl"]):
                    r_eur = -od["w"] * lots * CONTRAT / eurusd
                    solde += r_eur
                    trades.append({**{k: pos[k] for k in ("t", "session", "cote", "entree", "lots", "w")},
                                   "sortie": t, "prix_sortie": pos["sl"], "raison": "stop", "r": -1.0, "eur": r_eur,
                                   "solde": solde})
                    semaines[semaine]["trades"] += 1
                    pos = None
                    continue
                break

        # 3) la stratégie voit la bougie clôturée
        for cmd in strat.on_bar(Bar(t.to_pydatetime(), o, h, l, c, s)):
            if cmd["type"] == "armer" and not pause_jour and not pause_semaine:
                attente[cmd["session"]] = cmd
            elif cmd["type"] == "fermer":
                attente = {}
    if semaine is not None:
        semaines[semaine]["fin"] = solde
    tr = pd.DataFrame(trades)
    wk = pd.DataFrame([{"semaine": f"{a}-S{b:02d}", **v} for (a, b), v in semaines.items()])
    if len(wk):
        wk["eur"] = wk.fin - wk.debut
        wk["pct"] = wk.eur / wk.debut
    return tr, wk
