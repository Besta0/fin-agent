from __future__ import annotations

from typing import Any

import pandas as pd


def _round(value: Any, digits: int = 2):
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _period_return(close: pd.Series, days: int) -> float | None:
    if len(close) <= days:
        return None
    latest = close.iloc[-1]
    previous = close.iloc[-days - 1]
    if previous == 0 or pd.isna(previous):
        return None
    return _round((latest / previous - 1) * 100)


def _serialize_prices(history: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, row in history.iterrows():
        rows.append(
            {
                "date": idx.strftime("%Y-%m-%d"),
                "open": _round(row.get("Open")),
                "high": _round(row.get("High")),
                "low": _round(row.get("Low")),
                "close": _round(row.get("Close")),
                "volume": int(row.get("Volume", 0) or 0),
            }
        )
    return rows


def get_market_snapshot(ticker: str, period: str = "1y") -> dict[str, Any]:
    try:
        import yfinance as yf
    except ImportError as exc:
        return {"ok": False, "ticker": ticker, "error": f"yfinance is not installed: {exc}"}

    try:
        stock = yf.Ticker(ticker)
        history = stock.history(period=period, interval="1d", auto_adjust=False)
    except Exception as exc:
        return {"ok": False, "ticker": ticker, "error": str(exc)}

    if history.empty or "Close" not in history:
        return {"ok": False, "ticker": ticker, "error": "No price history returned."}

    history = history.dropna(subset=["Close"])
    close = history["Close"]
    last = history.iloc[-1]

    return {
        "ok": True,
        "ticker": ticker,
        "currency": getattr(stock, "fast_info", {}).get("currency", "USD"),
        "last_close": _round(last.get("Close")),
        "last_open": _round(last.get("Open")),
        "last_high": _round(last.get("High")),
        "last_low": _round(last.get("Low")),
        "last_volume": int(last.get("Volume", 0) or 0),
        "fifty_two_week_high": _round(close.max()),
        "fifty_two_week_low": _round(close.min()),
        "returns": {
            "1d": _period_return(close, 1),
            "5d": _period_return(close, 5),
            "1m": _period_return(close, 21),
            "3m": _period_return(close, 63),
            "6m": _period_return(close, 126),
        },
        "prices": _serialize_prices(history.tail(180)),
    }
