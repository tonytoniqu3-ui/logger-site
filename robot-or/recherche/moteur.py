"""Moteur de recherche intraday sur l'or (bougies M5, heure serveur du courtier).

Réalisme : prix des données = bid. Achat payé au ask (bid + spread), vente rachetée au ask.
Entrée à la clôture de la bougie signal. Si une bougie touche stop ET objectif : stop d'abord.
Une seule position à la fois. Tout est fermé à l'heure `flat` (21 h par défaut).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SPLIT = pd.Timestamp("2026-03-01")  # conception avant, contrôle après (regardé une seule fois)


def load(path="data/XAUUSD_M5.csv") -> pd.DataFrame:
    d = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    d["spr"] = d["spread"] * 0.01
    d["ema_h1"] = d["close"].ewm(span=200 * 12, adjust=False).mean().shift(1)  # ~EMA 200 en H1, sans regard futur
    return d


def _minutes(idx):
    return idx.hour.values * 60 + idx.minute.values


def run(d: pd.DataFrame, spec: dict) -> pd.DataFrame:
    """spec : {"windows": [(debut_min, fin_min, fin_trading_min, type)], "stop": fraction du range,
               "rr": objectif en multiples du risque, "trend": bool, "flat": minute de fermeture}"""
    o, h, l, c, spr, ema = (d[k].values for k in ("open", "high", "low", "close", "spr", "ema_h1"))
    mins = _minutes(d.index)
    days = d.index.normalize()
    day_codes, starts = np.unique(days.values, return_index=True)
    ends = np.r_[starts[1:], len(d)]
    flat = spec.get("flat", 21 * 60)
    trades = []
    prev_hi = prev_lo = None
    for s, e in zip(starts, ends):
        di = np.arange(s, e)
        m = mins[di]
        busy_until = -1
        for (a, b, until, kind) in spec["windows"]:
            if kind == "pdhl":
                if prev_hi is None:
                    continue
                H, L = prev_hi, prev_lo
            else:
                rg = di[(m >= a) & (m < b)]
                if len(rg) < max(3, (b - a) // 5 * 0.6):
                    continue
                H, L = h[rg].max(), l[rg].min()
            w = H - L
            if w <= 0:
                continue
            win = di[(m >= b) & (m < min(until, flat))]
            win = win[win > busy_until]
            sig = None
            if kind in ("break", "pdhl") and spec.get("entry") == "niveau":
                # ordres en attente : buy stop au plus haut du range (déclenché quand le ASK le touche),
                # sell stop au plus bas (déclenché quand le BID le touche). Le premier déclenché annule l'autre.
                # tendance lue à la fin du range (comme le robot) : un seul ordre, dans le sens de la tendance
                allowed = (1, -1)
                if spec.get("trend") and len(win):
                    allowed = (int(np.sign(c[win[0] - 1] - ema[win[0] - 1])),)
                late = spec.get("late", 0.35)
                for j in win:
                    up, dn = h[j] + spr[j] >= H, l[j] <= L
                    if up and dn:
                        break  # bougie qui touche les deux : ambigu, on s'abstient
                    if up or dn:
                        side = 1 if up else -1
                        if side not in allowed:
                            break  # cassure du mauvais côté : séance annulée
                        fill = max(H, o[j] + spr[j]) if up else min(L, o[j])  # trou d'ouverture : pire prix
                        if abs(fill - (H if up else L)) > late * w:
                            break  # trop loin du niveau : on ne court pas après le prix
                        sig = (j, side, fill)
                        break
            elif kind in ("break", "pdhl"):
                for j in win:
                    up, dn = c[j] > H, c[j] < L          # cassure confirmée par la clôture
                    if up or dn:
                        side = 1 if up else -1
                        if spec.get("trend") and np.sign(c[j] - ema[j]) != side:
                            break                          # cassure contre la tendance : on passe la séance
                        sig = (j, side)
                        break
            elif kind == "fade":
                out_up = out_dn = False
                for j in win:
                    if h[j] > H:
                        out_up = True
                    if l[j] < L:
                        out_dn = True
                    if out_up and c[j] < H and c[j] > L:   # sortie par le haut puis retour dans le range
                        sig = (j, -1)
                        break
                    if out_dn and c[j] > L and c[j] < H:
                        sig = (j, 1)
                        break
            if sig is None:
                continue
            if len(sig) == 3:
                j, side, ent = sig
                first = j  # la bougie de déclenchement peut déjà toucher le stop (cas défavorable)
            else:
                j, side = sig
                ent = c[j] + (spr[j] if side == 1 else 0.0)
                first = j + 1
            risk = spec["stop"] * w
            sl = ent - side * risk
            tp = ent + side * spec["rr"] * risk
            px, k = None, None
            for j2 in di[di >= first]:
                if mins[j2] >= flat:
                    px, k = (o[j2] if side == 1 else o[j2] + spr[j2]), j2
                    break
                lo_, hi_ = (l[j2], h[j2]) if side == 1 else (l[j2] + spr[j2], h[j2] + spr[j2])
                if (side == 1 and lo_ <= sl) or (side == -1 and hi_ >= sl):
                    px, k = sl, j2
                    break
                if j2 == j:
                    continue  # pas d'objectif atteint dans la bougie d'entrée (ordre inconnu)
                if (side == 1 and hi_ >= tp) or (side == -1 and lo_ <= tp):
                    px, k = tp, j2
                    break
            if px is None:
                k = di[-1]
                px = c[k] if side == 1 else c[k] + spr[k]
            trades.append({"t": d.index[j], "sortie": d.index[k], "side": side, "risk": risk,
                           "r": side * (px - ent) / risk, "w": w})
            busy_until = k
        prev_hi, prev_lo = h[di].max(), l[di].min()
    return pd.DataFrame(trades)


def stats(t: pd.DataFrame) -> dict:
    if len(t) < 10:
        return {"n": len(t)}
    r = t.r.values
    out = {"n": len(r), "reussite": (r > 0).mean(), "esp": r.mean(), "t": r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))}
    for nm, part in (("concep", t[t.t < SPLIT]), ("controle", t[t.t >= SPLIT])):
        out[f"esp_{nm}"] = part.r.mean() if len(part) else np.nan
        out[f"n_{nm}"] = len(part)
        if len(part) > 5:
            out[f"t_{nm}"] = part.r.mean() / (part.r.std(ddof=1) / np.sqrt(len(part)))
    return out
