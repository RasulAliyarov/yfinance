import streamlit as st
import yfinance as yf
import pandas as pd

# Настройка страницы
st.set_page_config(page_title="Stock Analyzer Pro", layout="wide", initial_sidebar_state="collapsed")

# Кастомный CSS для красоты
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stDataFrame { border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

def analyze_stocks(tickers):
    results = []
    for symbol in tickers:
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            fin = stock.financials
            cf = stock.cashflow
            
            # Данные для анализа (9 пунктов)
            # 1 & 2. Динамика
            rev_current = fin.loc['Total Revenue'].iloc[0]
            rev_prev = fin.loc['Total Revenue'].iloc[1]
            net_inc_current = fin.loc['Net Income'].iloc[0]
            net_inc_prev = fin.loc['Net Income'].iloc[1]
            
            # 3. FCF
            ocf = cf.loc['Operating Cash Flow'].iloc[0]
            capex = abs(cf.loc['Capital Expenditure'].iloc[0])
            fcf = ocf - capex
            
            # 4. P/E
            pe = info.get('trailingPE', 0)
            
            # 5. Ликвидность
            cr = info.get('currentRatio', 0)
            
            # 6. Маржа
            margin = info.get('profitMargins', 0) * 100
            
            # 7. P/FCF
            mcap = info.get('marketCap', 0)
            p_fcf = mcap / fcf if fcf > 0 else 0
            
            # 8. Акции
            shares = info.get('sharesOutstanding', 0)
            
            # 9. Дивиденды
            div_paid = abs(cf.loc['Cash Dividends Paid'].iloc[0]) if 'Cash Dividends Paid' in cf.index else 0
            payout_fcf = (div_paid / fcf * 100) if fcf > 0 else 0

            # Скорринг (Баллы)
            score = 0
            if rev_current > rev_prev: score += 1
            if net_inc_current > net_inc_prev: score += 1
            if fcf > 0: score += 1
            if 0 < pe < 25: score += 1
            if cr > 1.1: score += 1
            if margin > 10: score += 1
            if 0 < p_fcf < 25: score += 1
            if shares > 0: score += 1
            if payout_fcf < 70: score += 1
            
            signal = "🚀 КУПИТЬ" if score >= 7 else "👀 ЖДАТЬ" if score >= 5 else "❌ МИМО"

            results.append({
                "Тикер": symbol,
                "Баллы": f"{score}/9",
                "Выручка": "⬆️" if rev_current > rev_prev else "⬇️",
                "Прибыль": "⬆️" if net_inc_current > net_inc_prev else "⬇️",
                "FCF ($)": f"{fcf:,.0f}",
                "P/E": round(pe, 2) if pe else "N/A",
                "Ликвидность": round(cr, 2),
                "Маржа (%)": f"{margin:.1f}%",
                "P/FCF": round(p_fcf, 2) if p_fcf else "N/A",
                "Див/FCF (%)": f"{payout_fcf:.1f}%",
                "Сигнал": signal
            })
        except:
            st.warning(f"Не удалось получить полные данные для {symbol}")
    return pd.DataFrame(results)

# Интерфейс
st.title("📊 Финансовый Аналитик (Метод 9 шагов)")
st.subheader("Автоматический фундаментальный анализ по данным Yahoo Finance")

user_input = st.text_input("Введите тикеры компаний через запятую (например: AAPL, MSFT, GOOGL, NVDA, KO, INTC)", "AAPL, MSFT, KO")
tickers = [t.strip().upper() for t in user_input.split(",")]

if st.button("Запустить анализ"):
    with st.spinner('Анализирую отчетность...'):
        df = analyze_stocks(tickers)
        if not df.empty:
            # Красивое отображение таблицы
            st.table(df)
            
            # Сводка
            st.success("Анализ завершен!")
            col1, col2 = st.columns(2)
            with col1:
                st.info("🚀 КУПИТЬ: Хорошие показатели + адекватная цена.")
            with col2:
                st.info("❌ МИМО: Высокие риски или переоцененность.")