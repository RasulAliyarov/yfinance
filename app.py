import streamlit as st
import yfinance as yf
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Stock Analyzer Pro", layout="wide")

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Stock_Analysis')
    return output.getvalue()

def analyze_stocks_v2(tickers):
    results = []
    for symbol in tickers:
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            fin = stock.financials
            cf = stock.cashflow

            if fin.empty or cf.empty:
                continue

            fin = fin.sort_index(axis=1, ascending=False)
            cf = cf.sort_index(axis=1, ascending=False)

            # Данные
            rev_current = fin.loc['Total Revenue'].iloc[0]
            rev_prev = fin.loc['Total Revenue'].iloc[1] if fin.shape[1] > 1 else 0
            net_inc_current = fin.loc['Net Income'].iloc[0]
            net_inc_prev = fin.loc['Net Income'].iloc[1] if fin.shape[1] > 1 else 0
            
            ocf = cf.loc['Operating Cash Flow'].iloc[0]
            capex = abs(cf.loc['Capital Expenditure'].iloc[0])
            fcf = ocf - capex

            mcap = info.get('marketCap', 0)
            total_debt = info.get('totalDebt', 0)
            current_ratio = info.get('currentRatio', 0)
            margin = (net_inc_current / rev_current * 100) if rev_current else 0

            # --- ИСПРАВЛЕННЫЙ P/E (показывает минус) ---
            pe = info.get('trailingPE')
            if pe is None or pe == 0:
                pe = mcap / net_inc_current if net_inc_current != 0 else None

            # --- ИСПРАВЛЕННЫЙ P/FCF (показывает минус) ---
            p_fcf = mcap / fcf if fcf != 0 else None

            debt_market = (total_debt / mcap * 100) if mcap else 0
            
            div_yield = info.get('trailingAnnualDividendYield', 0)
            div_yield = div_yield * 100 if div_yield else 0
            payout_ratio = info.get('payoutRatio', 0)

            # Определение режима
            if net_inc_current > 0:
                mode = "PROFITABLE"
            elif rev_current > rev_prev:
                mode = "GROWTH"
            else:
                mode = "VENTURE"

            # СКОРИНГ
            score = 0
            if rev_current > rev_prev: score += 1
            if current_ratio > 1.2: score += 1
            if debt_market < 30: score += 1

            if mode == "PROFITABLE":
                score += 2
                if net_inc_current > net_inc_prev: score += 1
                if fcf > 0: score += 1
                if pe and 0 < pe <= 25: score += 1
                elif pe and (pe > 50 or pe < 0): score -= 2
                if margin > 15: score += 1
                if div_yield > 0:
                    score += 1
                    if 0 < payout_ratio < 0.7: score += 1
                    elif payout_ratio > 1: score -= 2
            elif mode == "GROWTH":
                score += 1
                if fcf > 0: score += 2
                if margin > -20: score += 1
            else:
                score -= 1
                if rev_current > 0: score += 1
                if total_debt == 0: score += 1

            signal = "🚀 КУПИТЬ" if score >= 7 else "👀 ЖДАТЬ" if score >= 5 else "❌ МИМО"

            results.append({
                "Тикер": symbol,
                "Режим": mode,
                "Сигнал": signal,
                "Баллы": score,
                "Капитализация ($B)": round(mcap / 1e9, 2),
                "P/E": round(pe, 1) if pe is not None else "N/A",
                "P/FCF": round(p_fcf, 1) if p_fcf is not None else "N/A",
                "Маржа (%)": round(margin, 1),
                "FCF": "✅" if fcf > 0 else "❌",
                "Выручка": "⬆️" if rev_current > rev_prev else "⬇️",
                "Прибыль": "⬆️" if net_inc_current > net_inc_prev else "⬇️",
                "Долг/Рынок (%)": round(debt_market, 1),
                "Дивиденды (%)": round(div_yield, 2),
                "Yahoo": f"https://finance.yahoo.com/quote/{symbol}" 
            })
        except Exception as e:
            st.warning(f"Ошибка тикера {symbol}: {e}")

    return pd.DataFrame(results)

# --- ИНТЕРФЕЙС ---
st.title("📊 Финансовый Терминал")

user_input = st.text_input("Введите тикеры:", "V, MA")
tickers = [t.strip().upper() for t in user_input.split(",")]
mode_filter = st.selectbox("🎯 Режим анализа:", options=["ALL", "PROFITABLE", "GROWTH", "VENTURE"])


if st.button("Запустить анализ"):
    with st.spinner('Загрузка...'):
        df = analyze_stocks_v2(tickers)

        if not df.empty:
            # ФИЛЬТРАЦИЯ (Теперь без KeyError)
            if mode_filter != "ALL":
                df = df[df["Режим"] == mode_filter]

            df = df.sort_values(by="Баллы", ascending=False)

            excel_data = to_excel(df)
            st.download_button(label='📥 Excel', data=excel_data, file_name='analysis.xlsx')

            # Красивое отображение
            st.dataframe(
                df,
                column_config={
                    "Баллы": st.column_config.NumberColumn("🏆 Рейтинг"),
                    "Дивиденды (%)": st.column_config.NumberColumn("Див %", format="%.2f%%"),
                    "P/E": st.column_config.TextColumn("P/E (Минус = Убыток)"),
                    "Yahoo": st.column_config.LinkColumn("Yahoo Link", display_text="Открыть"),
                },
                hide_index=True,
                width='stretch'

            )


st.divider()
st.sidebar.header("Как это работает?")
st.text("""
1. Блок «История и Качество» (Что уже произошло?)
Этот блок отвечает на вопрос: «Умеет ли этот бизнес зарабатывать деньги?»

Выручка и Прибыль (динамика): Если здесь ⬆️, значит, компания востребована на рынке.

Маржа (%): Твой главный фильтр качества. Если маржа > 20%, у компании есть «ров» (конкурентное преимущество).

FCF (Свободный кэш): Если он положительный, компания живет на свои деньги, а не на подачки банков.

2. Блок «Оценка» (Не слишком ли дорого?)
Этот блок отвечает на вопрос: «Адекватна ли цена за это качество?»

P/E и P/FCF: Твои стоп-краны. Если они красные (выше 25-30), то даже супер-акция (как твоя CRDO) сейчас плохая покупка, потому что ты переплачиваешь.

Капитализация: Помогает понять потенциал роста. Компании на $10B вырасти в 2 раза легче, чем гиганту на $3T (Apple).

3. Блок «Риски и Перспективы» (Что может пойти не так?)
Этот блок отвечает на вопрос: «Выживет ли компания в кризис?»

Долг/Рынок (%): Если он < 20%, компания финансово неубиваема.

Как пользоваться таблицей для сравнения (лайфхак):
Если ты вводишь, например, V и MA, смотри на них в таком порядке:

Сначала Сигнал и Баллы: Кто из них набрал больше? (Это первичный фильтр).

Затем P/E: Кто из них дешевле относительно своей прибыли?

Затем Долг/Рынок: Кто из них меньше обременен долгами?

Пример из твоего скриншота: У V и MA баллы одинаковые (6/9). Но у V показатель P/E чуть ниже (34.6 против 36.9) и маржа чуть выше (50% против 45%). Значит, исторически и фундаментально Visa выглядит чуть привлекательнее на данный момент, хотя обе компании отличные.
""")
