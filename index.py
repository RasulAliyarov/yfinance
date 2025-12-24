import yfinance as yf
import pandas as pd

# def analyze_stocks_comprehensive(tickers):
#     results = []

#     for symbol in tickers:
#         print(f"Анализируем {symbol}...")
#         stock = ticker_data.Ticker(symbol)
        
#         try:
#             info = stock.info
#             financials = stock.financials
#             cashflow = stock.cashflow
            
#             # --- 1 & 2. Динамика Выручки и Прибыли ---
#             rev_current = financials.loc['Total Revenue'].iloc[0]
#             rev_prev = financials.loc['Total Revenue'].iloc[1]
#             rev_growth = "⬆️ Растет" if rev_current > rev_prev else "⬇️ Падает"

#             net_inc_current = financials.loc['Net Income'].iloc[0]
#             net_inc_prev = financials.loc['Net Income'].iloc[1]
#             net_inc_growth = "⬆️ Растет" if net_inc_current > net_inc_prev else "⬇️ Падает"

#             # --- 3. FCF (Свободный денежный поток) ---
#             ocf = cashflow.loc['Operating Cash Flow'].iloc[0]
#             capex = abs(cashflow.loc['Capital Expenditure'].iloc[0])
#             fcf = ocf - capex

#             # --- 4. P/E ---
#             pe = info.get('trailingPE', 0)

#             # --- 5. Current Ratio (Ликвидность) ---
#             current_ratio = info.get('currentRatio', 0)

#             # --- 6. Маржа ---
#             margin = info.get('profitMargins', 0) * 100

#             # --- 7. P/FCF ---
#             market_cap = info.get('marketCap', 0)
#             p_fcf = market_cap / fcf if fcf > 0 else "Отриц. FCF"

#             # --- 8. Акции в обращении ---
#             shares_curr = info.get('sharesOutstanding', 0)

#             # --- 9. Выплата дивидендов из FCF ---
#             total_div = abs(cashflow.loc['Cash Dividends Paid'].iloc[0]) if 'Cash Dividends Paid' in cashflow.index else 0
#             payout_fcf = (total_div / fcf * 100) if fcf > 0 else 0

#             # --- ЛОГИКА СИГНАЛА (Скорринг) ---
#             score = 0
#             if rev_current > rev_prev: score += 1
#             if net_inc_current > net_inc_prev: score += 1
#             if fcf > 0: score += 1
#             if 0 < pe < 25: score += 1 # Для 2025 года планку чуть подняли
#             if current_ratio > 1.1: score += 1
#             if margin > 10: score += 1
#             if isinstance(p_fcf, float) and p_fcf < 25: score += 1
#             if payout_fcf < 70: score += 1
            
#             signal = "🚀 КУПИТЬ" if score >= 7 else "👀 НАБЛЮДАТЬ" if score >= 5 else "❌ ПРОПУСТИТЬ"

#             results.append({
#                 "Тикер": symbol,
#                 "Выручка (дин.)": rev_growth,
#                 "Прибыль (дин.)": net_inc_growth,
#                 "FCF ($)": f"{fcf:,.0f}",
#                 "P/E": f"{pe:.2f}" if pe else "N/A",
#                 "Current Ratio": f"{current_ratio:.2f}",
#                 "Маржа (%)": f"{margin:.2f}%",
#                 "P/FCF": f"{p_fcf:.2f}" if isinstance(p_fcf, float) else p_fcf,
#                 "Акции в обращении": f"{shares_curr:,.0f}",
#                 "Див/FCF (%)": f"{payout_fcf:.2f}%",
#                 "Сигнал": signal
#             })
            
#         except Exception as e:
#             print(f"Ошибка с {symbol}: {e}")

#     return pd.DataFrame(results)



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
            
            # Вместо простого наличия P/E, вводим штраф за дороговизну
            if 0 < pe <= 25: 
                score += 1  # Отличная цена (как в видео)
            elif 25 < pe <= 50:
                score += 0  # Приемлемо для растущих компаний, но без бонуса
            else:
                score -= 2  # ШТРАФ: Акция слишком дорогая, риск пузыря!

            # То же самое для P/FCF
            if isinstance(p_fcf, float) and p_fcf > 50:
                score -= 2  # Если цена к денежному потоку огромная — это риск
           

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
        except Exception as e:
            print(f"Ошибка с {symbol}: {e}")

    return pd.DataFrame(results)


# Тестовый массив
my_portfolio = ["CCJ", "CRDO", "APLD"]
df = analyze_stocks(my_portfolio)

# print("\n", df.to_string(index=False))