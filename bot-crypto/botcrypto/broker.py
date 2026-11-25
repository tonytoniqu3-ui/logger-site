"""Deux « courtiers » avec la même interface : simulation (par défaut) et Coinbase réel.

Interface :
  balance(devise) -> float
  buy(produit, montant_en_euros, prix)  -> {"qty": quantité reçue, ...}
  sell(produit, quantité, prix)         -> {"proceeds": euros reçus après frais, ...}

Le bot ne vend jamais plus que ce qu'il a lui-même acheté.
"""
from __future__ import annotations

import json
import math
import os
import time
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

    def sell(self, product: str, qty: float, price: float) -> dict:
        base = product.split("-")[0]
        qty = min(qty, self.wallet.get(base, 0.0))
        px = price * (1 - self.slippage)
        gross = qty * px
        self.wallet[base] = self.wallet.get(base, 0.0) - qty
        self.wallet[self.quote] += gross * (1 - self.fee)
        self._save()
        return {"side": "SELL", "product": product, "qty": qty, "price": px, "fee": gross * self.fee,
                "proceeds": gross * (1 - self.fee)}


class CoinbaseBroker:
    """Ordres réels via l'API Coinbase Advanced Trade (pip install coinbase-advanced-py).

    Clé : soit le fichier `cdp_api_key.json` téléchargé sur Coinbase (dans le dossier du bot, ou
    COINBASE_KEY_FILE), soit COINBASE_API_KEY + COINBASE_API_SECRET dans .env.
    """

    def __init__(self, quote: str, products: list[str], fee: float = 0.006, client=None):
        self.quote, self.fee = quote, fee
        self.client = client or self._make_client()
        self.increments = {}
        for p in products:
            info = self.client.get_product(p)
            self.increments[p] = (float(_get(info, "base_increment")), float(_get(info, "quote_increment")))

    @staticmethod
    def _make_client():
        from coinbase.rest import RESTClient  # import ici : inutile en simulation

        key_file = os.environ.get("COINBASE_KEY_FILE") or ("cdp_api_key.json" if Path("cdp_api_key.json").exists() else "")
        if key_file:
            return RESTClient(key_file=key_file)
        key, secret = os.environ.get("COINBASE_API_KEY"), os.environ.get("COINBASE_API_SECRET")
        if not key or not secret:
            raise RuntimeError("Clé Coinbase introuvable : mets cdp_api_key.json dans le dossier du bot (voir GUIDE-WINDOWS.md)")
        return RESTClient(api_key=key, api_secret=secret.replace("\\n", "\n"))

    def balance(self, currency: str) -> float:
        total, cursor = 0.0, None
        while True:
            page = self.client.get_accounts(limit=250, cursor=cursor) if cursor else self.client.get_accounts(limit=250)
            for acc in _get(page, "accounts"):
                if _get(acc, "currency") == currency:
                    total += float(_get(_get(acc, "available_balance"), "value"))
            if not _get(page, "has_next"):
                return total
            cursor = _get(page, "cursor")

    @staticmethod
    def _floor(x: float, step: float) -> str:
        decimals = max(0, -int(math.floor(math.log10(step))))
        return f"{math.floor(x / step + 1e-9) * step:.{decimals}f}"

    def _fill(self, response) -> dict:
        """Attend l'exécution de l'ordre et renvoie ce qui a vraiment été exécuté."""
        if not _get(response, "success"):
            raise RuntimeError(f"Ordre refusé par Coinbase : {_plain(response)}")
        order_id = _get(_get(response, "success_response"), "order_id")
        order = {}
        for _ in range(20):
            order = _get(self.client.get_order(order_id), "order")
            if _get(order, "status") in ("FILLED", "CANCELLED", "EXPIRED", "FAILED"):
                break
            time.sleep(1)
        return {"order_id": order_id, "status": _get(order, "status"),
                "filled_size": float(_get(order, "filled_size") or 0),
                "filled_value": float(_get(order, "filled_value") or 0),
                "total_fees": float(_get(order, "total_fees") or 0),
                "average_filled_price": float(_get(order, "average_filled_price") or 0)}

    def buy(self, product: str, quote_amount: float, price: float) -> dict:
        size = self._floor(quote_amount, self.increments[product][1])
        r = self.client.market_order_buy(client_order_id=str(uuid.uuid4()), product_id=product, quote_size=size)
        f = self._fill(r)
        return {"side": "BUY", "product": product, "quote_size": size, "qty": f["filled_size"],
                "price": f["average_filled_price"], "fee": f["total_fees"], **f}

    def sell(self, product: str, qty: float, price: float) -> dict:
        qty = min(qty, self.balance(product.split("-")[0]))  # jamais plus que ce qui est disponible
        size = self._floor(qty, self.increments[product][0])
        if float(size) <= 0:
            return {"side": "SELL", "product": product, "qty": 0.0, "proceeds": 0.0, "skipped": "rien à vendre"}
        r = self.client.market_order_sell(client_order_id=str(uuid.uuid4()), product_id=product, base_size=size)
        f = self._fill(r)
        proceeds = f["filled_value"] - f["total_fees"] if f["filled_value"] else float(size) * price * (1 - self.fee)
        return {"side": "SELL", "product": product, "qty": f["filled_size"] or float(size), "price": f["average_filled_price"],
                "fee": f["total_fees"], "proceeds": proceeds, **f}


def _get(obj, key, default=None):
    """Lit un champ, que le SDK renvoie un dict ou un objet."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    try:
        return obj[key]
    except Exception:
        return getattr(obj, key, default)


def _plain(r):
    return r.to_dict() if hasattr(r, "to_dict") else r
