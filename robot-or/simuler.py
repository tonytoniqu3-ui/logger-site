"""Rejoue la stratégie du robot sur l'historique M5 et affiche le résultat semaine par semaine."""
import json
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
from robot.simulateur import charger, simuler  # noqa: E402
from robot.strategie import Config  # noqa: E402

cfg = json.loads((ICI / "config.json").read_text(encoding="utf-8"))
d = charger(str(ICI / "data" / "XAUUSD_M5.csv"))
tr, wk = simuler(d, Config.from_dict(cfg["strategie"]), solde=500, risque=cfg["risque"], risque_max=cfg["risque_max"],
                 objectif_hebdo=cfg.get("objectif_semaine"), perte_max_hebdo=cfg["perte_max_semaine"],
                 perte_max_jour=cfg["perte_max_jour"])
wk = wk[wk.trades > 0]
print(wk[["semaine", "trades", "debut", "fin", "pct"]].round(3).to_string(index=False))
print(f"\n{len(tr)} trades, R moyen {tr.r.mean():+.3f}, semaines gagnantes {(wk.pct > 0).mean():.0%}, "
      f"moyenne {wk.pct.mean():+.1%} par semaine, pire {wk.pct.min():+.1%}, meilleure {wk.pct.max():+.1%}")
print(f"Solde : 500 € -> {tr.solde.iloc[-1]:.2f} € (historique {d.index[0]:%d/%m/%Y} -> {d.index[-1]:%d/%m/%Y})")
if len(sys.argv) < 2:
    input("\nAppuie sur Entrée pour fermer.")
