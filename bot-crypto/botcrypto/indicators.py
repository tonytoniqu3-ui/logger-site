"""Indicateurs techniques. Chaque valeur à l'instant t n'utilise QUE les bougies <= t."""
import numpy as np
import pandas as pd


def ema(s: pd.Series, period: int) -> pd.Series:
    return s.ewm(span=period, adjust=False, min_periods=period).mean()


def sma(s: pd.Series, period: int) -> pd.Series:
    return s.rolling(period, min_periods=period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI de Wilder (lissage alpha = 1/period)."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.where(loss != 0, 100.0).where(gain.notna())


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def donchian(df: pd.DataFrame, period: int = 20) -> tuple[pd.Series, pd.Series]:
    """Plus haut / plus bas des `period` bougies PRÉCÉDENTES (shift 1 : pas de triche)."""
    upper = df["high"].rolling(period, min_periods=period).max().shift(1)
    lower = df["low"].rolling(period, min_periods=period).min().shift(1)
    return upper, lower


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return line, sig, line - sig


def bollinger(close: pd.Series, period: int = 20, k: float = 2.0):
    mid = sma(close, period)
    std = close.rolling(period, min_periods=period).std(ddof=0)
    return mid - k * std, mid, mid + k * std
