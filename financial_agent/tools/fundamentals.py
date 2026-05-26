from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd


def _round(value: Any, digits: int = 2):
    if value is None or pd.isna(value):
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _percent(value: Any) -> float | None:
    number = _round(value, 4)
    if number is None:
        return None
    return _round(number * 100)


def _timestamp_to_date(value: Any) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return None


def _date_context(date_text: str | None) -> str | None:
    if not date_text:
        return None
    try:
        date_value = datetime.strptime(date_text, "%Y-%m-%d").date()
    except ValueError:
        return None
    today = datetime.now(timezone.utc).date()
    if date_value < today:
        return "past"
    if date_value == today:
        return "today"
    return "future"


def _compact_number(value: Any) -> str | None:
    number = _round(value, 2)
    if number is None:
        return None
    abs_number = abs(number)
    if abs_number >= 1_000_000_000_000:
        return f"{number / 1_000_000_000_000:.2f}T"
    if abs_number >= 1_000_000_000:
        return f"{number / 1_000_000_000:.2f}B"
    if abs_number >= 1_000_000:
        return f"{number / 1_000_000:.2f}M"
    return f"{number:.2f}"


def _safe_info(info: dict[str, Any], *keys: str):
    for key in keys:
        value = info.get(key)
        if value is not None and value != "":
            return value
    return None


def _safe_fast_info(fast_info: Any, key: str):
    if not fast_info:
        return None
    try:
        return fast_info.get(key)
    except AttributeError:
        pass
    except Exception:
        return None
    try:
        return fast_info[key]
    except Exception:
        return None


def _build_highlights(data: dict[str, Any], last_close: float | None) -> list[str]:
    highlights: list[str] = []

    revenue_growth = data.get("revenue_growth_percent")
    profit_margin = data.get("profit_margins_percent")
    gross_margin = data.get("gross_margins_percent")
    forward_pe = data.get("forward_pe")
    target_mean = data.get("target_mean_price")
    recommendation = (data.get("recommendation_key") or "").lower()

    if isinstance(revenue_growth, (int, float)) and revenue_growth >= 15:
        highlights.append(f"营收增长为 {revenue_growth}%，增长动能较强。")
    if isinstance(profit_margin, (int, float)) and profit_margin >= 15:
        highlights.append(f"净利率为 {profit_margin}%，盈利质量较好。")
    if isinstance(gross_margin, (int, float)) and gross_margin >= 50:
        highlights.append(f"毛利率为 {gross_margin}%，业务具备较强毛利弹性。")
    if isinstance(forward_pe, (int, float)) and 0 < forward_pe <= 25:
        highlights.append(f"Forward PE 为 {forward_pe}，估值相对克制。")
    if isinstance(target_mean, (int, float)) and isinstance(last_close, (int, float)) and target_mean > last_close * 1.1:
        upside = _round((target_mean / last_close - 1) * 100)
        highlights.append(f"分析师平均目标价较现价有约 {upside}% 上行空间。")
    if recommendation in {"buy", "strong_buy"}:
        highlights.append(f"分析师一致预期偏正面，当前 recommendation 为 {recommendation}。")

    return highlights[:5]


def _build_risks(data: dict[str, Any], last_close: float | None) -> list[str]:
    risks: list[str] = []

    trailing_pe = data.get("trailing_pe")
    forward_pe = data.get("forward_pe")
    price_to_sales = data.get("price_to_sales")
    revenue_growth = data.get("revenue_growth_percent")
    profit_margin = data.get("profit_margins_percent")
    target_mean = data.get("target_mean_price")
    beta = data.get("beta")
    recommendation = (data.get("recommendation_key") or "").lower()

    if isinstance(trailing_pe, (int, float)) and trailing_pe >= 60:
        risks.append(f"Trailing PE 为 {trailing_pe}，估值对盈利预期较敏感。")
    if isinstance(forward_pe, (int, float)) and forward_pe >= 45:
        risks.append(f"Forward PE 为 {forward_pe}，未来增长若放缓可能引发估值压缩。")
    if isinstance(price_to_sales, (int, float)) and price_to_sales >= 15:
        risks.append(f"PS 为 {price_to_sales}，收入端预期已经较高。")
    if isinstance(revenue_growth, (int, float)) and revenue_growth < 0:
        risks.append(f"营收增长为 {revenue_growth}%，基本面增长承压。")
    if isinstance(profit_margin, (int, float)) and profit_margin < 0:
        risks.append(f"净利率为 {profit_margin}%，盈利仍处于亏损或低质量状态。")
    if isinstance(target_mean, (int, float)) and isinstance(last_close, (int, float)) and target_mean < last_close:
        downside = _round((1 - target_mean / last_close) * 100)
        risks.append(f"分析师平均目标价低于现价约 {downside}%，可能限制估值空间。")
    if isinstance(beta, (int, float)) and beta >= 1.5:
        risks.append(f"Beta 为 {beta}，股价对市场风险偏好变化较敏感。")
    if recommendation in {"sell", "strong_sell", "underperform"}:
        risks.append(f"分析师 recommendation 为 {recommendation}，一致预期偏谨慎。")

    return risks[:5]


def get_fundamentals(ticker: str, last_close: float | None = None) -> dict[str, Any]:
    if not ticker:
        return {"ok": False, "ticker": ticker, "error": "Missing ticker."}

    try:
        import yfinance as yf
    except ImportError as exc:
        return {"ok": False, "ticker": ticker, "error": f"yfinance is not installed: {exc}"}

    try:
        stock = yf.Ticker(ticker)
    except Exception as exc:
        return {"ok": False, "ticker": ticker, "error": str(exc)}

    errors: list[str] = []
    info: dict[str, Any] = {}
    fast_info: Any = {}
    try:
        info = stock.info or {}
    except Exception as exc:
        errors.append(f"info: {exc}")
    try:
        fast_info = getattr(stock, "fast_info", {}) or {}
    except Exception as exc:
        errors.append(f"fast_info: {exc}")

    if not info and not fast_info:
        return {
            "ok": False,
            "ticker": ticker,
            "error": "; ".join(errors) or "No fundamental data returned.",
        }

    market_cap = _safe_info(info, "marketCap") or _safe_fast_info(fast_info, "market_cap")
    earnings_date = _timestamp_to_date(_safe_info(info, "earningsTimestamp"))
    data = {
        "ok": True,
        "ticker": ticker,
        "partial": bool(errors),
        "warnings": errors,
        "company_name": _safe_info(info, "longName", "shortName"),
        "sector": _safe_info(info, "sector"),
        "industry": _safe_info(info, "industry"),
        "currency": _safe_info(info, "currency") or _safe_fast_info(fast_info, "currency"),
        "market_cap": _round(market_cap),
        "market_cap_display": _compact_number(market_cap),
        "enterprise_value": _round(_safe_info(info, "enterpriseValue")),
        "enterprise_value_display": _compact_number(_safe_info(info, "enterpriseValue")),
        "trailing_pe": _round(_safe_info(info, "trailingPE")),
        "forward_pe": _round(_safe_info(info, "forwardPE")),
        "price_to_sales": _round(_safe_info(info, "priceToSalesTrailing12Months")),
        "price_to_book": _round(_safe_info(info, "priceToBook")),
        "beta": _round(_safe_info(info, "beta")),
        "eps_trailing": _round(_safe_info(info, "trailingEps")),
        "eps_forward": _round(_safe_info(info, "forwardEps")),
        "revenue_growth_percent": _percent(_safe_info(info, "revenueGrowth")),
        "earnings_growth_percent": _percent(_safe_info(info, "earningsGrowth")),
        "profit_margins_percent": _percent(_safe_info(info, "profitMargins")),
        "gross_margins_percent": _percent(_safe_info(info, "grossMargins")),
        "operating_margins_percent": _percent(_safe_info(info, "operatingMargins")),
        "dividend_yield_percent": _percent(_safe_info(info, "dividendYield")),
        "payout_ratio_percent": _percent(_safe_info(info, "payoutRatio")),
        "target_mean_price": _round(_safe_info(info, "targetMeanPrice")),
        "target_high_price": _round(_safe_info(info, "targetHighPrice")),
        "target_low_price": _round(_safe_info(info, "targetLowPrice")),
        "number_of_analyst_opinions": _safe_info(info, "numberOfAnalystOpinions"),
        "recommendation_key": _safe_info(info, "recommendationKey"),
        "earnings_date": earnings_date,
        "earnings_date_context": _date_context(earnings_date),
    }
    data["highlights"] = _build_highlights(data, last_close)
    data["risks"] = _build_risks(data, last_close)
    return data
