"""Оценка «устойчиво ли это дальше» — взгляд вперёд, а не в прошлое.

Фундаментальный скоринг описывает уже случившееся (рост, маржа, кэш). Здесь —
про будущее: прогнозы аналитиков на год вперёд, куда движется консенсус EPS,
пересматривают оценки вверх или вниз, дорого ли стоит ожидаемый рост (PEG),
закладывает ли рынок рост в оценку (forward P/E < trailing P/E).

Данные берутся одним пакетом (``get_growth_estimates`` / ``get_earnings_estimate``
/ ``get_revenue_estimate`` / ``get_eps_revisions`` / ``get_eps_trend`` тянутся из
одного ответа Yahoo) и кэшируются.
"""
from __future__ import annotations

import math

import pandas as pd
import streamlit as st
import yfinance as yf

from .config import INFO_TTL
from .models import Score

_MAX_RAW = 100.0


def _num(value, default=None):
    try:
        if value is None:
            return default
        f = float(value)
        return default if math.isnan(f) else f
    except (TypeError, ValueError):
        return default


def _cell(df: pd.DataFrame | None, period: str, column: str):
    if df is None or df.empty or period not in df.index or column not in df.columns:
        return None
    return _num(df.loc[period, column])


@st.cache_data(ttl=INFO_TTL, show_spinner=False)
def get_forward_data(ticker: str) -> dict:
    """Прогнозные метрики по тикеру. Пустой dict, если аналитики не покрывают."""
    try:
        tk = yf.Ticker(ticker)
        growth = tk.get_growth_estimates()
        eps_est = tk.get_earnings_estimate()
        rev_est = tk.get_revenue_estimate()
        revisions = tk.get_eps_revisions()
        trend = tk.get_eps_trend()
    except Exception:
        return {}

    # Прогноз роста EPS на год вперёд.
    eps_growth_1y = _cell(eps_est, "+1y", "growth")
    if eps_growth_1y is None:
        eps_growth_1y = _cell(growth, "+1y", "stockTrend")
    rev_growth_1y = _cell(rev_est, "+1y", "growth")
    ltg = _cell(growth, "LTG", "stockTrend")

    # Пересмотр оценок за 30 дней (по текущему году и году вперёд).
    up = sum(filter(None, (_cell(revisions, "0y", "upLast30days"),
                           _cell(revisions, "+1y", "upLast30days"))))
    down = sum(filter(None, (_cell(revisions, "0y", "downLast30days"),
                             _cell(revisions, "+1y", "downLast30days"))))
    revision_ratio = (up - down) / (up + down) if (up + down) else None

    # Как сдвинулся сам консенсус +1y за 90 дней.
    now = _cell(trend, "+1y", "current")
    ago = _cell(trend, "+1y", "90daysAgo")
    consensus_drift = (now / ago - 1) if (now and ago and ago > 0) else None

    n_analysts = _cell(eps_est, "+1y", "numberOfAnalysts")

    data = {
        "eps_growth_1y": eps_growth_1y,
        "rev_growth_1y": rev_growth_1y,
        "ltg": ltg,
        "revision_up_30d": int(up),
        "revision_down_30d": int(down),
        "revision_ratio": revision_ratio,
        "consensus_drift_90d": consensus_drift,
        "n_analysts": int(n_analysts) if n_analysts else 0,
    }
    # Считаем данные пустыми, если нет ни одного значимого сигнала.
    if all(data[k] is None for k in ("eps_growth_1y", "rev_growth_1y", "revision_ratio", "consensus_drift_90d")):
        return {}
    return data


def _grade_high(value, *bands) -> float:
    for threshold, fraction in bands:
        if value >= threshold:
            return fraction
    return 0.0


def _grade_low(value, *bands) -> float:
    for threshold, fraction in bands:
        if value <= threshold:
            return fraction
    return 0.0


def score_outlook(info: dict, fwd: dict) -> Score | None:
    """Балл устойчивости 0..100. None, если прогнозных данных нет."""
    if not fwd:
        return None

    g = lambda key: _num(info.get(key))
    trailing_pe = g("trailingPE")
    forward_pe = g("forwardPE")
    peg = g("trailingPegRatio")
    price = g("currentPrice") or g("regularMarketPrice")
    target = g("targetMeanPrice")

    breakdown: list[tuple[str, float, float, str]] = []
    raw = 0.0

    def add(label, weight, fraction, note, penalty=0.0):
        nonlocal raw
        fraction = max(0.0, min(1.0, fraction))
        raw += weight * fraction - penalty
        breakdown.append((label, round(weight * fraction - penalty, 1), float(weight), note))

    # 1. Прогноз роста прибыли на год вперёд (20) --------------------------
    eps_g = fwd["eps_growth_1y"]
    if eps_g is None:
        add("Прогноз прибыли +1г", 20, 0.3, "нет прогноза")
    else:
        frac = _grade_high(eps_g, (0.20, 1.0), (0.10, 0.75), (0.03, 0.45), (0.0, 0.2))
        pen = 8 if eps_g < -0.10 else 0
        add("Прогноз прибыли +1г", 20, frac, f"{eps_g * 100:+.0f}% ожид.", pen)

    # 2. Прогноз роста выручки на год вперёд (15) -------------------------
    rev_g = fwd["rev_growth_1y"]
    if rev_g is None:
        add("Прогноз выручки +1г", 15, 0.3, "нет прогноза")
    else:
        frac = _grade_high(rev_g, (0.20, 1.0), (0.10, 0.75), (0.03, 0.45), (0.0, 0.2))
        add("Прогноз выручки +1г", 15, frac, f"{rev_g * 100:+.0f}% ожид.")

    # 3. Пересмотр прогнозов аналитиками за 30 дней (22) — ключевой сигнал -
    ratio = fwd["revision_ratio"]
    up, down = fwd["revision_up_30d"], fwd["revision_down_30d"]
    if ratio is None:
        add("Пересмотр прогнозов (30д)", 22, 0.35, "нет пересмотров")
    else:
        frac = _grade_high(ratio, (0.5, 1.0), (0.2, 0.8), (-0.2, 0.45), (-0.5, 0.15))
        pen = 10 if ratio < -0.4 else 0
        verb = "повышают" if ratio > 0.1 else "снижают" if ratio < -0.1 else "без изменений"
        add("Пересмотр прогнозов (30д)", 22, frac, f"{up}↑ / {down}↓ — {verb}", pen)

    # 4. Куда сдвинулся консенсус за 90 дней (13) -------------------------
    drift = fwd["consensus_drift_90d"]
    if drift is None:
        add("Тренд консенсуса (90д)", 13, 0.35, "нет данных")
    else:
        frac = _grade_high(drift, (0.05, 1.0), (0.0, 0.7), (-0.05, 0.35))
        add("Тренд консенсуса (90д)", 13, frac, f"оценка EPS {drift * 100:+.0f}% за 90д")

    # 5. PEG — дорого ли стоит ожидаемый рост (12) ----------------------
    if peg is not None and peg > 0:
        frac = _grade_low(peg, (1.0, 1.0), (1.6, 0.75), (2.5, 0.45), (3.5, 0.2))
        pen = 4 if peg > 4 else 0
        add("PEG (рост vs цена)", 12, frac, f"PEG {peg:.1f}", pen)
    elif eps_g and eps_g > 0 and forward_pe and forward_pe > 0:
        add("PEG (рост vs цена)", 12, 0.4, "PEG н/д, оценка по forward P/E")
    else:
        add("PEG (рост vs цена)", 12, 0.25, "PEG недоступен")

    # 6. Рынок закладывает рост в оценку (8) --------------------------
    if forward_pe and trailing_pe and forward_pe > 0 and trailing_pe > 0:
        rel = forward_pe / trailing_pe
        frac = _grade_low(rel, (0.8, 1.0), (0.95, 0.7), (1.05, 0.4), (1.3, 0.15))
        add("Forward P/E vs Trailing", 8, frac, f"fwd {forward_pe:.0f} / trail {trailing_pe:.0f}")
    else:
        add("Forward P/E vs Trailing", 8, 0.35, "нет обоих P/E")

    # 7. Потенциал до средней цели аналитиков (10) ---------------------
    if target and price and price > 0:
        upside = target / price - 1
        frac = _grade_high(upside, (0.25, 1.0), (0.10, 0.7), (0.0, 0.4))
        pen = 4 if upside < -0.10 else 0
        add("Потенциал до таргета", 10, frac, f"{upside * 100:+.0f}% до консенсус-цели", pen)
    else:
        add("Потенциал до таргета", 10, 0.35, "нет таргета")

    value = max(0.0, min(100.0, raw / _MAX_RAW * 100))

    # Мало аналитиков -> прогноз ненадёжен, приглушаем балл.
    low_coverage = fwd["n_analysts"] and fwd["n_analysts"] < 5
    if low_coverage:
        value *= 0.8
        breakdown.append(("Покрытие аналитиками", 0.0, 0.0,
                          f"всего {fwd['n_analysts']} — прогноз ненадёжен, балл снижен"))

    metrics = {
        "eps_growth_1y": eps_g,
        "rev_growth_1y": rev_g,
        "revision_ratio": ratio,
        "consensus_drift_90d": drift,
        "peg": peg,
        "n_analysts": fwd["n_analysts"],
    }
    return Score(round(value, 1), "OUTLOOK", breakdown, metrics)
