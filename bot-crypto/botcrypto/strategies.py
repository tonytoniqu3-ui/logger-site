"""Stratégies : chacune renvoie une colonne `signal` (1 = être acheté, 0 = être à plat).

Le signal est calculé sur la bougie CLÔTURÉE t ; le backtest l'exécute à l'ouverture de t+1.
"""
from __future__ import annotations

import pandas as pd

from . import indicators as ind


def _filters(df: pd.DataFrame, p: dict) -> pd.Series:
    ok = pd.Series(True, index=df.index)
    if p.get("trend_filter", True):  # filtre de tendance : seulement au-dessus de l'EMA 200
        ok &= df["close"] > ind.ema(df["close"], p.get("trend_period", 200))
    if p.get("volume_filter", False):  # filtre de volume : volume > moyenne x facteur
        ok &= df["volume"] > ind.sma(df["volume"], 20) * p.get("volume_mult", 1.2)
    return ok


def _hold(entry: pd.Series, exit_: pd.Series) -> pd.Series:
    """Transforme des événements d'entrée/sortie en position tenue (0/1)."""
    state, out = 0, []
    for e, x in zip(entry.fillna(False), exit_.fillna(False)):
        if state == 0 and e:
            state = 1
        elif state == 1 and x:
            state = 0
        out.append(state)
    return pd.Series(out, index=entry.index, dtype=int)


def ema_cross(df: pd.DataFrame, fast: int = 20, slow: int = 50, **p) -> pd.Series:
    f, s = ind.ema(df["close"], fast), ind.ema(df["close"], slow)
    return _hold((f > s) & _filters(df, p), f < s)


def rsi_dip(df: pd.DataFrame, low: float = 30, high: float = 55, **p) -> pd.Series:
    """Achat des creux : RSI survendu dans une tendance haussière."""
    r = ind.rsi(df["close"], 14)
    return _hold((r < low) & _filters(df, p), r > high)


def donchian_breakout(df: pd.DataFrame, entry: int = 20, exit: int = 10, **p) -> pd.Series:
    up, _ = ind.donchian(df, entry)
    _, lo = ind.donchian(df, exit)
    return _hold((df["close"] > up) & _filters(df, p), df["close"] < lo)


def macd_trend(df: pd.DataFrame, **p) -> pd.Series:
    line, sig, _ = ind.macd(df["close"])
    return _hold((line > sig) & (line > 0) & _filters(df, p), line < sig)


def bollinger_rebound(df: pd.DataFrame, **p) -> pd.Series:
    lo, mid, _ = ind.bollinger(df["close"])
    return _hold((df["close"] < lo) & _filters(df, p), df["close"] > mid)


def trend(df: pd.DataFrame, period: int = 200, **p) -> pd.Series:
    """Suivi de tendance classique : acheté au-dessus de l'EMA longue, à plat en dessous."""
    e = ind.ema(df["close"], period)
    return _hold(df["close"] > e, df["close"] < e)


def buy_and_hold(df: pd.DataFrame, **p) -> pd.Series:
    return pd.Series(1, index=df.index, dtype=int)


STRATEGIES = {
    "ema_cross": ema_cross,
    "rsi_dip": rsi_dip,
    "donchian": donchian_breakout,
    "macd": macd_trend,
    "bollinger": bollinger_rebound,
    "trend": trend,
    "buy_hold": buy_and_hold,
}
