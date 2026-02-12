import streamlit as st
import yfinance as yf
import pandas as pd
import time

st.title("Smart Entry Terminal")
st.write("Страница анализа входов 💰")


def get_technical_signals(symbol):
    try:
        # Загружаем данные
        df = yf.download(symbol, period="60d", interval="1d", progress=False)
        
        # Исправление MultiIndex (если yfinance выдает колонки типа ('Low', 'IONQ'))
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        if df.empty or len(df) < 20:
            return None

        # 1. Проверка Lows (Замедление падения)
        current_low = float(df['Low'].iloc[-1])
        # Минимум за 3 предыдущих дня (не включая сегодня)
        min_low_3d = float(df['Low'].iloc[-4:-1].min())
        no_new_lows = current_low >= min_low_3d

        # 2. RSI (14) - классический расчет
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi_series = 100 - (100 / (1 + rs))
        
        rsi_today = float(rsi_series.iloc[-1])
        rsi_yesterday = float(rsi_series.iloc[-2])
        # Сигнал: в зоне перепроданности и разворачивается вверх
        rsi_stable = (rsi_today > rsi_yesterday) if rsi_today < 40 else False

        # 3. Объемы (Затухание паники)
        avg_vol = df['Volume'].tail(5).mean()
        current_vol = df['Volume'].iloc[-1]
        vol_decreasing = current_vol < avg_vol 
        
        # 4. Свечной анализ (Откуп)
        close_p = float(df['Close'].iloc[-1])
        open_p = float(df['Open'].iloc[-1])
        low_p = float(df['Low'].iloc[-1])
        body = abs(close_p - open_p)
        lower_shadow = min(close_p, open_p) - low_p
        # Если тень длиннее тела — значит, был сильный выкуп
        has_tail = lower_shadow > (body * 1.2) if body > 0 else lower_shadow > 0

        tech_score = 0
        if no_new_lows: tech_score += 1
        if rsi_stable: tech_score += 1
        if vol_decreasing: tech_score += 1
        if has_tail: tech_score += 1

        return {
            "tech_score": tech_score,
            "rsi": round(rsi_today, 1),
            "no_new_low": "✅" if no_new_lows else "❌ Провал",
            "vol_status": "⬇️ Спадает" if vol_decreasing else "⬆️ Растет",
            "tail": "🎯 Есть" if has_tail else "Нет"
        }
    except Exception as e:
        print(f"Тех. ошибка для {symbol}: {e}")
        return None

def analyze_v3(tickers):
    results = []
    for symbol in tickers:
        try:
            stock = yf.Ticker(symbol)
            # Технический блок
            tech = get_technical_signals(symbol)
            
            # Фундаментальный блок (упрощенно для примера)
            info = stock.info
            price = info.get('regularMarketPrice') or info.get('currentPrice')
            
            # Логика сигналов
            t_score = tech['tech_score'] if tech else 0
            
            if t_score >= 3:
                status = "🚀 ВХОД (Стабильно)"
            elif t_score == 2:
                status = "👀 ПРИСМОТРЕТЬСЯ"
            elif t_score == 1:
                status = "⚠️ СЛАБОСТЬ"
            else:
                status = "❌ ПАДЕНИЕ"

            results.append({
                "Тикер": symbol,
                "Сигнал": status,
                "Техн. Балл (0-4)": t_score,
                "RSI": tech['rsi'] if tech else "N/A",
                "Нет новых лоев": tech['no_new_low'] if tech else "N/A",
                "Объем": tech['vol_status'] if tech else "N/A",
                "Откуп (Тень)": tech['tail'] if tech else "N/A",
                "Цена": f"{round(price, 2)}" if price else "N/A"
            })
            time.sleep(1)
        except Exception as e:
            st.error(f"Ошибка по {symbol}: {e}")
    return pd.DataFrame(results)

user_input = st.text_input("Введите тикеры:", "IONQ, RKLB, TSLA, NVDA")
if st.button("Проверить сигналы"):
    tickers = [t.strip().upper() for t in user_input.split(",")]
    with st.spinner('Считаем индикаторы...'):
        df_res = analyze_v3(tickers)
        # st.table(df_res) 
        st.dataframe(
            df_res,
            hide_index=True,
            width='stretch'
        )
        
        import streamlit as st
        
        
        
        
        
        
        
        
        
        
        
st.text("""
        2. Технические фильтры (Автоматизация)
Чтобы не сидеть в мониторе, используй алерты в TradingView (комбо из 2+ сигналов):

Цена: Нет новых минимумов (Low) в течение 3–5 дней. Падение замедлилось.

RSI: Выход из зоны перепроданности (пересечение 20 или 25 снизу вверх).

Волатильность: Снижение ATR. Рынок перестает «истерить».

3. Визуальное подтверждение (Глазами)
Когда алерты сработали, ищем на графике признаки силы:

Структура: Появление Higher Low (новый минимум выше предыдущего) или Double Bottom (двойное дно на одном уровне).

Свечи: Длинные нижние тени («фитили») — признак того, что покупатели выкупают просадку внутри дня.

Объем: Падение объемов после паники. Это значит, что продавцы иссякли, а остались только те, кто готов держать.

4. Чек-лист перед сделкой
Можно входить, если соблюдены минимум 3 условия:

[ ] Цена не обновляла лой 2–3 дня.

[ ] Появились свечи откупа (тени снизу).

[ ] Объемы торгов снижаются (затишье перед разворотом).

[ ] Общий фон рынка стабилен.
        """)