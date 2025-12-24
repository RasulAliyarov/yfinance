import streamlit as st
import yfinance as yf
import pandas as pd

# Настройка страницы
st.set_page_config(page_title="Stock Analyzer Pro", layout="wide", initial_sidebar_state="collapsed")

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
            
            # Данные из info
            sector = info.get('sector', 'N/A')
            debt_to_equity = info.get('debtToEquity', 0)
            pe = info.get('trailingPE', 0)
            cr = info.get('currentRatio', 0)
            margin = info.get('profitMargins', 0) * 100
            mcap = info.get('marketCap', 0)
            shares = info.get('sharesOutstanding', 0)
            
            # Динамика выручки и прибыли
            rev_current = fin.loc['Total Revenue'].iloc[0]
            rev_prev = fin.loc['Total Revenue'].iloc[1]
            net_inc_current = fin.loc['Net Income'].iloc[0]
            net_inc_prev = fin.loc['Net Income'].iloc[1]
            
            # FCF
            ocf = cf.loc['Operating Cash Flow'].iloc[0]
            capex = abs(cf.loc['Capital Expenditure'].iloc[0])
            fcf = ocf - capex
            p_fcf = mcap / fcf if fcf > 0 else 0
            
            # Дивиденды
            div_paid = abs(cf.loc['Cash Dividends Paid'].iloc[0]) if 'Cash Dividends Paid' in cf.index else 0
            payout_fcf = (div_paid / fcf * 100) if fcf > 0 else 0

            # --- СКОРРИНГ (Баллы) ---
            score = 0
            if rev_current > rev_prev: score += 1
            if net_inc_current > net_inc_prev: score += 1
            if fcf > 0: score += 1
            
            # Логика P/E
            if 0 < pe <= 25: score += 1
            elif pe > 50: score -= 2  # Штраф за пузырь
            
            # Логика P/FCF
            if 0 < p_fcf <= 25: score += 1
            elif p_fcf > 50: score -= 2 # Штраф
            
            if cr > 1.1: score += 1
            if margin > 10: score += 1
            if shares > 0: score += 1
            if debt_to_equity < 100 and debt_to_equity > 0: score += 1 # Балл за низкий долг

            signal = "🚀 КУПИТЬ" if score >= 7 else "👀 ЖДАТЬ" if score >= 5 else "❌ МИМО"

            results.append({
                "Тикер": symbol,
                "Сигнал": signal,
                "Баллы": f"{score}/9",
                "Отрасль": sector,
                "P/E": round(pe, 1) if pe else "N/A",
                "P/FCF": round(p_fcf, 1) if p_fcf else "N/A",
                "Долг/Кап (%)": f"{debt_to_equity:.1f}%" if debt_to_equity else "N/A",
                "Маржа (%)": f"{margin:.1f}%",
                "Выручка": "⬆️" if rev_current > rev_prev else "⬇️",
                "Ликвидность": round(cr, 2),
                "Yahoo": f"https://finance.yahoo.com/quote/{symbol}"
            })
        except Exception as e:
            st.error(f"Ошибка в {symbol}: {e}")
    return pd.DataFrame(results)

# --- ИНТЕРФЕЙС ---
st.title("📈 Smart Stock Analyzer")
st.write("Анализ по 9 критериям + фильтр переоцененности.")

user_input = st.text_input("Введите тикеры (AAPL, MSFT, KO...)", "AAPL, MSFT, NVDA, KO")
tickers = [t.strip().upper() for t in user_input.split(",")]

if st.button("Начать проверку"):
    df = analyze_stocks(tickers)
    if not df.empty:
        # Используем column_config для создания кликабельных ссылок
        st.dataframe(
            df,
            column_config={
                "Yahoo": st.column_config.Link_Column("Ссылка Yahoo")
            },
            hide_index=True,
            use_container_width=True
        )

st.divider()
st.sidebar.header("Как это работает?")
st.sidebar.info("""
1. **P/E > 50** — отнимаем 2 балла (слишком дорого).
2. **Долг > 100%** — нет балла за стабильность.
3. **Маржа > 10%** — плюс 1 балл (эффективность).
""")