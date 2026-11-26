"""Lance le robot or sur MetaTrader 5 (compte DÉMO uniquement). Double-clic : windows/3-lancer-robot.bat"""
import json
import os
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
from robot.mt5_robot import Robot, Stop  # noqa: E402


def lire_env():
    f = ICI / ".env"
    if f.exists():
        for ligne in f.read_text(encoding="utf-8").splitlines():
            if "=" in ligne and not ligne.lstrip().startswith("#"):
                k, v = ligne.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def telegram():
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return None
    import urllib.parse
    import urllib.request

    def envoyer(texte):
        try:
            data = urllib.parse.urlencode({"chat_id": chat, "text": texte[:4000]}).encode()
            urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=10)
        except Exception as e:  # une alerte ratée n'arrête jamais le robot
            print("Telegram indisponible :", e)
    return envoyer


def main():
    lire_env()
    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("Le module MetaTrader5 manque : lance d'abord windows/1-installer.bat")
        sys.exit(2)
    cfg = json.loads((ICI / "config.json").read_text(encoding="utf-8"))
    robot = Robot(cfg, mt5, dossier=str(ICI), notifier=telegram())
    try:
        robot.tourner(cfg.get("pause_secondes", 5))
    except Stop as e:
        print("\n*** ROBOT ARRÊTÉ :", e)
        sys.exit(2)
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
