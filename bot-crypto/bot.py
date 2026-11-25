"""Point d'entrée : python bot.py <commande> [options]

  backtest   teste une stratégie sur l'historique (avec frais) et la compare à acheter-et-garder
  compare    teste toutes les stratégies d'un coup
  validate   optimise sur 70 % des données, juge sur 30 % jamais vues + Monte-Carlo
  portfolio  teste la configuration complète (toutes les paires de config.json, capital partagé)
  paper      fait tourner le bot en direct avec de l'argent fictif
  live       fait tourner le bot avec de l'argent réel (Coinbase) — après des semaines de paper !
  telegram   vérifie les alertes Telegram (et trouve ton TELEGRAM_CHAT_ID)
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

from botcrypto import backtest as bt
from botcrypto.data import load_or_fetch, synthetic_candles
from botcrypto.strategies import STRATEGIES

GRIDS = {
    "ema_cross": {"fast": [10, 20, 30], "slow": [50, 100]},
    "rsi_dip": {"low": [25, 30, 35], "high": [50, 60]},
    "donchian": {"entry": [20, 40, 55], "exit": [10, 20]},
    "macd": {},
    "trend": {"period": [100, 150, 200]},
    "bollinger": {},
    "buy_hold": {},
}


def load_env(path=".env"):
    if Path(path).exists():
        for line in Path(path).read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def get_data(cfg, args):
    if args.demo:
        print("[démo] données SYNTHÉTIQUES : les résultats ne disent rien du vrai marché.")
        return synthetic_candles(args.bars)
    return load_or_fetch(cfg["product"], cfg["timeframe"], args.days or (3400 if cfg["timeframe"] == "1d" else 730))


def pct(x):
    return f"{x*100:+.1f} %" if isinstance(x, (int, float)) else str(x)


def show(title, m):
    print(f"\n== {title} ==")
    for k in ("rendement", "acheter_garder", "max_drawdown", "sharpe", "calmar", "trades", "taux_gain",
              "profit_factor", "frais_payes"):
        if k in m:
            v = m[k]
            txt = pct(v) if k in ("rendement", "acheter_garder", "max_drawdown", "taux_gain") else (
                f"{v:.2f}" if isinstance(v, float) else v)
            print(f"  {k:<15} {txt}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["backtest", "compare", "validate", "portfolio", "paper", "live", "telegram"])
    p.add_argument("--config", default="config.json")
    p.add_argument("--strategy")
    p.add_argument("--days", type=int, default=0, help="jours d'historique (défaut : 3400 en 1d, 730 sinon)")
    p.add_argument("--product", help="une seule paire, par ex. ETH-EUR")
    p.add_argument("--demo", action="store_true", help="données synthétiques, sans internet")
    p.add_argument("--bars", type=int, default=6000)
    p.add_argument("--yes-real-money", action="store_true")
    args = p.parse_args()
    load_env()
    cfg = json.loads(Path(args.config).read_text())
    cfg.setdefault("products", [cfg.get("product", "BTC-EUR")])
    cfg["product"] = args.product or cfg["products"][0]
    if args.strategy:
        cfg["strategy"], cfg["params"] = args.strategy, {}
    costs, risk = bt.Costs(**cfg["costs"]), bt.Risk(**cfg["risk"])
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler("bot.log", encoding="utf-8")])

    if args.command == "telegram":
        from botcrypto.notify import Telegram
        tg = Telegram()
        if not tg.token:
            sys.exit("TELEGRAM_BOT_TOKEN manquant dans le fichier .env (voir GUIDE-WINDOWS.md).")
        if not tg.chat_id:
            ids = tg.find_chat_ids()
            if not ids:
                sys.exit("Aucun message reçu : envoie d'abord « bonjour » à ton bot dans Telegram, puis relance.")
            for cid, name in ids:
                print(f"TELEGRAM_CHAT_ID={cid}   ({name})")
            print("Copie la ligne dans ton fichier .env, puis relance : python bot.py telegram")
            return
        print("Message envoyé !" if tg.send("✅ Le bot crypto est bien relié à Telegram.") else "Échec de l'envoi : vérifie le token et le chat id.")
        return

    if args.command == "portfolio":
        from botcrypto.data import load_or_fetch as lf
        days = args.days or (3400 if cfg["timeframe"] == "1d" else 730)
        data = {p: (synthetic_candles(args.bars, seed=i) if args.demo else lf(p, cfg["timeframe"], days))
                for i, p in enumerate(cfg["products"])}
        idx = None
        for d in data.values():
            idx = d.index if idx is None else idx.intersection(d.index)
        cut = int(len(idx) * 0.7)
        for title, sl in [("Tout l'historique", slice(None)), ("Entraînement (70 %)", slice(0, cut)),
                          ("Données jamais vues (30 %)", slice(cut, None))]:
            part = cfg["capital"] / len(data)
            eq, trs, bh = 0, [], 0
            for p, d in data.items():
                d = d.loc[idx]
                r = bt.run(d.iloc[sl], STRATEGIES[cfg["strategy"]](d, **cfg["params"]).iloc[sl], part, costs, risk, cfg["timeframe"])
                eq, bh = eq + r.equity, bh + part * d["close"].iloc[sl] / d["close"].iloc[sl].iloc[0]
                trs.append(r.trades)
            import pandas as pd
            m = bt.metrics(eq, pd.concat(trs), pd.DataFrame({"close": bh}), cfg["timeframe"])
            show(f"{title} : {idx[sl][0].date()} -> {idx[sl][-1].date()}", m)
        return

    if args.command in ("backtest", "compare", "validate"):
        df = get_data(cfg, args)
        names = list(STRATEGIES) if args.command == "compare" else [cfg["strategy"]]
        for name in names:
            if args.command == "validate":
                wf = bt.walk_forward(df, name, GRIDS.get(name, {}), timeframe=cfg["timeframe"], costs=costs, risk=risk)
                print(f"\n##### {name} — meilleurs paramètres (70 % du passé) : {wf['params']}")
                show("Sur les données d'entraînement", wf["in_sample"])
                show("Sur les données JAMAIS VUES (le seul chiffre qui compte)", wf["out_of_sample"])
                mc = bt.monte_carlo(wf["oos_result"].trades)
                if mc:
                    print(f"  Monte-Carlo : médiane {pct(mc['rendement_median'])}, pire 5 % {pct(mc['rendement_p5'])}, "
                          f"proba de perte {mc['proba_perte']*100:.0f} %, drawdown pire 5 % {pct(mc['drawdown_p95'])}")
                print("  VERDICT :", "VALIDÉE (gagne, bat acheter-et-garder, profit factor > 1) -> paper trading"
                      if wf["valide"] else "REJETÉE -> ne pas passer en réel")
            else:
                params = cfg["params"] if name == cfg["strategy"] else {}
                rk = bt.BUY_HOLD_RISK if name == "buy_hold" else risk
                r = bt.run(df, STRATEGIES[name](df, **params), cfg["capital"], costs, rk, cfg["timeframe"])
                show(f"{name} ({cfg['product']} {cfg['timeframe']})", r.metrics)
                if r.stopped:
                    print("  /!\\ coupe-circuit déclenché pendant le test")
        return

    from botcrypto.broker import CoinbaseBroker, PaperBroker
    from botcrypto.live import Bot

    quote = cfg["products"][0].split("-")[1]
    if args.command == "paper":
        cfg["mode"] = "paper"
        broker = PaperBroker(quote, cfg["capital"], **cfg["costs"])
    else:
        if not args.yes_real_money:
            sys.exit("Mode réel : relance avec --yes-real-money (et seulement après des semaines en paper).")
        cfg["mode"] = "live"
        broker = CoinbaseBroker(quote, cfg["products"], fee=cfg["costs"]["fee"])
    Bot(cfg, broker).run_forever()


if __name__ == "__main__":
    main()
