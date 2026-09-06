"""Анализ акций: фундаментал (Ticker.info) + техника (батч котировок) + вердикт."""
from .config import GOOD_VERDICTS, WATCHLIST
from .data import clear_cache
from .discovery import STRATEGY_NAMES, discover, sources_map
from .screener import analyze, opportunities

__all__ = [
    "analyze",
    "opportunities",
    "discover",
    "sources_map",
    "STRATEGY_NAMES",
    "clear_cache",
    "WATCHLIST",
    "GOOD_VERDICTS",
]
