from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go


def build_price_chart(market_data: dict[str, Any], technicals: dict[str, Any]):
    prices = market_data.get("prices", [])
    if not prices:
        return None

    frame = pd.DataFrame(prices)
    if frame.empty or "date" not in frame or "close" not in frame:
        return None

    frame["date"] = pd.to_datetime(frame["date"])
    frame["ma20"] = pd.to_numeric(frame["close"], errors="coerce").rolling(20).mean()
    frame["ma60"] = pd.to_numeric(frame["close"], errors="coerce").rolling(60).mean()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=frame["date"],
            y=frame["close"],
            mode="lines",
            name="Close",
            line={"width": 2},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=frame["date"],
            y=frame["ma20"],
            mode="lines",
            name="MA20",
            line={"width": 1},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=frame["date"],
            y=frame["ma60"],
            mode="lines",
            name="MA60",
            line={"width": 1},
        )
    )
    fig.update_layout(
        title=f"{market_data.get('ticker', '')} Price Trend",
        height=420,
        margin={"l": 24, "r": 24, "t": 48, "b": 24},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    return fig
