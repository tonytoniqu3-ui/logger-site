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
from .strategies import STRATEGIES

log = logging.getLogger("botcrypto")


def products_of(cfg: dict) -> list[str]:
    return cfg.get("products") or [cfg["product"]]


class Bot:
    def __init__(self, cfg: dict, broker, state_dir: str = "state"):
        self.cfg, self.broker = cfg, broker
        self.products = products_of(cfg)
        self.quote = self.products[0].split("-")[1]
        self.dir = Path(state_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir / f"state_{cfg['mode']}.json"
        self.journal = self.dir / f"journal_{cfg['mode']}.csv"
        fresh = {"peak": None, "halted": False,
                 "pos": {p: {"in_position": False, "stop": 0.0, "entry": 0.0, "waiting_reset": False, "last_candle": None}
                         for p in self.products}}
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else fresh
        for p in self.products:
            self.state["pos"].setdefault(p, fresh["pos"][p])

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

    def equity(self, prices: dict) -> float:
        return self.broker.balance(self.quote) + sum(
            self.broker.balance(p.split("-")[0]) * prices[p] for p in self.products)

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
                if self.broker.balance(p.split("-")[0]) > 0:
                    self.record("VENTE coupe-circuit", p, prices[p], equity, self.broker.sell_all(p, prices[p]))
            st["halted"] = True
            self.save()
            return {"_": "COUPE-CIRCUIT déclenché"}

        out = {}
        alloc = 1 / len(self.products)
        for p, df in data.items():
            ps, price = st["pos"][p], prices[p]
            # 2) Stop ATR (vérifié à chaque passage, même au milieu d'une bougie)
            if ps["in_position"] and ps["stop"] > 0 and float(df["low"].iloc[-1]) <= ps["stop"]:
                self.record("VENTE stop", p, price, equity, self.broker.sell_all(p, price))
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
                amount = min(equity * alloc * frac, self.broker.balance(self.quote), cfg.get("max_order", float("inf")))
                if amount >= cfg.get("min_order", 1.0):
                    self.record("ACHAT", p, price, equity, self.broker.buy(p, amount, price))
                    ps.update(in_position=True, entry=price, stop=price - r["atr_stop"] * a if r["atr_stop"] > 0 else 0.0)
                    action = "achat"
            elif sig == 0 and ps["in_position"]:
                self.record("VENTE signal", p, price, equity, self.broker.sell_all(p, price))
                ps.update(in_position=False, stop=0.0)
                action = "vente"
            out[p] = action
        self.save()
        return out

    def run_forever(self):
        gran = GRANULARITIES[self.cfg["timeframe"]]
        poll = self.cfg.get("poll_seconds", 300)
        log.info("Bot démarré (%s) sur %s en %s, stratégie %s", self.cfg["mode"], ", ".join(self.products),
                 self.cfg["timeframe"], self.cfg["strategy"])
        errors = 0
        while True:
            try:
                log.info("-> %s", self.step())
                errors = 0
            except Exception as e:  # réseau, API... on ne plante pas, on réessaie
                errors += 1
                log.exception("Erreur (%d d'affilée) : %s", errors, e)
                if errors >= 10:
                    log.error("Trop d'erreurs : arrêt par sécurité.")
                    raise
            time.sleep(min(poll, gran))
