"""Слой доступа к данным yfinance.

Главная идея оптимизации: весь фундаментал берём одним вызовом ``Ticker.info``
(там уже есть revenueGrowth, freeCashflow, profitMargins, trailingPE и т.д.),
а котировки — одним батч-запросом ``yf.download`` на все тикеры сразу.
Всё оборачиваем в ``st.cache_data``, поэтому повторные прогоны почти мгновенны.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
import yfinance as yf

from .config import INFO_TTL, PRICES_TTL


@st.cache_data(ttl=INFO_TTL, show_spinner=False)
def get_info(ticker: str) -> dict:
    """Сводка по компании. Пустой dict, если тикер не найден / нет данных."""
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        return {}
    # Иногда yfinance отдаёт «пустышку» без ключевых полей — считаем это ошибкой.
    if not info.get("regularMarketPrice") and not info.get("currentPrice"):
        return {}
    return info


@st.cache_data(ttl=PRICES_TTL, show_spinner=False)
def get_price_history(tickers: tuple[str, ...], period: str = "6mo") -> dict[str, pd.DataFrame]:
    """Дневные свечи по всем тикерам за один запрос -> {тикер: DataFrame}."""
    tickers = tuple(dict.fromkeys(t for t in tickers if t))
    if not tickers:
        return {}

    raw = yf.download(
        list(tickers),
        period=period,
        interval="1d",
        auto_adjust=True,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    if raw is None or raw.empty:
        return {}

    out: dict[str, pd.DataFrame] = {}
    if isinstance(raw.columns, pd.MultiIndex):
        available = set(raw.columns.get_level_values(0))
        for t in tickers:
            if t in available:
                frame = raw[t].dropna(how="all")
                if not frame.empty:
                    out[t] = frame
    else:  # одиночный тикер -> плоские колонки
        frame = raw.dropna(how="all")
        if not frame.empty:
            out[tickers[0]] = frame
    return out


def clear_cache() -> None:
    """Сбросить кэш котировок, фундаментала и скринера (кнопка «Обновить данные»)."""
    get_info.clear()
    get_price_history.clear()
    for module, name in (("analysis.discovery", "screen_strategy"),
                         ("analysis.outlook", "get_forward_data")):
        try:
            import importlib
            getattr(importlib.import_module(module), name).clear()
        except Exception:
            pass
