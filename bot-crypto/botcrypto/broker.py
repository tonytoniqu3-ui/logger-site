"""Deux « courtiers » avec la même interface : simulation (par défaut) et Coinbase réel.

Interface : balance(devise) -> float ; buy(produit, montant_en_devise_de_cotation, prix) ; sell_all(produit, prix).
"""
from __future__ import annotations

import json
import math
import os
import uuid
from pathlib import Path


class PaperBroker:
    """Simulation : argent fictif, mêmes frais que le réel, portefeuille sauvegardé sur disque."""

    def __init__(self, quote: str, capital: float, fee: float = 0.006, slippage: float = 0.0005,
                 path: str = "state/paper_wallet.json"):
        self.quote, self.fee, self.slippage = quote, fee, slippage
        self.path = Path(path)
        if self.path.exists():
            self.wallet = json.loads(self.path.read_text())
        else:
            self.wallet = {quote: capital}
            self._save()

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.wallet, indent=2))

    def balance(self, currency: str) -> float:
        return self.wallet.get(currency, 0.0)

    def buy(self, product: str, quote_amount: float, price: float) -> dict:
        base = product.split("-")[0]
        quote_amount = min(quote_amount, self.wallet[self.quote])
        px = price * (1 + self.slippage)
        qty = quote_amount * (1 - self.fee) / px
        self.wallet[self.quote] -= quote_amount
        self.wallet[base] = self.wallet.get(base, 0.0) + qty
        self._save()
        return {"side": "BUY", "product": product, "qty": qty, "price": px, "fee": quote_amount * self.fee}

    def sell_all(self, product: str, price: float) -> dict:
        base = product.split("-")[0]
        qty = self.wallet.get(base, 0.0)
        px = price * (1 - self.slippage)
        gross = qty * px
        self.wallet[base] = 0.0
        self.wallet[self.quote] += gross * (1 - self.fee)
        self._save()
        return {"side": "SELL", "product": product, "qty": qty, "price": px, "fee": gross * self.fee}


class CoinbaseBroker:
    """Ordres réels via l'API Coinbase Advanced Trade (pip install coinbase-advanced-py)."""

    def __init__(self, quote: str, products: list[str]):
        from coinbase.rest import RESTClient  # import ici : inutile en simulation

        key, secret = os.environ.get("COINBASE_API_KEY"), os.environ.get("COINBASE_API_SECRET")
        if not key or not secret:
            raise RuntimeError("COINBASE_API_KEY / COINBASE_API_SECRET manquants (voir .env.example)")
        self.client = RESTClient(api_key=key, api_secret=secret.replace("\\n", "\n"))
        self.quote = quote
        self.increments = {}
        for p in products:
            info = self.client.get_product(p)
            self.increments[p] = (float(info["base_increment"]), float(info["quote_increment"]))

    def balance(self, currency: str) -> float:
        total, cursor = 0.0, None
        while True:
            page = self.client.get_accounts(limit=250, cursor=cursor) if cursor else self.client.get_accounts(limit=250)
            for acc in page["accounts"]:
                if acc["currency"] == currency:
                    total += float(acc["available_balance"]["value"])
            if not page["has_next"]:
                return total
            cursor = page["cursor"]

    @staticmethod
    def _floor(x: float, step: float) -> str:
        decimals = max(0, -int(math.floor(math.log10(step))))
        return f"{math.floor(x / step) * step:.{decimals}f}"

    def buy(self, product: str, quote_amount: float, price: float) -> dict:
        size = self._floor(quote_amount, self.increments[product][1])
        r = self.client.market_order_buy(client_order_id=str(uuid.uuid4()), product_id=product, quote_size=size)
        return {"side": "BUY", "product": product, "quote_size": size, "response": _plain(r)}

    def sell_all(self, product: str, price: float) -> dict:
        qty = self.balance(product.split("-")[0])
        size = self._floor(qty, self.increments[product][0])
        if float(size) <= 0:
            return {"side": "SELL", "product": product, "skipped": "rien à vendre"}
        r = self.client.market_order_sell(client_order_id=str(uuid.uuid4()), product_id=product, base_size=size)
        return {"side": "SELL", "product": product, "base_size": size, "response": _plain(r)}


def _plain(r):
    return r.to_dict() if hasattr(r, "to_dict") else r
