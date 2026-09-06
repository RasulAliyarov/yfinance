"""Общие элементы интерфейса, чтобы страницы не дублировали код."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .models import Score, Tech

# Порядок и оформление колонок основной таблицы.
_TABLE_COLUMNS = [
    "Тикер", "Название", "Цена", "Режим", "Вердикт", "Скор",
    "Прошлое", "Перспектива", "Техника", "RSI",
    "P/E", "P/FCF", "Маржа %", "Выручка г/г %", "Прогноз EPS +1г %",
    "Див. дох. %", "Кап-я $B", "Найдено по", "Почему", "Yahoo",
]

_COLUMN_CONFIG = {
    "Скор": st.column_config.ProgressColumn("Скор", min_value=0, max_value=100, format="%.0f",
                                            help="Общий балл: прошлое + перспектива + тайминг"),
    "Прошлое": st.column_config.ProgressColumn("Прошлое", min_value=0, max_value=100, format="%.0f",
                                               help="Качество уже случившегося: рост, маржа, кэш, долг"),
    "Перспектива": st.column_config.ProgressColumn("Перспектива", min_value=0, max_value=100, format="%.0f",
                                                   help="Устойчивость вперёд: прогнозы и их пересмотр, PEG"),
    "Техника": st.column_config.NumberColumn("Техника", format="%.0f"),
    "RSI": st.column_config.NumberColumn("RSI", format="%.0f"),
    "P/E": st.column_config.NumberColumn("P/E", help="Отрицательное значение = убыток"),
    "P/FCF": st.column_config.NumberColumn("P/FCF", help="Отрицательное значение = прожигает кэш"),
    "Маржа %": st.column_config.NumberColumn("Маржа %", format="%.1f"),
    "Выручка г/г %": st.column_config.NumberColumn("Выручка г/г %", format="%.1f"),
    "Прогноз EPS +1г %": st.column_config.NumberColumn("Прогноз EPS +1г %", format="%.0f",
                                                       help="Ожидаемый аналитиками рост прибыли на год вперёд"),
    "Див. дох. %": st.column_config.NumberColumn("Див. %", format="%.2f"),
    "Кап-я $B": st.column_config.NumberColumn("Кап-я $B", format="%.1f"),
    "Yahoo": st.column_config.LinkColumn("Yahoo", display_text="открыть"),
}


def show_table(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("Нет данных для отображения.")
        return
    columns = [c for c in _TABLE_COLUMNS if c in df.columns]
    st.dataframe(
        df[columns],
        hide_index=True,
        width="stretch",
        column_config=_COLUMN_CONFIG,
    )


def _breakdown_frame(rows) -> pd.DataFrame:
    return pd.DataFrame(
        [(lbl, f"{pts:+.1f}", f"из {mx:.0f}" if mx else "—", note) for lbl, pts, mx, note in rows],
        columns=["Критерий", "Баллы", "Макс", "Комментарий"],
    )


def show_breakdown(ticker: str, fund: Score, outlook: Score | None, tech: Tech | None) -> None:
    """Разбор одной компании: из чего сложились баллы."""
    name = fund.metrics.get("name") or ""
    header = f"{ticker} — {name}  ·  прошлое {fund.value:.0f}"
    if outlook is not None:
        header += f" · перспектива {outlook.value:.0f}"
    if tech is not None:
        header += f" · техника {tech.value:.0f}"

    with st.expander(header):
        st.markdown("**Прошлое — качество уже случившегося**")
        st.dataframe(_breakdown_frame(fund.breakdown), hide_index=True, width="stretch")

        left, right = st.columns(2)
        with left:
            st.markdown("**Перспектива — устойчиво ли это дальше**")
            if outlook is None:
                st.caption("Нет прогнозов аналитиков — устойчивость не подтверждена.")
            else:
                st.dataframe(_breakdown_frame(outlook.breakdown), hide_index=True, width="stretch")
        with right:
            st.markdown("**Техника — тайминг входа**")
            if tech is None:
                st.caption("Недостаточно истории котировок.")
            else:
                st.dataframe(
                    pd.DataFrame(
                        [(lbl, "✅" if ok else "—") for lbl, ok in tech.breakdown],
                        columns=["Проверка", ""],
                    ),
                    hide_index=True,
                    width="stretch",
                )
                st.caption(f"RSI {tech.rsi:.0f} · SMA20 {tech.metrics['sma20']} · "
                           f"пройдено {tech.t_score}/5")
