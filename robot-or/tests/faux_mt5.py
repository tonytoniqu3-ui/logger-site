"""Faux MetaTrader 5 : rejoue un historique M5 bougie par bougie pour tester le VRAI code du robot sans Windows.
Mêmes règles d'exécution que le simulateur (prix = bid, ask = bid + spread, stop prioritaire)."""
from __future__ import annotations

from types import SimpleNamespace as NS

import numpy as np
import pandas as pd


class FauxMT5:
    ACCOUNT_TRADE_MODE_DEMO, ACCOUNT_TRADE_MODE_REAL = 0, 2
    TIMEFRAME_M5 = 5
    ORDER_TYPE_BUY, ORDER_TYPE_SELL, ORDER_TYPE_BUY_STOP, ORDER_TYPE_SELL_STOP = 0, 1, 4, 5
    POSITION_TYPE_BUY, POSITION_TYPE_SELL = 0, 1
    TRADE_ACTION_DEAL, TRADE_ACTION_PENDING, TRADE_ACTION_SLTP, TRADE_ACTION_REMOVE = 1, 5, 6, 8
    ORDER_FILLING_FOK, ORDER_FILLING_IOC, ORDER_FILLING_RETURN = 0, 1, 2
    ORDER_TIME_GTC = 0
    TRADE_RETCODE_DONE, TRADE_RETCODE_PLACED = 10009, 10008

    def __init__(self, d: pd.DataFrame, i0: int, solde: float = 500.0, eurusd: float = 1.15, demo: bool = True):
        self.d, self.i, self.eurusd = d, i0, eurusd
        self.mode = self.ACCOUNT_TRADE_MODE_DEMO if demo else self.ACCOUNT_TRADE_MODE_REAL
        self.solde = solde
        self.ordres, self.positions, self.deals = {}, {}, []
        self.ticket = 1000
        self.T = (d.index.values.astype("datetime64[s]").astype(np.int64))
        self.O, self.H, self.L, self.C, self.S = (d[k].values for k in ("open", "high", "low", "close", "spr"))
        self.SP = d["spread"].values

    # --- compte et symbole ---
    def initialize(self):
        return True

    def last_error(self):
        return (0, "ok")

    def account_info(self):
        eq = self.solde + sum(self._pnl(p, self._px_sortie(p)) for p in self.positions.values())
        return NS(login=12345678, trade_mode=self.mode, balance=self.solde, equity=eq, currency="EUR")

    def symbols_get(self, pattern=None):
        return [NS(name="XAUUSD")]

    def symbol_select(self, name, on=True):
        return name == "XAUUSD"

    def symbol_info(self, name):
        if name != "XAUUSD":
            return None
        return NS(volume_min=0.01, volume_step=0.01, volume_max=100.0, point=0.01, digits=2, filling_mode=1,
                  trade_contract_size=100.0)

    def symbol_info_tick(self, name):
        i = self.i
        return NS(time=int(self.T[i]), bid=self.O[i], ask=self.O[i] + self.S[i])

    def copy_rates_from_pos(self, name, tf, start, n):
        a = max(0, self.i - n + 1)
        rec = np.zeros(self.i - a + 1, dtype=[("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"),
                                               ("close", "f8"), ("tick_volume", "i8"), ("spread", "i4")])
        sl = slice(a, self.i + 1)
        rec["time"], rec["open"], rec["high"], rec["low"], rec["close"] = self.T[sl], self.O[sl], self.H[sl], self.L[sl], self.C[sl]
        rec["spread"] = self.SP[sl]
        return rec

    def order_calc_profit(self, typ, name, vol, po, pc):
        sens = 1 if typ == self.ORDER_TYPE_BUY else -1
        return sens * (pc - po) * vol * 100 / self.eurusd

    # --- ordres ---
    def _res(self, code, order=0):
        return NS(retcode=code, order=order, comment="")

    def order_send(self, r):
        self.ticket += 1
        a = r["action"]
        if a == self.TRADE_ACTION_PENDING:
            self.ordres[self.ticket] = NS(ticket=self.ticket, type=r["type"], price_open=r["price"], sl=r["sl"], tp=r["tp"],
                                          volume=r["volume"], magic=r["magic"], comment=r["comment"])
            return self._res(self.TRADE_RETCODE_PLACED, self.ticket)
        if a == self.TRADE_ACTION_REMOVE:
            self.ordres.pop(r["order"], None)
            return self._res(self.TRADE_RETCODE_DONE)
        if a == self.TRADE_ACTION_SLTP:
            p = self.positions[r["position"]]
            p.sl, p.tp = r["sl"], r["tp"]
            return self._res(self.TRADE_RETCODE_DONE)
        if a == self.TRADE_ACTION_DEAL and "position" in r:
            p = self.positions.get(r["position"])
            if p:
                self._fermer(p, r["price"])
            return self._res(self.TRADE_RETCODE_DONE)
        if a == self.TRADE_ACTION_DEAL:
            typ = self.POSITION_TYPE_BUY if r["type"] == self.ORDER_TYPE_BUY else self.POSITION_TYPE_SELL
            self._ouvrir(typ, r["price"], r["sl"], r["tp"], r["volume"], r["magic"], r["comment"], self.i)
            return self._res(self.TRADE_RETCODE_DONE, self.ticket)
        raise ValueError(r)

    def positions_get(self, symbol=None):
        return tuple(self.positions.values())

    def orders_get(self, symbol=None):
        return tuple(self.ordres.values())

    def history_deals_get(self, *a, position=None):
        return [x for x in self.deals if x.position_id == position]

    # --- mécanique interne ---
    def _ouvrir(self, typ, prix, sl, tp, vol, magic, comment, i):
        self.ticket += 1
        self.positions[self.ticket] = NS(ticket=self.ticket, type=typ, price_open=prix, sl=sl, tp=tp, volume=vol, magic=magic,
                                         comment=comment, time=int(self.T[i]), i=i)
        return self.positions[self.ticket]

    def _pnl(self, p, px):
        sens = 1 if p.type == self.POSITION_TYPE_BUY else -1
        return sens * (px - p.price_open) * p.volume * 100 / self.eurusd

    def _px_sortie(self, p):
        i = self.i
        return self.O[i] if p.type == self.POSITION_TYPE_BUY else self.O[i] + self.S[i]

    def _fermer(self, p, px):
        g = self._pnl(p, px)
        self.solde += g
        self.deals.append(NS(position_id=p.ticket, profit=g, commission=0.0, swap=0.0, fee=0.0))
        self.positions.pop(p.ticket, None)

    def avancer(self):
        """La bougie en cours se termine : déclenchements, stops, objectifs. Puis on passe à la suivante."""
        i, o, h, l, s = self.i, self.O[self.i], self.H[self.i], self.L[self.i], self.S[self.i]
        for p in list(self.positions.values()):
            achat = p.type == self.POSITION_TYPE_BUY
            lo, hi = (l, h) if achat else (l + s, h + s)
            if (achat and lo <= p.sl) or (not achat and hi >= p.sl):
                self._fermer(p, p.sl)
            elif p.i < i and ((achat and hi >= p.tp) or (not achat and lo <= p.tp)):
                self._fermer(p, p.tp)
        for od in list(self.ordres.values()):
            achat = od.type == self.ORDER_TYPE_BUY_STOP
            if achat and h + s >= od.price_open:
                fill = max(od.price_open, o + s)
            elif not achat and l <= od.price_open:
                fill = min(od.price_open, o)
            else:
                continue
            del self.ordres[od.ticket]
            p = self._ouvrir(self.POSITION_TYPE_BUY if achat else self.POSITION_TYPE_SELL, fill, od.sl, od.tp, od.volume,
                             od.magic, od.comment, i)
            lo, hi = (l, h) if achat else (l + s, h + s)
            if (achat and lo <= p.sl) or (not achat and hi >= p.sl):
                self._fermer(p, p.sl)
        self.i += 1
