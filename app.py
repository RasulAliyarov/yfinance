import streamlit as st
import yfinance as yf
import pandas as pd
from io import BytesIO

# Настройка страницы
st.set_page_config(page_title="Stock Analyzer Pro", layout="wide")

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Stock_Analysis')
    return output.getvalue()

def analyze_stocks(tickers):
    results = []
    for symbol in tickers:
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            fin = stock.financials
            cf = stock.cashflow
            
            # --- 1. Сбор базовых данных ---
            mcap = info.get('marketCap', 0)
            pe = info.get('trailingPE', 0)
            margin = info.get('profitMargins', 0) * 100
            total_debt = info.get('totalDebt', 0)
            cr = info.get('currentRatio', 0)
            payout_ratio = info.get('payoutRatio', 0)
            
            # Разделяем Выручку и Чистую прибыль (Income)
            rev_current = fin.loc['Total Revenue'].iloc[0]
            rev_prev = fin.loc['Total Revenue'].iloc[1]
            net_inc_current = fin.loc['Net Income'].iloc[0]
            net_inc_prev = fin.loc['Net Income'].iloc[1]
            
            # Свободный денежный поток (FCF) и Долг к рынку
            ocf = cf.loc['Operating Cash Flow'].iloc[0]
            capex = abs(cf.loc['Capital Expenditure'].iloc[0])
            fcf = ocf - capex
            
            # Честный расчет P/FCF (может быть отрицательным)
            p_fcf = mcap / fcf if fcf != 0 else 0
            debt_market_ratio = (total_debt / mcap * 100) if mcap > 0 else 0

            # --- 2. Работа с дивидендами (Trailing - как в Trading 212) ---
            div_yield_raw = info.get('trailingAnnualDividendYield', 0)
            if not div_yield_raw:
                div_yield_raw = info.get('dividendYield', 0)
            div_yield = div_yield_raw * 100 if div_yield_raw else 0

            # --- 3. Скорринг (Логика баллов) ---
            score = 0
            if rev_current > rev_prev: score += 1      # Рост продаж
            if net_inc_current > net_inc_prev: score += 1 # Рост прибыли
            if fcf > 0: score += 1                     # Положительный поток
            
            # Фильтр цены (P/E)
            if 0 < pe <= 25: score += 1
            elif pe > 50 or pe < 0: score -= 2         # Штраф за пузырь или убыток
            
            if 0 < p_fcf <= 25: score += 1
            if cr > 1.1: score += 1
            if margin > 15: score += 1
            if debt_market_ratio < 20: score += 1
            
            # Логика дивидендов
            if div_yield > 0:
                score += 1
                if 0 < payout_ratio < 0.7: score += 1  # Надежно
                elif payout_ratio > 1.0: score -= 2    # Рискованно (платят в долг)

            signal = "🚀 КУПИТЬ" if score >= 7 else "👀 ЖДАТЬ" if score >= 5 else "❌ МИМО"

            # --- 4. Формирование результата ---
            results.append({
                "Тикер": symbol,
                "Сигнал": signal,
                "Баллы": f"{score}/10",
                "Капитализация": f"${mcap/1e9:.1f}B",
                "Див. доходность (%)": round(div_yield, 2),
                "P/E": round(pe, 1) if pe else "Убыток",
                "P/FCF": round(p_fcf, 1) if p_fcf else "N/A",
                "Маржа (%)": round(margin, 1),
                "Выручка": "⬆️" if rev_current > rev_prev else "⬇️",
                "Прибыль": "⬆️" if net_inc_current > net_inc_prev else "⬇️",
                "Долг/Рынок (%)": round(debt_market_ratio, 1),
                "Yahoo": f"https://finance.yahoo.com/quote/{symbol}"
            })
        except Exception as e:
            st.error(f"Ошибка в данных {symbol}: {e}")
    return pd.DataFrame(results)

# --- ИНТЕРФЕЙС STREAMLIT ---
st.title("📊 Финансовый Терминал: История и Перспективы")

user_input = st.text_input("Введите тикеры (через запятую):", "V, MA, KO, TSLA")
tickers = [t.strip().upper() for t in user_input.split(",")]

if st.button("Запустить анализ"):
    with st.spinner('Анализирую отчетность...'):
        df = analyze_stocks(tickers)
        
        if not df.empty:
            # Сортировка по баллам (опционально)
            df['score_num'] = df['Баллы'].str.split('/').str[0].astype(int)
            df = df.sort_values(by='score_num', ascending=False).drop(columns=['score_num'])

            # Кнопка Excel
            excel_data = to_excel(df)
            st.download_button(label='📥 Скачать отчет в Excel',
                               data=excel_data,
                               file_name='stock_analysis.xlsx',
                               mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            
            # Отображение таблицы
            st.dataframe(
                df,
                column_config={
                    "Yahoo": st.column_config.LinkColumn("Yahoo Link", display_text="Открыть"),
                    "Баллы": st.column_config.TextColumn("🏆 Рейтинг"),
                    "Див. доходность (%)": st.column_config.NumberColumn("Дивиденды", format="%.2f%% 💰")
                },
                hide_index=True,
                use_container_width=True
            )
            st.success("Анализ завершен! Самые сильные компании вверху списка.")


st.divider()
st.sidebar.header("Как это работает?")
st.sidebar.info("""
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

Ликвидность: Если > 1.1, у компании нет проблем с наличностью на операционку.

Как пользоваться таблицей для сравнения (лайфхак):
Если ты вводишь, например, V и MA, смотри на них в таком порядке:

Сначала Сигнал и Баллы: Кто из них набрал больше? (Это первичный фильтр).

Затем P/E: Кто из них дешевле относительно своей прибыли?

Затем Долг/Рынок: Кто из них меньше обременен долгами?

Пример из твоего скриншота: У V и MA баллы одинаковые (6/9). Но у V показатель P/E чуть ниже (34.6 против 36.9) и маржа чуть выше (50% против 45%). Значит, исторически и фундаментально Visa выглядит чуть привлекательнее на данный момент, хотя обе компании отличные.
""")
