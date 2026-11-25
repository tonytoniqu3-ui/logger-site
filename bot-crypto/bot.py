"""Point d'entrée : python bot.py <commande> [options]

  backtest   teste une stratégie sur l'historique (avec frais) et la compare à acheter-et-garder
  compare    teste toutes les stratégies d'un coup
  validate   optimise sur 70 % des données, juge sur 30 % jamais vues + Monte-Carlo
  paper      fait tourner le bot en direct avec de l'argent fictif
  live       fait tourner le bot avec de l'argent réel (Coinbase) — après des semaines de paper !
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
    return load_or_fetch(cfg["product"], cfg["timeframe"], args.days)


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
    p.add_argument("command", choices=["backtest", "compare", "validate", "paper", "live"])
    p.add_argument("--config", default="config.json")
    p.add_argument("--strategy")
    p.add_argument("--days", type=int, default=730, help="jours d'historique (défaut : 2 ans)")
    p.add_argument("--demo", action="store_true", help="données synthétiques, sans internet")
    p.add_argument("--bars", type=int, default=6000)
    p.add_argument("--yes-real-money", action="store_true")
    args = p.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    if args.strategy:
        cfg["strategy"], cfg["params"] = args.strategy, {}
    costs, risk = bt.Costs(**cfg["costs"]), bt.Risk(**cfg["risk"])
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler("bot.log")])

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

    base, quote = cfg["product"].split("-")
    if args.command == "paper":
        cfg["mode"] = "paper"
        broker = PaperBroker(base, quote, cfg["capital"], **cfg["costs"])
    else:
        if not args.yes_real_money:
            sys.exit("Mode réel : relance avec --yes-real-money (et seulement après des semaines en paper).")
        load_env()
        cfg["mode"] = "live"
        broker = CoinbaseBroker(base, quote)
    Bot(cfg, broker).run_forever()


if __name__ == "__main__":
    main()
