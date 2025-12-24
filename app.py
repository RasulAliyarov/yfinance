import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Stock Analyzer Pro", layout="wide")

def analyze_stocks(tickers):
    results = []
    for symbol in tickers:
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            fin = stock.financials
            cf = stock.cashflow
            
            # Базовые данные
            sector = info.get('sector', 'N/A')
            pe = info.get('trailingPE', 0)
            debt_to_equity = info.get('debtToEquity', 0)
            margin = info.get('profitMargins', 0) * 100
            cr = info.get('currentRatio', 0)
            mcap = info.get('marketCap', 0)
            
            # Динамика
            rev_current = fin.loc['Total Revenue'].iloc[0]
            rev_prev = fin.loc['Total Revenue'].iloc[1]
            net_inc_current = fin.loc['Net Income'].iloc[0]
            net_inc_prev = fin.loc['Net Income'].iloc[1]
            
            # FCF
            ocf = cf.loc['Operating Cash Flow'].iloc[0]
            capex = abs(cf.loc['Capital Expenditure'].iloc[0])
            fcf = ocf - capex
            p_fcf = mcap / fcf if fcf > 0 else 0

            # Скорринг
            score = 0
            if rev_current > rev_prev: score += 1
            if net_inc_current > net_inc_prev: score += 1
            if fcf > 0: score += 1
            if 0 < pe <= 25: score += 1
            elif pe > 50: score -= 2
            if 0 < p_fcf <= 25: score += 1
            elif p_fcf > 50: score -= 2
            if cr > 1.1: score += 1
            if margin > 10: score += 1
            if debt_to_equity < 100 and debt_to_equity > 0: score += 1
            if (abs(cf.loc['Cash Dividends Paid'].iloc[0]) / fcf < 0.7 if 'Cash Dividends Paid' in cf.index and fcf > 0 else True): score += 1

            signal = "🚀 КУПИТЬ" if score >= 7 else "👀 ЖДАТЬ" if score >= 5 else "❌ МИМО"

            # Формируем словарь (Тикер теперь просто текст, ссылку сделаем через конфиг)
            results.append({
                "Тикер": symbol,
                "Сигнал": signal,
                "Баллы": score,
                "Отрасль": sector,
                "P/E": round(pe, 1) if pe else 0,
                "P/FCF": round(p_fcf, 1) if p_fcf else 0,
                "Долг/Кап (%)": round(debt_to_equity, 1) if debt_to_equity else 0,
                "Маржа (%)": round(margin, 1),
                "Выручка": "⬆️" if rev_current > rev_prev else "⬇️",
                "Ликвидность": round(cr, 2),
                "Yahoo": f"https://finance.yahoo.com/quote/{symbol}"
            })
        except:
            st.error(f"Ошибка в данных {symbol}")
    return pd.DataFrame(results)

# --- ИНТЕРФЕЙС ---
st.title("🚀 Анализатор акций по 9 пунктам")

user_input = st.text_input("Введите тикеры:", "AAPL, MSFT, KO, NVDA, CRDO")
tickers = [t.strip().upper() for t in user_input.split(",")]

if st.button("Начать анализ"):
    df = analyze_stocks(tickers)
    
    if not df.empty:
        # Функция для окрашивания ячеек
        def highlight_signal(val):
            if val == "🚀 КУПИТЬ": return 'background-color: #053e05'
            if val == "❌ МИМО": return 'background-color: #4e0505'
            return ''

        # Применяем стиль и выводим таблицу
        st.dataframe(
            df.style.applymap(highlight_signal, subset=['Сигнал']),
            column_config={
                "Yahoo": st.column_config.LinkColumn("Yahoo Link", display_text="Открыть"),
                "Баллы": st.column_config.NumberColumn("Баллы", format="%d/9 🏆"),
                "Долг/Кап (%)": st.column_config.ProgressColumn("Долг/Кап (%)", min_value=0, max_value=200, format="%.1f%%")
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
st.sidebar.info("""
Высокая маржа (>20%) при низком долге (<50%) — это "дойная корова" (Cash Cow), такие компании обычно самые надежные.
Если выручка ⬆️, но P/FCF > 50, компания растет, но ты за этот рост платишь двойную цену.
""")
st.divider()