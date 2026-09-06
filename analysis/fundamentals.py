"""Фундаментальный скоринг компании по данным ``Ticker.info``.

Единая рубрика на 110 «сырых» баллов, нормируется в 0..100. Пороги немного
подстраиваются под режим бизнеса (прибыльный / растущий / венчур), но список
критериев один и тот же — так проще читать и поддерживать.
"""
from __future__ import annotations

import math

from .models import Score

_MAX_RAW = 110.0

_MODE_RU = {"PROFITABLE": "Прибыльный", "GROWTH": "Растущий", "VENTURE": "Венчур"}


def mode_ru(mode: str) -> str:
    return _MODE_RU.get(mode, mode)


def _num(value, default=None):
    """Безопасно привести к float (None / NaN / строки -> default)."""
    try:
        if value is None:
            return default
        f = float(value)
        return default if math.isnan(f) else f
    except (TypeError, ValueError):
        return default


def _grade_high(value, *bands) -> float:
    """«Больше — лучше». bands = (порог, доля) по убыванию порога."""
    for threshold, fraction in bands:
        if value >= threshold:
            return fraction
    return 0.0


def _grade_low(value, *bands) -> float:
    """«Меньше — лучше». bands = (порог, доля) по возрастанию порога."""
    for threshold, fraction in bands:
        if value <= threshold:
            return fraction
    return 0.0


def score_fundamentals(info: dict) -> Score:
    g = lambda key: _num(info.get(key))

    rev_growth = g("revenueGrowth")
    eps_growth = g("earningsGrowth")
    net_margin = g("profitMargins")
    op_margin = g("operatingMargins")
    gross_margin = g("grossMargins")
    fcf = g("freeCashflow")
    ocf = g("operatingCashflow")
    mcap = g("marketCap")
    pe = g("trailingPE")
    fwd_pe = g("forwardPE")
    ps = g("priceToSalesTrailing12Months")
    debt = g("totalDebt") or 0.0
    cash = g("totalCash") or 0.0
    d2e = g("debtToEquity")
    current_ratio = g("currentRatio")
    roe = g("returnOnEquity")
    div_yield = g("dividendYield") or 0.0          # в yfinance 1.x это уже проценты
    payout = g("payoutRatio")
    price = g("currentPrice") or g("regularMarketPrice")
    target = g("targetMeanPrice")
    rec = (info.get("recommendationKey") or "").lower()

    # --- режим бизнеса ---
    if net_margin is not None and net_margin > 0:
        mode = "PROFITABLE"
    elif rev_growth is not None and rev_growth > 0:
        mode = "GROWTH"
    else:
        mode = "VENTURE"

    breakdown: list[tuple[str, float, float, str]] = []
    raw = 0.0

    def add(label: str, weight: float, fraction: float, note: str, penalty: float = 0.0):
        nonlocal raw
        fraction = max(0.0, min(1.0, fraction))
        points = weight * fraction - penalty
        raw += points
        breakdown.append((label, round(points, 1), float(weight), note))

    # 1. Рост выручки (15) -----------------------------------------------------
    if rev_growth is None:
        add("Рост выручки", 15, 0.0, "нет данных")
    else:
        frac = _grade_high(rev_growth, (0.20, 1.0), (0.10, 0.7), (0.03, 0.4), (0.0, 0.15))
        pen = 6 if rev_growth < -0.10 else 0
        add("Рост выручки", 15, frac, f"{rev_growth * 100:+.0f}% г/г", pen)

    # 2. Рост прибыли (12) ---------------------------------------------------
    if eps_growth is None:
        pen = 3 if mode == "PROFITABLE" else 0
        add("Рост прибыли", 12, 0.0, "убыточна / нет данных", pen)
    else:
        frac = _grade_high(eps_growth, (0.20, 1.0), (0.08, 0.7), (0.0, 0.4))
        pen = 4 if (eps_growth < -0.15 and mode == "PROFITABLE") else 0
        add("Рост прибыли", 12, frac, f"{eps_growth * 100:+.0f}% г/г", pen)

    # 3. Маржа / юнит-экономика (15) --------------------------------------------
    if net_margin is not None and net_margin > 0:
        margin, mlabel, bands = net_margin, "чистая", [(0.20, 1.0), (0.10, 0.7), (0.03, 0.35), (0.0, 0.1)]
    elif op_margin is not None:
        margin, mlabel, bands = op_margin, "операционная", [(0.15, 1.0), (0.05, 0.6), (0.0, 0.25)]
    elif gross_margin is not None:
        margin, mlabel, bands = gross_margin, "валовая", [(0.50, 1.0), (0.35, 0.7), (0.20, 0.35), (0.0, 0.1)]
    else:
        margin, mlabel, bands = None, "", []
    if margin is None:
        add("Маржа", 15, 0.0, "нет данных")
    else:
        pen = 5 if margin < -0.20 else 0
        add(f"Маржа ({mlabel})", 15, _grade_high(margin, *bands), f"{margin * 100:.0f}%", pen)

    # 4. Свободный денежный поток (15) ----------------------------------------
    if fcf is not None and fcf > 0:
        add("FCF", 15, 1.0, f"{fcf / 1e6:,.0f}M — генерирует кэш")
    elif ocf is not None and ocf > 0:
        add("FCF", 15, 0.35, "FCF ≤ 0, но операционный поток положителен", 3)
    else:
        add("FCF", 15, 0.0, "прожигает наличность", 6)

    # 5. Оценка (15, может уходить в минус) -----------------------------------
    pfcf = (mcap / fcf) if (mcap and fcf and fcf > 0) else None
    if mode == "PROFITABLE" and pe is not None and pe > 0:
        frac = _grade_low(pe, (18, 1.0), (28, 0.75), (40, 0.45), (55, 0.15))
        pen = 8 if pe > 60 else 0
        note = f"P/E {pe:.0f}"
        if pfcf is not None:
            note += f", P/FCF {pfcf:.0f}"
            if pfcf > 55:
                pen += 4
        if fwd_pe and fwd_pe < pe * 0.85:          # прибыль ускоряется -> оценка лучше
            frac = min(1.0, frac + 0.15)
        add("Оценка", 15, frac, note, pen)
    elif ps is not None:
        frac = _grade_low(ps, (4, 1.0), (8, 0.7), (15, 0.4), (25, 0.15))
        pen = 6 if ps > 30 else 0
        add("Оценка", 15, frac, f"P/S {ps:.1f} (нет прибыли)", pen)
    else:
        add("Оценка", 15, 0.3, "недостаточно данных")

    # 6. Долговая нагрузка (12) ---------------------------------------------
    if mcap and mcap > 0:
        ratio = debt / mcap
        frac = _grade_low(ratio, (0.1, 1.0), (0.3, 0.7), (0.6, 0.35))
        pen = 5 if ratio >= 1 else 0
        note = f"долг/капитализация {ratio * 100:.0f}%"
    elif d2e is not None:
        frac = _grade_low(d2e, (40, 1.0), (100, 0.6), (200, 0.2))
        pen = 4 if d2e >= 250 else 0
        note = f"D/E {d2e:.0f}"
    else:
        frac, pen, note = 0.4, 0, "нет данных о долге"
    if cash and debt and cash > debt:
        frac = min(1.0, frac + 0.15)
        note += ", кэша больше долга"
    add("Долг", 12, frac, note, pen)

    # 7. Ликвидность (8) --------------------------------------------------
    if current_ratio is None:
        add("Ликвидность", 8, 0.4, "нет данных")
    else:
        frac = _grade_high(current_ratio, (2.0, 1.0), (1.5, 0.8), (1.0, 0.5))
        add("Ликвидность", 8, frac, f"current ratio {current_ratio:.1f}",
            3 if current_ratio < 1 else 0)

    # 8. ROE (8) -----------------------------------------------------------
    if roe is None:
        add("ROE", 8, 0.3, "нет данных")
    else:
        add("ROE", 8, _grade_high(roe, (0.20, 1.0), (0.12, 0.7), (0.0, 0.35)), f"{roe * 100:.0f}%")

    # 9. Дивиденды (5) — не платит != штраф ----------------------------------
    if not div_yield:
        add("Дивиденды", 5, 0.5, "не платит (нейтрально)")
    elif payout is not None and 0 < payout < 0.7:
        add("Дивиденды", 5, 1.0, f"доходность {div_yield:.1f}%, payout {payout * 100:.0f}%")
    elif payout is not None and payout >= 1:
        add("Дивиденды", 5, 0.0, f"payout {payout * 100:.0f}% — платят больше, чем зарабатывают", 4)
    else:
        add("Дивиденды", 5, 0.6, f"доходность {div_yield:.1f}%")

    # 10. Взгляд аналитиков (5) --------------------------------------------
    rec_frac = {
        "strong_buy": 1.0, "buy": 0.75, "outperform": 0.75,
        "hold": 0.4, "neutral": 0.4, "underperform": 0.1, "sell": 0.0,
    }.get(rec, 0.4)
    note = f"консенсус: {rec or 'н/д'}"
    if target and price and target > price * 1.2:
        rec_frac = min(1.0, rec_frac + 0.2)
        note += f", таргет +{(target / price - 1) * 100:.0f}%"
    add("Аналитики", 5, rec_frac, note)

    value = max(0.0, min(100.0, raw / _MAX_RAW * 100))
    metrics = {
        "name": info.get("shortName") or info.get("longName"),
        "sector": info.get("sector"),
        "currency": info.get("currency"),
        "price": price,
        "mcap": mcap,
        "pe": pe,
        "pfcf": pfcf,
        "margin": margin,
        "fcf": fcf,
        "rev_growth": rev_growth,
        "div_yield": div_yield,
    }
    return Score(round(value, 1), mode, breakdown, metrics)
