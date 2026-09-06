"""Динамический поиск кандидатов через скринер Yahoo Finance.

Здесь бот сам находит тикеры под заданную стратегию (недооценённый рост,
качество+дивиденды, просадка от максимумов и т.д.), а не берёт готовый список.
Дальше эти кандидаты прогоняются через обычный анализ (fundamentals + technicals).
"""
from __future__ import annotations

import re

import streamlit as st
import yfinance as yf
from yfinance import EquityQuery as Q

from .config import DISCOVERY_TTL

# Биржи, которые считаем «нормальным листингом» (без OTC/Pink).
_GOOD_EXCHANGES = {"NMS", "NGM", "NCM", "NYQ", "ASE", "PCX", "BATS", "BTS"}
_CLEAN_SYMBOL = re.compile(r"[A-Z]{1,5}")

# Стратегия -> (запрос, поле сортировки, по возрастанию?).
# Пороговые числа в процентах, капитализация — в долларах.
_STRATEGIES: dict[str, tuple[Q, str, bool]] = {
    "Недооценённый рост": (
        Q("and", [
            Q("gt", ["intradaymarketcap", 2_000_000_000]),
            Q("btwn", ["peratio.lasttwelvemonths", 5, 30]),
            Q("gt", ["quarterlyrevenuegrowth.quarterly", 12]),
            Q("gt", ["epsgrowth.lasttwelvemonths", 8]),
            Q("eq", ["region", "us"]),
        ]),
        "quarterlyrevenuegrowth.quarterly", False,
    ),
    "Качество + дивиденды": (
        Q("and", [
            Q("gt", ["intradaymarketcap", 5_000_000_000]),
            Q("gt", ["returnonequity.lasttwelvemonths", 15]),
            Q("gt", ["netincomemargin.lasttwelvemonths", 12]),
            Q("gt", ["dividendyield", 1.5]),
            Q("lt", ["totaldebtequity.lasttwelvemonths", 120]),
            Q("eq", ["region", "us"]),
        ]),
        "returnonequity.lasttwelvemonths", False,
    ),
    "Кэш-машина (FCF)": (
        Q("and", [
            Q("gt", ["intradaymarketcap", 1_000_000_000]),
            Q("gt", ["leveredfreecashflow.lasttwelvemonths", 0]),
            Q("gt", ["netincomemargin.lasttwelvemonths", 10]),
            Q("lt", ["peratio.lasttwelvemonths", 35]),
            Q("eq", ["region", "us"]),
        ]),
        "leveredfreecashflow.lasttwelvemonths", False,
    ),
    "Просадка от максимумов": (
        Q("and", [
            Q("gt", ["intradaymarketcap", 3_000_000_000]),
            Q("lt", ["fiftytwowkpercentchange", -25]),
            Q("gt", ["netincomemargin.lasttwelvemonths", 5]),
            Q("lt", ["totaldebtequity.lasttwelvemonths", 150]),
            Q("eq", ["region", "us"]),
        ]),
        "fiftytwowkpercentchange", True,
    ),
    "Малые каппы с ускорением": (
        Q("and", [
            Q("btwn", ["intradaymarketcap", 300_000_000, 3_000_000_000]),
            Q("gt", ["quarterlyrevenuegrowth.quarterly", 20]),
            Q("gt", ["grossprofitmargin.lasttwelvemonths", 30]),
            Q("gt", ["avgdailyvol3m", 300_000]),
            Q("eq", ["region", "us"]),
        ]),
        "quarterlyrevenuegrowth.quarterly", False,
    ),
}

STRATEGY_NAMES = list(_STRATEGIES)


@st.cache_data(ttl=DISCOVERY_TTL, show_spinner=False)
def screen_strategy(strategy: str, size: int = 40) -> list[str]:
    """Тикеры под одну стратегию. Пустой список при ошибке/неизвестном имени."""
    spec = _STRATEGIES.get(strategy)
    if spec is None:
        return []
    query, sort_field, ascending = spec
    try:
        resp = yf.screen(query, sortField=sort_field, sortAsc=ascending, size=size)
    except Exception:
        return []

    symbols: list[str] = []
    for quote in resp.get("quotes") or []:
        symbol = (quote.get("symbol") or "").upper()
        if quote.get("quoteType") != "EQUITY":
            continue
        if quote.get("exchange") not in _GOOD_EXCHANGES:
            continue
        if not _CLEAN_SYMBOL.fullmatch(symbol):
            continue
        if symbol not in symbols:
            symbols.append(symbol)
    return symbols


def discover(strategies: list[str], size: int = 40) -> dict[str, list[str]]:
    """{стратегия: [тикеры]} по выбранным стратегиям."""
    return {name: screen_strategy(name, size) for name in strategies}


def sources_map(found: dict[str, list[str]]) -> dict[str, list[str]]:
    """Обратная карта {тикер: [стратегии, которые его нашли]}."""
    result: dict[str, list[str]] = {}
    for strategy, tickers in found.items():
        for ticker in tickers:
            result.setdefault(ticker, []).append(strategy)
    return result
