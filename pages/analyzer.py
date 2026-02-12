import streamlit as st
import yfinance as yf
import pandas as pd
import time

# --- ЛОГИКА ВЕРДИКТА (ТВОИ ЖЕСТКИЕ ПРАВИЛА) ---
def get_final_verdict(f_score, tech_data):
    if not tech_data: return "⚪️ НЕТ ДАННЫХ"
    
    t_score = tech_data['t_score']
    no_new_low = tech_data['is_no_new_low']

    # 1. ЖЕСТКОЕ ВЕТО: Если нет дна — ЗАПРЕТ без вариантов
    if not no_new_low:
        return "⛔️ ЗАПРЕТ (Нет дна)"
    
    # 2. Если дно есть, работаем по тех. баллу (разрешение на вход)
    if t_score <= 1:
        return "⛔️ ЗАПРЕТ (Слабая техника)"
    elif t_score == 2:
        return "⚠️ РИСК (Начало стабилизации)"
    elif t_score == 3:
        return "🟡 НАЧАЛЬНЫЙ ВХОД (25%)"
    elif t_score == 4:
        # Только если и бизнес отличный, и техника на максимуме
        if f_score >= 7:
            return "🚀 ПОЛНЫЙ ВХОД (Идеал)"
        return "🚀 ПОЛНЫЙ ВХОД (Техн. ракета)"
    
    return "⏳ ЖДАТЬ"

def get_technical_signals(symbol):
    try:
        df = yf.download(symbol, period="60d", interval="1d", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # 1. Проверка Lows (ТВОЙ ЖЕСТКИЙ ФЛАГ)
        current_low = float(df['Low'].iloc[-1])
        min_low_3d = float(df['Low'].iloc[-4:-1].min())
        is_no_new_low = current_low >= min_low_3d

        # 2. RSI (Разворот)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi_today = 100 - (100 / (1 + rs.iloc[-1]))
        rsi_yesterday = 100 - (100 / (1 + rs.iloc[-2]))
        rsi_stable = (rsi_today > rsi_yesterday) if rsi_today < 50 else True

        # 3. Объемы (Падение волатильности)
        avg_vol = df['Volume'].tail(5).mean()
        vol_falling = df['Volume'].iloc[-1] < avg_vol 

        # 4. Откуп (Тень)
        close_p, open_p, low_p = float(df['Close'].iloc[-1]), float(df['Open'].iloc[-1]), float(df['Low'].iloc[-1])
        lower_shadow = min(close_p, open_p) - low_p
        has_tail = lower_shadow > (abs(close_p - open_p) * 1.2)

        # Считаем баллы
        t_score = sum([is_no_new_low, rsi_stable, vol_falling, has_tail])

        return {
            "t_score": t_score,
            "is_no_new_low": is_no_new_low,
            "rsi": round(rsi_today, 1),
            "no_new_low_text": "✅ Держит" if is_no_new_low else "❌ ПРОБИТО",
            "vol_status": "⬇️ Спадает" if vol_falling else "⬆️ Растет",
            "tail": "🎯 Есть" if has_tail else "Нет"
        }
    except: return None

# --- ТАБЛИЦА БЕЗ P/E ---
def full_analysis(tickers):
    results = []
    for symbol in tickers:
        try:
            # 1. Загрузка данных
            stock = yf.Ticker(symbol)
            info = stock.info
            fin, cf = stock.financials, stock.cashflow
            
            if fin.empty or cf.empty:
                st.warning(f"Нет финансовых данных для {symbol}")
                continue

            # 2. ТЕХНИКА (сначала получаем ее!)
            tech = get_technical_signals(symbol)
            t_score = tech['t_score'] if tech else 0

            # 3. БИЗНЕС
            net_inc = fin.loc['Net Income'].iloc[0] if 'Net Income' in fin.index else 0
            ocf = cf.loc['Operating Cash Flow'].iloc[0] if 'Operating Cash Flow' in cf.index else 0
            capex = abs(cf.loc['Capital Expenditure'].iloc[0]) if 'Capital Expenditure' in cf.index else 0
            fcf = ocf - capex
            
            mcap = info.get('marketCap', 0)
            pe = info.get('trailingPE') or (mcap / net_inc if net_inc != 0 else None)

            # Скоринг бизнеса (0-10)
            f_score = 0
            if net_inc > 0: f_score += 3
            if fcf > 0: f_score += 4
            if 0 < (pe or 999) < 30: f_score += 3

            # 4. ВЕРДИКТ
            verdict = get_final_verdict(f_score, tech)

            results.append({
                "Тикер": symbol,
                "ВЕРДИКТ": verdict,
                "Техн. Балл": t_score,
                "Бизнес-балл": f_score,
                "Дно": tech['no_new_low_text'] if tech else "N/A",
                "Объем": tech['vol_status'] if tech else "N/A",
                "RSI": tech['rsi'] if tech else "N/A",
                "Откуп": tech['tail'] if tech else "N/A",
                "Цена": info.get('currentPrice') or info.get('regularMarketPrice'),
                "Yahoo": f"https://finance.yahoo.com/quote/{symbol}"
            })
            time.sleep(1) # Пауза, чтобы Yahoo не забанил
        except Exception as e:
            st.error(f"Ошибка в {symbol}: {e}")
            continue
    return pd.DataFrame(results)

# --- ИНТЕРФЕЙС ---
st.title("🦅 Инвестиционный Радар: Качество + Вход")

user_input = st.text_input("Введите тикеры:", "V, IONQ, RKLB, TSLA, NVDA")
if st.button("🔥 ПРОВЕРИТЬ ВСЁ"):
    tickers = [t.strip().upper() for t in user_input.split(",")]
    with st.spinner('Анализируем отчеты и графики...'):
        df = full_analysis(tickers)
        if not df.empty:
            st.dataframe(df, hide_index=True, column_config={
                "Yahoo": st.column_config.LinkColumn("График", display_text="Open"),
                "Бизнес (0-10)": st.column_config.ProgressColumn("Бизнес", min_value=0, max_value=10),
            })
            st.success("Готово! Не усредняй там, где горит 'ЗАПРЕТ'.")