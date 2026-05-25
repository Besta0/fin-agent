from __future__ import annotations

from typing import Any

import pandas as pd


def _round(value: Any, digits: int = 2):
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_technicals(prices: list[dict[str, Any]]) -> dict[str, Any]:
    if not prices:
        return {
            "ok": False,
            "trend_label": "暂无行情数据，无法计算技术指标",
            "error": "No prices provided.",
        }

    frame = pd.DataFrame(prices)
    if "close" not in frame:
        return {
            "ok": False,
            "trend_label": "价格数据缺少 close 字段",
            "error": "Missing close column.",
        }

    close = pd.to_numeric(frame["close"], errors="coerce").dropna()
    if len(close) < 35:
        return {
            "ok": False,
            "trend_label": "历史数据不足，无法稳定计算技术指标",
            "error": "Not enough price history.",
        }

    ma_5 = close.rolling(5).mean()
    ma_20 = close.rolling(20).mean()
    ma_60 = close.rolling(60).mean()
    rsi_14 = _rsi(close, 14)

    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    macd = ema_12 - ema_26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - macd_signal

    latest_close = close.iloc[-1]
    latest_ma20 = ma_20.iloc[-1]
    latest_ma60 = ma_60.iloc[-1]
    latest_rsi = rsi_14.iloc[-1]
    latest_macd_hist = macd_hist.iloc[-1]

    if latest_close > latest_ma20 > latest_ma60:
        trend_label = "趋势偏强，价格位于中期均线之上"
    elif latest_close < latest_ma20 < latest_ma60:
        trend_label = "趋势偏弱，价格位于中期均线之下"
    else:
        trend_label = "趋势震荡，均线结构尚未形成单边信号"

    if latest_macd_hist > 0:
        macd_signal_label = "动能偏多"
    elif latest_macd_hist < 0:
        macd_signal_label = "动能偏空"
    else:
        macd_signal_label = "动能中性"

    return {
        "ok": True,
        "last_close": _round(latest_close),
        "ma_5": _round(ma_5.iloc[-1]),
        "ma_20": _round(latest_ma20),
        "ma_60": _round(latest_ma60),
        "rsi_14": _round(latest_rsi),
        "macd": _round(macd.iloc[-1]),
        "macd_signal": _round(macd_signal.iloc[-1]),
        "macd_hist": _round(latest_macd_hist),
        "macd_signal_label": macd_signal_label,
        "trend_label": trend_label,
    }
