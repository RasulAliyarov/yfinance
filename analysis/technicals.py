"""Технический скоринг: «нащупала ли цена дно и можно ли входить».

5 проверок, каждая даёт 20 баллов. Отдельно возвращаем ``holds_low`` —
жёсткий фильтр: пока цена штампует новые минимумы, вход запрещён.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .models import Tech

_MIN_ROWS = 30


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """RSI Уайлдера через EWM. Деление на ноль -> RSI = 100 (нет просадок)."""
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100)


def score_technicals(ohlc: pd.DataFrame, low_window: int = 4) -> Tech | None:
    """ohlc — дневные свечи (Open/High/Low/Close/Volume). None, если данных мало."""
    d = ohlc.dropna()
    if len(d) < _MIN_ROWS:
        return None

    close, open_, low, volume = d["Close"], d["Open"], d["Low"], d["Volume"]
    rsi_series = rsi(close)
    rsi_now = float(rsi_series.iloc[-1])
    rsi_ago = float(rsi_series.iloc[-4])

    # 1. Держит дно: сегодняшний минимум не ниже минимумов предыдущих N дней.
    prior_min = float(low.iloc[-(low_window + 1):-1].min())
    holds_low = float(low.iloc[-1]) >= prior_min * 0.995

    # 2. RSI разворачивается вверх из ямы либо уже в здоровой зоне.
    rsi_ok = (rsi_now > rsi_ago and rsi_now < 68) or (45 <= rsi_now <= 62)

    # 3. Объём затухает: последние 5 дней тише, чем последние 25.
    vol_fading = float(volume.iloc[-5:].mean()) < float(volume.iloc[-25:].mean())

    # 4. Нижние тени у последних свечей длиннее тела — покупатели откупают.
    body = (close - open_).abs()
    lower_wick = pd.concat([close, open_], axis=1).min(axis=1) - low
    wick_buy = float(lower_wick.iloc[-3:].mean()) > float(body.iloc[-3:].mean())

    # 5. Цена вернулась к 20-дневной средней (или почти).
    sma20 = float(close.rolling(20).mean().iloc[-1])
    reclaim = float(close.iloc[-1]) >= sma20 * 0.97

    checks = [
        ("Держит дно (нет новых минимумов)", holds_low),
        ("RSI разворот вверх / здоровый", rsi_ok),
        ("Объём затухает (паника выдохлась)", vol_fading),
        ("Нижние тени — идёт откуп", wick_buy),
        ("Цена вернулась к 20-дневной средней", reclaim),
    ]
    t_score = sum(passed for _, passed in checks)
    value = round(t_score / len(checks) * 100, 1)
    metrics = {"rsi": round(rsi_now, 1), "sma20": round(sma20, 2),
               "last": round(float(close.iloc[-1]), 2)}
    return Tech(value, int(t_score), holds_low, round(rsi_now, 1), checks, metrics)
