"""Идеи бота: динамический поиск кандидатов через скринер Yahoo + наш анализ.

Пайплайн:
1. Скринер Yahoo отдаёт тикеры под выбранные стратегии (бот сам их находит).
2. Кандидаты прогоняются через обычный анализ (качество бизнеса + тайминг входа).
3. Отдельным блоком показываем те, где сигнал на вход есть уже сейчас.
"""
from __future__ import annotations

import streamlit as st

from analysis import (
    STRATEGY_NAMES,
    analyze,
    clear_cache,
    discover,
    opportunities,
    sources_map,
)
from analysis.ui import show_table

st.set_page_config(page_title="Идеи бота", page_icon="💡", layout="wide")
st.title("💡 Идеи бота")
st.caption(
    "Бот сам ищет кандидатов через скринер Yahoo под выбранные стратегии, "
    "затем прогоняет их через тот же анализ (качество + тайминг) и отдельно "
    "выносит те, где сигнал на вход есть уже сейчас."
)

strategies = st.multiselect(
    "Стратегии поиска",
    STRATEGY_NAMES,
    default=["Недооценённый рост", "Кэш-машина (FCF)", "Просадка от максимумов"],
    help="Каждая стратегия — отдельный запрос к скринеру Yahoo со своими фильтрами.",
)
per_strategy = st.slider("Кандидатов на стратегию", 15, 60, 35)

col1, _, col3 = st.columns(3)
period = col1.selectbox("Период графика", ["3mo", "6mo", "1y"], index=1)
col3.write("")
col3.write("")
if col3.button("↻ Обновить данные"):
    clear_cache()
    st.toast("Кэш очищен")

if st.button("Найти идеи", type="primary"):
    if not strategies:
        st.warning("Выберите хотя бы одну стратегию.")
        st.stop()

    # --- 1. Динамический поиск кандидатов ---
    with st.spinner("Спрашиваю скринер Yahoo…"):
        found = discover(strategies, size=per_strategy)
    source_of = sources_map(found)

    st.write("**Скринер вернул:** " + " · ".join(
        f"{name} — {len(tickers)}" for name, tickers in found.items()
    ))

    candidates = sorted(source_of)
    if not candidates:
        st.error("Скринер ничего не вернул (возможно, временная ошибка Yahoo). "
                 "Попробуйте позже.")
        st.stop()

    # --- 2. Анализ кандидатов ---
    progress = st.progress(0.0, text=f"Анализирую {len(candidates)} кандидатов…")
    df, _ = analyze(
        candidates,
        price_period=period,
        on_progress=lambda done, total: progress.progress(done / total, text=f"{done}/{total}"),
    )
    progress.empty()

    if df.empty:
        st.error("Не удалось получить данные по кандидатам.")
        st.stop()

    # Колонка «Найдено по» — какая стратегия принесла тикер.
    df["Найдено по"] = df["Тикер"].map(lambda t: ", ".join(source_of.get(t, [])))

    # --- 3. Идеи на вход ---
    ideas = opportunities(df)
    st.subheader(f"💡 Кандидаты на вход — {len(ideas)}")
    if ideas.empty:
        st.info(
            "Скринер нашёл интересные компании, но ни по одной сейчас нет сигнала "
            "на вход (техника не подтверждает или бизнес не дотянул по баллам). "
            "Отсутствие точки входа — это тоже результат."
        )
    else:
        show_table(ideas)
        for _, row in ideas.iterrows():
            st.markdown(
                f"**{row['Тикер']}** · {row['Название']} — {row['Вердикт']} · "
                f"скор {row['Скор']:.0f}  \n"
                f"_найдено по: {row['Найдено по']}_  \n{row['Почему']}"
            )

    with st.expander(f"Все проверенные кандидаты — {len(df)}"):
        show_table(df)

st.caption("Не является инвестиционной рекомендацией. Это отправная точка для собственного анализа.")
