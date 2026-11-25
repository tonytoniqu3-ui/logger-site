"""Deux « courtiers » avec la même interface : simulation (par défaut) et Coinbase réel."""
from __future__ import annotations

import json
import math
import os
import uuid
from pathlib import Path


class PaperBroker:
    """Simulation : argent fictif, mêmes frais que le réel, état sauvegardé sur disque."""

    def __init__(self, base: str, quote: str, capital: float, fee: float = 0.006,
                 slippage: float = 0.0005, path: str = "state/paper_wallet.json"):
        self.base, self.quote, self.fee, self.slippage = base, quote, fee, slippage
        self.path = Path(path)
        if self.path.exists():
            self.wallet = json.loads(self.path.read_text())
        else:
            self.wallet = {quote: capital, base: 0.0}
            self._save()

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.wallet, indent=2))

    def balances(self) -> tuple[float, float]:
        return self.wallet[self.quote], self.wallet[self.base]

    def buy(self, quote_amount: float, price: float) -> dict:
        quote_amount = min(quote_amount, self.wallet[self.quote])
        px = price * (1 + self.slippage)
        qty = quote_amount * (1 - self.fee) / px
        self.wallet[self.quote] -= quote_amount
        self.wallet[self.base] += qty
        self._save()
        return {"side": "BUY", "qty": qty, "price": px, "fee": quote_amount * self.fee}

    def sell_all(self, price: float) -> dict:
        qty = self.wallet[self.base]
        px = price * (1 - self.slippage)
        gross = qty * px
        self.wallet[self.base] = 0.0
        self.wallet[self.quote] += gross * (1 - self.fee)
        self._save()
        return {"side": "SELL", "qty": qty, "price": px, "fee": gross * self.fee}


class CoinbaseBroker:
    """Ordres réels via l'API Coinbase Advanced Trade (pip install coinbase-advanced-py)."""

    def __init__(self, base: str, quote: str):
        from coinbase.rest import RESTClient  # import ici : inutile en simulation

        key, secret = os.environ.get("COINBASE_API_KEY"), os.environ.get("COINBASE_API_SECRET")
        if not key or not secret:
            raise RuntimeError("COINBASE_API_KEY / COINBASE_API_SECRET manquants (voir .env.example)")
        self.client = RESTClient(api_key=key, api_secret=secret.replace("\\n", "\n"))
        self.base, self.quote = base, quote
        self.product = f"{base}-{quote}"
        info = self.client.get_product(self.product)
        self.base_increment = float(info["base_increment"])
        self.quote_increment = float(info["quote_increment"])

    def balances(self) -> tuple[float, float]:
        vals = {self.base: 0.0, self.quote: 0.0}
        cursor = None
        while True:
            page = self.client.get_accounts(limit=250, cursor=cursor) if cursor else self.client.get_accounts(limit=250)
            for acc in page["accounts"]:
                if acc["currency"] in vals:
                    vals[acc["currency"]] += float(acc["available_balance"]["value"])
            if not page["has_next"]:
                break
            cursor = page["cursor"]
        return vals[self.quote], vals[self.base]

    @staticmethod
    def _floor(x: float, step: float) -> str:
        decimals = max(0, -int(math.floor(math.log10(step))))
        return f"{math.floor(x / step) * step:.{decimals}f}"

    def buy(self, quote_amount: float, price: float) -> dict:
        size = self._floor(quote_amount, self.quote_increment)
        r = self.client.market_order_buy(client_order_id=str(uuid.uuid4()), product_id=self.product, quote_size=size)
        return {"side": "BUY", "quote_size": size, "response": _plain(r)}

    def sell_all(self, price: float) -> dict:
        _, qty = self.balances()
        size = self._floor(qty, self.base_increment)
        if float(size) <= 0:
            return {"side": "SELL", "skipped": "rien à vendre"}
        r = self.client.market_order_sell(client_order_id=str(uuid.uuid4()), product_id=self.product, base_size=size)
        return {"side": "SELL", "base_size": size, "response": _plain(r)}


def _plain(r):
    return r.to_dict() if hasattr(r, "to_dict") else r
