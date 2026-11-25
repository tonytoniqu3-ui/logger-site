"""Boucle du bot en direct (simulation ou réel). Une décision par bougie clôturée."""
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


class Bot:
    def __init__(self, cfg: dict, broker, state_dir: str = "state"):
        self.cfg, self.broker = cfg, broker
        self.dir = Path(state_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir / f"state_{cfg['mode']}.json"
        self.journal = self.dir / f"journal_{cfg['mode']}.csv"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {
            "in_position": False, "stop": 0.0, "entry": 0.0, "peak": None, "halted": False,
            "waiting_reset": False, "last_candle": None}

    def save(self):
        self.state_path.write_text(json.dumps(self.state, indent=2))

    def record(self, action: str, price: float, equity: float, detail=""):
        new = not self.journal.exists()
        with self.journal.open("a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["heure_utc", "action", "prix", "capital", "detail"])
            w.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds"), action, f"{price:.2f}",
                        f"{equity:.2f}", json.dumps(detail, default=str)[:500]])
        log.info("%s @ %.2f | capital %.2f", action, price, equity)

    def step(self, df=None) -> str:
        cfg, st, r = self.cfg, self.state, self.cfg["risk"]
        if st["halted"]:
            return "arrêté (coupe-circuit) — supprime le fichier d'état pour relancer"
        if df is None:
            raw = fetch_candles(cfg["product"], cfg["timeframe"], days=cfg.get("history_days", 30))
            df = drop_unclosed(raw, cfg["timeframe"])
        last_time = str(df.index[-1])
        price = float(df["close"].iloc[-1])
        quote, base = self.broker.balances()
        equity = quote + base * price
        st["peak"] = max(st["peak"] or equity, equity)

        # 1) Coupe-circuit : -20 % depuis le plus haut => on vend tout et on s'arrête
        if equity <= st["peak"] * (1 - r["kill_drawdown"]):
            if base > 0:
                self.record("VENTE coupe-circuit", price, equity, self.broker.sell_all(price))
            st["halted"] = True
            self.save()
            return "COUPE-CIRCUIT déclenché"

        # 2) Stop ATR (vérifié à chaque passage, même au milieu d'une bougie)
        if st["in_position"] and st["stop"] > 0 and float(df["low"].iloc[-1]) <= st["stop"]:
            self.record("VENTE stop", price, equity, self.broker.sell_all(price))
            st.update(in_position=False, stop=0.0, waiting_reset=True)
            self.save()
            return "stop touché"

        # 3) Signal : une seule décision par bougie clôturée
        if st["last_candle"] == last_time:
            return "rien de neuf"
        st["last_candle"] = last_time
        sig = int(STRATEGIES[cfg["strategy"]](df, **cfg.get("params", {})).iloc[-1])
        if sig == 0:
            st["waiting_reset"] = False
        action = "attente"
        if sig == 1 and not st["in_position"] and not st["waiting_reset"]:
            a = float(ind.atr(df, 14).iloc[-1])
            dist = r["atr_stop"] * a / price
            frac = min(r["max_position"], r["risk_per_trade"] / max(dist, 1e-9)) if r["atr_stop"] > 0 else r["max_position"]
            amount = min(equity * frac, quote, cfg.get("max_order", float("inf")))
            if amount >= cfg.get("min_order", 1.0):
                self.record("ACHAT", price, equity, self.broker.buy(amount, price))
                st.update(in_position=True, entry=price, stop=price - r["atr_stop"] * a if r["atr_stop"] > 0 else 0.0)
                action = "achat"
        elif sig == 0 and st["in_position"]:
            self.record("VENTE signal", price, equity, self.broker.sell_all(price))
            st.update(in_position=False, stop=0.0)
            action = "vente"
        self.save()
        return action

    def run_forever(self):
        gran = GRANULARITIES[self.cfg["timeframe"]]
        poll = self.cfg.get("poll_seconds", 60)
        log.info("Bot démarré (%s) sur %s %s, stratégie %s", self.cfg["mode"], self.cfg["product"],
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
