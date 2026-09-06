"""Небольшие контейнеры для результатов анализа."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Score:
    """Результат фундаментального анализа компании."""

    value: float                      # итоговый балл 0..100
    mode: str                         # PROFITABLE / GROWTH / VENTURE
    breakdown: list = field(default_factory=list)   # [(метка, баллы, максимум, комментарий)]
    metrics: dict = field(default_factory=dict)     # сырые числа для таблицы


@dataclass
class Tech:
    """Результат технического анализа (тайминг входа)."""

    value: float                      # итоговый балл 0..100
    t_score: int                      # сколько из 5 проверок пройдено
    holds_low: bool                   # ключевой фильтр: цена не делает новых минимумов
    rsi: float
    breakdown: list = field(default_factory=list)   # [(метка, пройдено ли)]
    metrics: dict = field(default_factory=dict)
