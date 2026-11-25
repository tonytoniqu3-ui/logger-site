"""Backtest honnête : frais + glissement, exécution à la bougie suivante, stop ATR,
coupe-circuit, comparaison à « acheter et garder », Monte-Carlo, validation hors échantillon."""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import indicators as ind
from .strategies import STRATEGIES

BARS_PER_YEAR = {"1m": 525600, "5m": 105120, "15m": 35040, "1h": 8760, "6h": 1460, "1d": 365}


@dataclass
class Costs:
    fee: float = 0.006  # frais « taker » Coinbase Advanced (petit volume) : 0,6 % par ordre
    slippage: float = 0.0005  # 0,05 % de glissement par ordre


@dataclass
class Risk:
    atr_stop: float = 3.0  # stop à 3 x ATR sous le prix d'entrée (0 = pas de stop)
    risk_per_trade: float = 0.02  # on accepte de perdre 2 % du capital si le stop est touché
    max_position: float = 1.0  # jamais plus de 100 % du capital (pas de levier)
    kill_drawdown: float = 0.20  # arrêt total si -20 % depuis le plus haut


@dataclass
class Result:
    equity: pd.Series
    trades: pd.DataFrame
    metrics: dict = field(default_factory=dict)
    stopped: bool = False


def run(df: pd.DataFrame, signal: pd.Series, capital: float = 100.0, costs: Costs = Costs(),
        risk: Risk = Risk(), timeframe: str = "1h") -> Result:
    a = ind.atr(df, 14).to_numpy()
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    sig = signal.reindex(df.index).fillna(0).to_numpy()
    cash, qty, entry_px, stop_px, entry_time, fees_in = capital, 0.0, 0.0, 0.0, None, 0.0
    peak, stopped, waiting_reset = capital, False, False
    equity, trades = np.empty(len(df)), []

    def close_position(i, px, reason):
        nonlocal cash, qty
        px *= 1 - costs.slippage
        gross = qty * px
        fee = gross * costs.fee
        cash += gross - fee
        cost_basis = qty * entry_px + fees_in
        trades.append({"entry_time": entry_time, "exit_time": df.index[i], "entry": entry_px, "exit": px,
                       "pnl": gross - fee - cost_basis, "ret": (gross - fee) / cost_basis - 1,
                       "fees": fee + fees_in, "reason": reason})
        qty = 0.0

    for i in range(len(df)):
        if i > 0 and not stopped:
            want = sig[i - 1]  # décision prise à la clôture précédente
            if want == 0:
                waiting_reset = False
            if qty == 0 and want == 1 and not waiting_reset and not np.isnan(a[i - 1]):
                px = o[i] * (1 + costs.slippage)
                eq = cash
                frac = risk.max_position
                if risk.atr_stop > 0:
                    dist = risk.atr_stop * a[i - 1] / px
                    frac = min(risk.max_position, risk.risk_per_trade / max(dist, 1e-9))
                spend = eq * frac
                fees_in = spend * costs.fee
                qty = (spend - fees_in) / px
                cash -= spend
                entry_px, entry_time = px, df.index[i]
                stop_px = px - risk.atr_stop * a[i - 1] if risk.atr_stop > 0 else 0.0
            elif qty > 0 and want == 0:
                close_position(i, o[i], "signal")
            if qty > 0 and stop_px > 0 and l[i] <= stop_px:
                close_position(i, min(o[i], stop_px), "stop")
                waiting_reset = True  # on attend un nouveau signal avant de racheter
        eq = cash + qty * c[i]
        peak = max(peak, eq)
        if not stopped and eq <= peak * (1 - risk.kill_drawdown):
            if qty > 0:
                close_position(i, c[i], "coupe-circuit")
            eq, stopped = cash, True
        equity[i] = eq

    if qty > 0:
        close_position(len(df) - 1, c[-1], "fin")
        equity[-1] = cash
    eq_s = pd.Series(equity, index=df.index)
    tr = pd.DataFrame(trades)
    res = Result(eq_s, tr, stopped=stopped)
    res.metrics = metrics(eq_s, tr, df, timeframe)
    return res


def metrics(equity: pd.Series, trades: pd.DataFrame, df: pd.DataFrame, timeframe: str = "1h") -> dict:
    bpy = BARS_PER_YEAR[timeframe]
    rets = equity.pct_change().fillna(0)
    years = max(len(equity) / bpy, 1e-9)
    total = equity.iloc[-1] / equity.iloc[0] - 1
    cagr = (1 + total) ** (1 / years) - 1 if total > -1 else -1.0
    dd = (equity / equity.cummax() - 1).min()
    sharpe = rets.mean() / rets.std() * np.sqrt(bpy) if rets.std() > 0 else 0.0
    bh = df["close"].iloc[-1] / df["close"].iloc[0] - 1
    m = {"rendement": total, "cagr": cagr, "max_drawdown": dd, "sharpe": sharpe,
         "calmar": cagr / abs(dd) if dd < 0 else 0.0, "acheter_garder": bh, "trades": len(trades)}
    if len(trades):
        wins = trades[trades.pnl > 0]
        losses = trades[trades.pnl <= 0]
        m["taux_gain"] = len(wins) / len(trades)
        m["profit_factor"] = wins.pnl.sum() / abs(losses.pnl.sum()) if len(losses) and losses.pnl.sum() != 0 else np.inf
        m["frais_payes"] = trades.fees.sum()
    return m


def monte_carlo(trades: pd.DataFrame, n: int = 2000, seed: int = 1) -> dict:
    """Ré-échantillonne l'ordre des trades : « et si la chance avait tourné autrement ? »"""
    if trades.empty:
        return {}
    rng = np.random.default_rng(seed)
    r = trades["ret"].to_numpy()
    sims = rng.choice(r, size=(n, len(r)), replace=True)
    curves = np.cumprod(1 + sims, axis=1)
    finals = curves[:, -1] - 1
    dds = (curves / np.maximum.accumulate(curves, axis=1) - 1).min(axis=1)
    return {"rendement_median": float(np.median(finals)), "rendement_p5": float(np.percentile(finals, 5)),
            "proba_perte": float((finals < 0).mean()), "drawdown_p95": float(np.percentile(dds, 5))}


BUY_HOLD_RISK = Risk(atr_stop=0, risk_per_trade=1, max_position=1, kill_drawdown=1.0)


def walk_forward(df: pd.DataFrame, strategy: str, grid: dict, split: float = 0.7, timeframe: str = "1h",
                 costs: Costs = Costs(), risk: Risk = Risk()) -> dict:
    """Optimise sur les 70 % premiers, juge sur les 30 % JAMAIS VUS."""
    fn = STRATEGIES[strategy]
    if strategy == "buy_hold":
        risk = BUY_HOLD_RISK
    cut = int(len(df) * split)
    keys = list(grid)
    best, best_score = {}, -np.inf
    for combo in itertools.product(*grid.values()) if keys else [()]:
        params = dict(zip(keys, combo))
        sig = fn(df, **params)
        r = run(df.iloc[:cut], sig.iloc[:cut], costs=costs, risk=risk, timeframe=timeframe)
        score = r.metrics["calmar"] if r.metrics["trades"] >= 5 else -np.inf
        if score > best_score:
            best, best_score = params, score
    sig = fn(df, **best)  # indicateurs causaux : calculés sur tout, tradés sur la fin seulement
    ins = run(df.iloc[:cut], sig.iloc[:cut], costs=costs, risk=risk, timeframe=timeframe)
    oos = run(df.iloc[cut:], sig.iloc[cut:], costs=costs, risk=risk, timeframe=timeframe)
    m = oos.metrics
    passed = bool(m["rendement"] > 0 and m["rendement"] > m["acheter_garder"]
              and m.get("profit_factor", 0) > 1 and m["trades"] >= 5)
    return {"params": best, "in_sample": ins.metrics, "out_of_sample": m, "oos_result": oos, "valide": passed}
