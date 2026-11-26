"""Exporte l'historique M5 de plusieurs marchés depuis MT5 (lecture seule, aucun ordre).
Double-clic : windows/7-exporter-donnees.bat. Résultat : export_donnees.zip à envoyer à Claude."""
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ICI = Path(__file__).resolve().parent
SYMBOLES = ["XAUUSD", "XAGUSD", "US500", "US30", "USTEC", "XPTUSD", "XPDUSD", "COPPER", "UK100"]


def exporter(mt5, dossier: Path, symboles=SYMBOLES, depuis=datetime(2018, 1, 1)) -> list[tuple[str, int, str]]:
    dossier.mkdir(parents=True, exist_ok=True)
    bilan = []
    for s in symboles:
        if not mt5.symbol_select(s, True):
            bilan.append((s, 0, "absent chez ce courtier"))
            continue
        rates = mt5.copy_rates_range(s, mt5.TIMEFRAME_M5, depuis, datetime.now(timezone.utc).replace(tzinfo=None))
        if rates is None or len(rates) == 0:
            rates = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_M5, 0, 500000)
        if rates is None or len(rates) == 0:
            bilan.append((s, 0, "pas d'historique"))
            continue
        df = pd.DataFrame(rates)
        df["date"] = pd.to_datetime(df["time"], unit="s")
        df[["date", "open", "high", "low", "close", "tick_volume", "spread"]].to_csv(dossier / f"{s}_M5.csv", index=False)
        info = mt5.symbol_info(s)
        bilan.append((s, len(df), f"{df.date.iloc[0]:%d/%m/%Y} -> {df.date.iloc[-1]:%d/%m/%Y}, point {info.point}, "
                                   f"contrat {info.trade_contract_size}"))
    pd.DataFrame(bilan, columns=["symbole", "bougies", "detail"]).to_csv(dossier / "bilan.csv", index=False)
    return bilan


def main():
    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("Le module MetaTrader5 manque : lance d'abord windows/1-installer.bat")
        sys.exit(2)
    if not mt5.initialize():
        print("MetaTrader 5 ne répond pas : ouvre-le et connecte-toi, puis relance.")
        sys.exit(2)
    ai = mt5.account_info()
    print(f"Courtier : {ai.server} · export en cours (cela peut prendre quelques minutes)...")
    dossier = ICI / "export"
    for s, n, detail in exporter(mt5, dossier):
        print(f"  {s:8s} {n:7d} bougies  {detail}")
    (dossier / "courtier.txt").write_text(f"{ai.server}\n", encoding="utf-8")
    mt5.shutdown()
    z = ICI / "export_donnees.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as f:
        for p in dossier.iterdir():
            f.write(p, p.name)
    print(f"\nTerminé : envoie le fichier {z} à Claude.")


if __name__ == "__main__":
    main()
