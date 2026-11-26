"""Récupération des bougies (API publique Coinbase Exchange, sans clé) + cache CSV."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

BASE_URL = "https://api.exchange.coinbase.com"
GRANULARITIES = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "6h": 21600, "1d": 86400}
MAX_CANDLES_PER_CALL = 300
COLUMNS = ["open", "high", "low", "close", "volume"]


def fetch_candles(product: str, timeframe: str = "1h", days: int = 365, session=None) -> pd.DataFrame:
    """Télécharge `days` jours de bougies, par paquets de 300 (limite Coinbase)."""
    import requests

    gran = GRANULARITIES[timeframe]
    http = session or requests.Session()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    rows: list = []
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + timedelta(seconds=gran * MAX_CANDLES_PER_CALL), end)
        r = http.get(
            f"{BASE_URL}/products/{product}/candles",
            params={"granularity": gran, "start": cursor.isoformat(), "end": chunk_end.isoformat()},
            headers={"User-Agent": "botcrypto/1.0"},
            timeout=20,
        )
        if r.status_code == 429:  # trop de requêtes : on patiente
            time.sleep(2)
            continue
        r.raise_for_status()
        rows.extend(r.json())  # [time, low, high, open, close, volume]
        cursor = chunk_end
        time.sleep(0.35)
    return _to_frame(rows)


def _to_frame(rows) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.drop_duplicates("time").set_index("time").sort_index()
    return df[COLUMNS].astype(float)


def drop_unclosed(df: pd.DataFrame, timeframe: str, now: datetime | None = None) -> pd.DataFrame:
    """Retire la dernière bougie si elle n'est pas terminée (sinon le signal « bouge »)."""
    if df.empty:
        return df
    now = now or datetime.now(timezone.utc)
    last_open = df.index[-1].to_pydatetime()
    if last_open + timedelta(seconds=GRANULARITIES[timeframe]) > now:
        return df.iloc[:-1]
    return df


def load_or_fetch(product: str, timeframe: str, days: int, folder: str = "data") -> pd.DataFrame:
    path = Path(folder) / f"{product}_{timeframe}_{days}d.csv"
    if path.exists() and time.time() - path.stat().st_mtime < 6 * 3600:
        return pd.read_csv(path, index_col=0, parse_dates=True)
    df = fetch_candles(product, timeframe, days)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path)
    return df


def synthetic_candles(n: int = 3000, seed: int = 7, start_price: float = 30000.0, freq: str = "1h") -> pd.DataFrame:
    """Marché fictif (marche aléatoire à régimes) pour tester sans internet."""
    rng = np.random.default_rng(seed)
    regime = np.repeat(rng.choice([-1, 0, 1], size=n // 200 + 1), 200)[:n]
    rets = rng.normal(0.0002 * regime, 0.008)
    close = start_price * np.exp(np.cumsum(rets))
    open_ = np.concatenate([[start_price], close[:-1]])
    spread = np.abs(rng.normal(0, 0.004, n)) * close
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    vol = rng.lognormal(3, 0.5, n) * (1 + 3 * np.abs(rets) / 0.008)
    idx = pd.date_range("2024-01-01", periods=n, freq=freq, tz="UTC")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol}, index=idx)
