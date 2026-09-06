"""Финальный вердикт = качество прошлого + устойчивость вперёд + тайминг входа.

Порядок фильтров:
1. Жёсткое вето по технике: цена делает новые минимумы — вход запрещён.
2. Фильтр устойчивости: аналитики режут прогнозы / ожидается спад — «под вопросом».
3. Комбинируем фундаментал (прошлое), outlook (будущее) и технику (момент).
"""
from __future__ import annotations

from .models import Score, Tech

VERDICT_BAN = "⛔️ ЗАПРЕТ"
VERDICT_FULL = "🚀 ПОЛНЫЙ ВХОД"
VERDICT_PARTIAL = "🟢 ЧАСТИЧНЫЙ ВХОД"
VERDICT_WAIT_TECH = "⏳ ЖДЁМ ТЕХНИКУ"
VERDICT_FRAGILE = "⚠️ УСТОЙЧИВОСТЬ ПОД ВОПРОСОМ"
VERDICT_WATCH = "👀 НАБЛЮДАТЬ"
VERDICT_SKIP = "❌ МИМО"

# Порядок для сортировки идей (меньше = выше).
VERDICT_RANK = {
    VERDICT_FULL: 0,
    VERDICT_PARTIAL: 1,
    VERDICT_WAIT_TECH: 2,
    VERDICT_WATCH: 3,
    VERDICT_FRAGILE: 4,
    VERDICT_SKIP: 5,
    VERDICT_BAN: 6,
}

# Ниже этого outlook считаем, что устойчивость под вопросом.
_FRAGILE_OUTLOOK = 35


def _top_reasons(score: Score, limit: int = 2) -> list[str]:
    ranked = sorted(score.breakdown, key=lambda row: row[1], reverse=True)
    return [f"{label}: {note}" for label, points, _, note in ranked if points > 0][:limit]


def _active_technical_reasons(tech: Tech, limit: int = 2) -> list[str]:
    return [label for label, passed in tech.breakdown if passed][:limit]


def combined_score(fund: Score, outlook: Score | None, tech: Tech | None) -> float:
    """Единый балл 0..100 с учётом того, какие блоки доступны."""
    if tech is not None and outlook is not None:
        return round(0.42 * fund.value + 0.20 * outlook.value + 0.38 * tech.value, 1)
    if tech is not None:
        return round(0.55 * fund.value + 0.45 * tech.value, 1)
    if outlook is not None:
        return round(0.60 * fund.value + 0.40 * outlook.value, 1)
    return fund.value


def decide(fund: Score, outlook: Score | None, tech: Tech | None) -> tuple[str, str]:
    """Вернуть (вердикт, короткое «почему»)."""
    reasons = _top_reasons(fund)
    if outlook is not None:
        reasons += _top_reasons(outlook, limit=1)

    # 1. Вето по технике.
    if tech is not None and not tech.holds_low:
        return VERDICT_BAN, "цена обновляет минимумы — ловить нож рано"

    # 2. Устойчивость под вопросом: хороший прошлый бизнес, но прогноз ухудшается.
    if outlook is not None and outlook.value < _FRAGILE_OUTLOOK:
        why = "; ".join(_top_reasons(fund, 1) +
                        [f"но вперёд слабо ({outlook.value:.0f}/100): "
                         + (_top_reasons(outlook, 1)[0] if _top_reasons(outlook, 1) else "аналитики снижают прогнозы")])
        if fund.value < 55:
            return VERDICT_SKIP, why
        return VERDICT_FRAGILE, why

    f = fund.value
    o = outlook.value if outlook is not None else f
    quality = 0.6 * f + 0.4 * o          # «качество идеи» без учёта тайминга

    # 3a. Без техники — решаем по качеству идеи.
    if tech is None:
        if quality >= 72:
            verdict = VERDICT_FULL
        elif quality >= 58:
            verdict = VERDICT_PARTIAL
        elif quality >= 45:
            verdict = VERDICT_WATCH
        else:
            verdict = VERDICT_SKIP
        return verdict, "; ".join(reasons) or "нет заметных плюсов"

    # 3b. С техникой.
    reasons += _active_technical_reasons(tech)
    t = tech.value
    if quality >= 70 and t >= 60:
        verdict = VERDICT_FULL
    elif quality >= 55 and t >= 40:
        verdict = VERDICT_PARTIAL
    elif quality >= 55:
        verdict = VERDICT_WAIT_TECH
    elif quality < 40:
        verdict = VERDICT_SKIP
    else:
        verdict = VERDICT_WATCH
    return verdict, "; ".join(reasons)
