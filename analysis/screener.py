"""Сборка таблицы анализа и отбор перспективных идей."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import pandas as pd

from .config import GOOD_VERDICTS
from .data import get_info, get_price_history
from .fundamentals import mode_ru, score_fundamentals
from .outlook import get_forward_data, score_outlook
from .technicals import score_technicals
from .verdict import VERDICT_RANK, combined_score, decide

ProgressCB = Callable[[int, int], None]


def _clean(tickers) -> list[str]:
    return list(dict.fromkeys(
        t.strip().upper() for t in tickers if t and t.strip()
    ))


def _fetch_bundle(ticker: str) -> tuple[dict, dict]:
    """Один тикер: (info, forward_data). Оба запроса кэшируются по отдельности."""
    return get_info(ticker), get_forward_data(ticker)


def _fetch_all(tickers: list[str], on_progress: ProgressCB | None) -> list[tuple[dict, dict]]:
    """Параллельно тянем info + прогнозы по всем тикерам, сохраняя порядок."""
    total = len(tickers)
    results: list[tuple[dict, dict]] = [({}, {}) for _ in tickers]

    def worker(index: int) -> tuple[int, tuple[dict, dict]]:
        return index, _fetch_bundle(tickers[index])

    try:
        from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
        import threading

        ctx = get_script_run_ctx()

        def init_thread():
            add_script_run_ctx(threading.current_thread(), ctx)

        done = 0
        with ThreadPoolExecutor(max_workers=min(8, total), initializer=init_thread) as pool:
            futures = [pool.submit(worker, i) for i in range(total)]
            for future in as_completed(futures):
                index, bundle = future.result()
                results[index] = bundle
                done += 1
                if on_progress:
                    on_progress(done, total)
    except Exception:                       # нет Streamlit-контекста — последовательно
        for i in range(total):
            results[i] = _fetch_bundle(tickers[i])
            if on_progress:
                on_progress(i + 1, total)
    return results


def _price(value, currency) -> str:
    if not value:
        return "—"
    return f"{value:,.2f} {currency or ''}".strip()


def analyze(
    tickers,
    price_period: str = "6mo",
    low_window: int = 4,
    on_progress: ProgressCB | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Проанализировать список тикеров.

    Возвращает (таблица, {тикер: (fund, outlook, tech)}). Таблица отсортирована
    по общему баллу по убыванию.
    """
    tickers = _clean(tickers)
    if not tickers:
        return pd.DataFrame(), {}

    prices = get_price_history(tuple(tickers), price_period)
    bundles = _fetch_all(tickers, on_progress)

    rows, details = [], {}
    for ticker, (info, fwd) in zip(tickers, bundles):
        if not info:
            continue

        fund = score_fundamentals(info)
        outlook = score_outlook(info, fwd)
        ohlc = prices.get(ticker)
        tech = score_technicals(ohlc, low_window) if ohlc is not None else None
        verdict, why = decide(fund, outlook, tech)
        m = fund.metrics

        rows.append({
            "Тикер": ticker,
            "Название": m["name"] or "",
            "Сектор": m["sector"] or "",
            "Цена": _price(m["price"], m["currency"]),
            "Режим": mode_ru(fund.mode),
            "Вердикт": verdict,
            "Скор": combined_score(fund, outlook, tech),
            "Прошлое": fund.value,
            "Перспектива": outlook.value if outlook else None,
            "Техника": tech.value if tech else None,
            "RSI": tech.rsi if tech else None,
            "P/E": round(m["pe"], 1) if m["pe"] else None,
            "P/FCF": round(m["pfcf"], 1) if m["pfcf"] else None,
            "Маржа %": round(m["margin"] * 100, 1) if m["margin"] is not None else None,
            "Выручка г/г %": round(m["rev_growth"] * 100, 1) if m["rev_growth"] is not None else None,
            "Прогноз EPS +1г %": round(outlook.metrics["eps_growth_1y"] * 100, 1)
            if (outlook and outlook.metrics.get("eps_growth_1y") is not None) else None,
            "Див. дох. %": round(m["div_yield"], 2) if m["div_yield"] else None,
            "Кап-я $B": round(m["mcap"] / 1e9, 1) if m["mcap"] else None,
            "Почему": why,
            "Yahoo": f"https://finance.yahoo.com/quote/{ticker}",
        })
        details[ticker] = (fund, outlook, tech)

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Скор", ascending=False, ignore_index=True)
    return df, details


def opportunities(df: pd.DataFrame) -> pd.DataFrame:
    """Отфильтровать таблицу до тикеров с сигналом на вход, лучшие сверху."""
    if df.empty:
        return df
    picked = df[df["Вердикт"].isin(GOOD_VERDICTS)].copy()
    if picked.empty:
        return picked
    picked["_rank"] = picked["Вердикт"].map(VERDICT_RANK)
    picked = picked.sort_values(["_rank", "Скор"], ascending=[True, False], ignore_index=True)
    return picked.drop(columns="_rank")
