"""Ручной анализ: пользователь вводит тикеры, получает таблицу и разбор."""
from __future__ import annotations

import streamlit as st

from analysis import WATCHLIST, clear_cache
from analysis.screener import analyze
from analysis.ui import show_breakdown, show_table

st.set_page_config(page_title="Ручной анализ", page_icon="🔎", layout="wide")
st.title("🔎 Ручной анализ акций")

tickers_raw = st.text_input("Тикеры через запятую", ", ".join(WATCHLIST))

col1, col2, col3 = st.columns(3)
period = col1.selectbox("Период графика", ["3mo", "6mo", "1y"], index=1)
low_window = col2.slider("Окно проверки дна, дней", 3, 7, 4,
                         help="Сколько предыдущих дней сравниваем с сегодняшним минимумом")
col3.write("")
col3.write("")
if col3.button("↻ Обновить данные", help="Сбросить кэш и перекачать котировки и отчётность"):
    clear_cache()
    st.toast("Кэш очищен")

if st.button("Анализировать", type="primary"):
    tickers = [t.strip().upper() for t in tickers_raw.split(",") if t.strip()]
    if not tickers:
        st.warning("Введите хотя бы один тикер.")
        st.stop()

    with st.spinner("Считаю фундаментал и технику…"):
        df, details = analyze(tickers, price_period=period, low_window=low_window)

    if df.empty:
        st.error("Не удалось получить данные ни по одному тикеру.")
        st.stop()

    missing = sorted(set(tickers) - set(df["Тикер"]))
    if missing:
        st.warning("Нет данных: " + ", ".join(missing))

    show_table(df)

    st.subheader("Разбор по компаниям")
    for ticker in df["Тикер"]:
        fund, outlook, tech = details[ticker]
        show_breakdown(ticker, fund, outlook, tech)

st.caption("Не является инвестиционной рекомендацией.")
