"""Boucle du bot en direct (simulation ou réel), sur une ou plusieurs paires.

Le capital est partagé à parts égales entre les paires. Une décision par bougie clôturée.
"""
from __future__ import annotations

import csv
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from . import indicators as ind
from .data import GRANULARITIES, drop_unclosed, fetch_candles
from .notify import Telegram
from .strategies import STRATEGIES

log = logging.getLogger("botcrypto")


def products_of(cfg: dict) -> list[str]:
    return cfg.get("products") or [cfg["product"]]


class Bot:
    def __init__(self, cfg: dict, broker, state_dir: str = "state", notifier=None):
        self.cfg, self.broker = cfg, broker
        self.notifier = notifier if notifier is not None else Telegram()
        self.tag = "SIMULATION" if cfg["mode"] == "paper" else "ARGENT RÉEL"
        self.products = products_of(cfg)
        self.quote = self.products[0].split("-")[1]
        self.dir = Path(state_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir / f"state_{cfg['mode']}.json"
        self.journal = self.dir / f"journal_{cfg['mode']}.csv"
        # Registre du bot : son propre budget (cash) et les quantités qu'IL a achetées.
        # Il ne touche jamais au reste du compte.
        fresh = {"cash": float(cfg["capital"]), "peak": None, "halted": False, "last_report": None,
                 "pos": {p: {"in_position": False, "qty": 0.0, "stop": 0.0, "entry": 0.0, "waiting_reset": False, "last_candle": None}
                         for p in self.products}}
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else fresh
        for p in self.products:
            self.state["pos"].setdefault(p, fresh["pos"][p])
            self.state["pos"][p].setdefault("qty", 0.0)
        self.state.setdefault("cash", float(cfg["capital"]))

    def save(self):
        self.state_path.write_text(json.dumps(self.state, indent=2))

    def record(self, action: str, product: str, price: float, equity: float, detail=""):
        new = not self.journal.exists()
        with self.journal.open("a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["heure_utc", "action", "paire", "prix", "capital_total", "detail"])
            w.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds"), action, product, f"{price:.2f}",
                        f"{equity:.2f}", json.dumps(detail, default=str)[:500]])
        log.info("%s %s @ %.2f | capital %.2f", action, product, price, equity)
        icon = "🟢" if action == "ACHAT" else "🔴" if ("stop" in action or "coupe" in action) else "🟡"
        self.notifier.send(f"{icon} [{self.tag}] {action} {product}\nPrix : {price:,.2f}\nCapital total : {equity:,.2f} {self.quote}".replace(",", " "))

    def equity(self, prices: dict) -> float:
        """Capital du bot uniquement : son budget en euros + ce qu'il a acheté, au prix du moment."""
        return self.state["cash"] + sum(self.state["pos"][p]["qty"] * prices[p] for p in self.products)

    def _buy(self, p, amount, price):
        res = self.broker.buy(p, amount, price)
        self.state["cash"] -= amount
        self.state["pos"][p]["qty"] += float(res.get("qty", 0.0))
        return res

    def _sell(self, p, price):
        ps = self.state["pos"][p]
        res = self.broker.sell(p, ps["qty"], price)
        self.state["cash"] += float(res.get("proceeds", 0.0))
        ps["qty"] = max(0.0, ps["qty"] - float(res.get("qty", 0.0)))
        if ps["qty"] < 1e-12:
            ps["qty"] = 0.0
        return res

    def step(self, data: dict | None = None) -> dict:
        """`data` : {paire: DataFrame de bougies clôturées}. Sans `data`, on télécharge."""
        cfg, st, r = self.cfg, self.state, self.cfg["risk"]
        if st["halted"]:
            return {"_": "arrêté (coupe-circuit) — supprime le fichier d'état pour relancer"}
        if data is None:
            data = {p: drop_unclosed(fetch_candles(p, cfg["timeframe"], days=cfg.get("history_days", 300)), cfg["timeframe"])
                    for p in self.products}
        prices = {p: float(df["close"].iloc[-1]) for p, df in data.items()}
        equity = self.equity(prices)
        st["peak"] = max(st["peak"] or equity, equity)

        # 1) Coupe-circuit global : -20 % depuis le plus haut => on vend tout et on s'arrête
        if equity <= st["peak"] * (1 - r["kill_drawdown"]):
            for p in self.products:
                if st["pos"][p]["qty"] > 0:
                    self.record("VENTE coupe-circuit", p, prices[p], equity, self._sell(p, prices[p]))
                st["pos"][p].update(in_position=False, stop=0.0)
            st["halted"] = True
            self.save()
            self.notifier.send(f"⛔ [{self.tag}] COUPE-CIRCUIT : -{r['kill_drawdown']:.0%} depuis le plus haut. "
                               f"Tout est vendu, le bot est arrêté. Capital : {equity:.2f} {self.quote}")
            return {"_": "COUPE-CIRCUIT déclenché"}

        out = {}
        alloc = 1 / len(self.products)
        for p, df in data.items():
            ps, price = st["pos"][p], prices[p]
            # 2) Stop ATR (vérifié à chaque passage, même au milieu d'une bougie)
            if ps["in_position"] and ps["stop"] > 0 and float(df["low"].iloc[-1]) <= ps["stop"]:
                self.record("VENTE stop", p, price, equity, self._sell(p, price))
                ps.update(in_position=False, stop=0.0, waiting_reset=True)
                out[p] = "stop touché"
                continue
            # 3) Signal : une seule décision par bougie clôturée
            last = str(df.index[-1])
            if ps["last_candle"] == last:
                out[p] = "rien de neuf"
                continue
            ps["last_candle"] = last
            sig = int(STRATEGIES[cfg["strategy"]](df, **cfg.get("params", {})).iloc[-1])
            if sig == 0:
                ps["waiting_reset"] = False
            action = "attente"
            if sig == 1 and not ps["in_position"] and not ps["waiting_reset"]:
                a = float(ind.atr(df, 14).iloc[-1])
                frac = r["max_position"]
                if r["atr_stop"] > 0:
                    frac = min(frac, r["risk_per_trade"] / max(r["atr_stop"] * a / price, 1e-9))
                amount = min(equity * alloc * frac, st["cash"], self.broker.balance(self.quote), cfg.get("max_order", float("inf")))
                if amount >= cfg.get("min_order", 1.0):
                    self.record("ACHAT", p, price, equity, self._buy(p, amount, price))
                    ps.update(in_position=True, entry=price, stop=price - r["atr_stop"] * a if r["atr_stop"] > 0 else 0.0)
                    action = "achat"
            elif sig == 0 and ps["in_position"]:
                self.record("VENTE signal", p, price, equity, self._sell(p, price))
                ps.update(in_position=False, stop=0.0)
                action = "vente"
            out[p] = action
        self.daily_report(equity, data)
        self.save()
        return out

    def daily_report(self, equity: float, data: dict):
        """Un petit bilan par jour sur Telegram."""
        today = datetime.now(timezone.utc).date().isoformat()
        if self.state.get("last_report") == today:
            return
        self.state["last_report"] = today
        lines = [f"📊 [{self.tag}] Bilan du {today}", f"Capital : {equity:.2f} {self.quote} (plus haut {self.state['peak']:.2f})"]
        for p, df in data.items():
            ps = self.state["pos"][p]
            trend = "au-dessus" if df["close"].iloc[-1] > ind.ema(df["close"], 200).iloc[-1] else "en dessous"
            pos = f"acheté, stop {ps['stop']:.2f}" if ps["in_position"] else "pas de position"
            lines.append(f"{p} : {df['close'].iloc[-1]:.2f} · {trend} de l'EMA 200 · {pos}")
        self.notifier.send("\n".join(lines))

    def run_forever(self):
        gran = GRANULARITIES[self.cfg["timeframe"]]
        poll = self.cfg.get("poll_seconds", 300)
        log.info("Bot démarré (%s) sur %s en %s, stratégie %s", self.cfg["mode"], ", ".join(self.products),
                 self.cfg["timeframe"], self.cfg["strategy"])
        self.notifier.send(f"▶️ [{self.tag}] Bot démarré sur {', '.join(self.products)} ({self.cfg['timeframe']}, {self.cfg['strategy']})")
        errors = 0
        while True:
            try:
                log.info("-> %s", self.step())
                errors = 0
            except Exception as e:  # réseau, API... on ne plante pas, on réessaie
                errors += 1
                log.exception("Erreur (%d d'affilée) : %s", errors, e)
                if errors == 3:
                    self.notifier.send(f"⚠️ [{self.tag}] 3 erreurs d'affilée : {e}")
                if errors >= 10:
                    log.error("Trop d'erreurs : arrêt par sécurité.")
                    self.notifier.send(f"⛔ [{self.tag}] Trop d'erreurs, le bot s'arrête : {e}")
                    raise
            time.sleep(min(poll, gran))
