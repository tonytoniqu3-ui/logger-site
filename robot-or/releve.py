"""Relevé de la semaine, en lecture seule (n'envoie aucun ordre). Double-clic : windows/5-releve-semaine.bat"""
import json
import sys
from pathlib import Path

import pandas as pd

ICI = Path(__file__).resolve().parent
ATTENDU_R = 0.08   # espérance mesurée sur la période de contrôle (mars -> novembre 2026), en R par trade


def lire_journal(path=ICI / "journal" / "journal.csv") -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame()
    j = pd.read_csv(path, sep=";", parse_dates=["heure_serveur"])
    return j


def releve(j: pd.DataFrame) -> str:
    if j.empty:
        return "Aucun journal pour l'instant : le robot n'a encore rien fait."
    fer = j[j.evenement == "POSITION FERMÉE"].copy()
    if fer.empty:
        return "Aucun trade terminé pour l'instant."
    det = fer.details.apply(json.loads)
    fer["gain"] = det.apply(lambda x: x["gain_eur"])
    fer["r"] = det.apply(lambda x: x["r"])
    fer["solde"] = det.apply(lambda x: x["solde"])
    fer["semaine"] = fer.heure_serveur.dt.strftime("%G-S%V")
    lignes = ["RELEVÉ DU ROBOT OR (compte démo)", ""]
    for sem, g in fer.groupby("semaine"):
        depart = g.solde.iloc[0] - g.gain.iloc[0]
        lignes.append(f"Semaine {sem} : {len(g)} trades, {int((g.gain > 0).sum())} gagnants, "
                      f"{g.gain.sum():+.2f} € ({g.gain.sum() / depart:+.1%}), solde {g.solde.iloc[-1]:.2f} €")
    n, moy = len(fer), fer.r.mean()
    lignes += ["", f"Depuis le début : {n} trades, {fer.gain.sum():+.2f} €, R moyen {moy:+.3f} (attendu environ {ATTENDU_R:+.2f})"]
    if n < 30:
        lignes.append(f"Trop tôt pour juger : il faut au moins 30 trades, idéalement 100 (encore {100 - n}).")
    elif n < 100:
        lignes.append(f"Tendance à confirmer : encore {100 - n} trades avant de trancher.")
    else:
        lignes.append("100 trades atteints : " + ("l'avantage tient." if moy >= 0.05 else
                      "l'avantage n'est pas confirmé, il faut arrêter ou revoir la stratégie."))
    return "\n".join(lignes)


if __name__ == "__main__":
    print(releve(lire_journal()))
    if len(sys.argv) < 2:
        input("\nAppuie sur Entrée pour fermer.")
