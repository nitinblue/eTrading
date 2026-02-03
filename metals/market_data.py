# metals/market_data.py

from dataclasses import dataclass
import yfinance as yf
import pandas as pd

from metals.indicators import calculate_rsi, calculate_macd
from metals.dxy import get_dxy_trend


@dataclass
class MarketState:
    symbol: str
    price: float
    rsi: float
    macd: float
    macd_signal: float
    dxy_trend: str


def get_market_state(symbol: str) -> MarketState:
    data = yf.download(
        symbol,
        period="6mo",
        interval="1d",
        auto_adjust=True,
        progress=False
    )

    if data.empty:
        raise RuntimeError(f"No market data for {symbol}")

    close = data["Close"].squeeze()

    rsi = calculate_rsi(close)
    macd, macd_signal = calculate_macd(close)

    dxy_trend = get_dxy_trend()

    return MarketState(
        symbol=symbol,
        price=float(close.iloc[-1]),
        rsi=float(rsi),
        macd=float(macd),
        macd_signal=float(macd_signal),
        dxy_trend=dxy_trend,
    )
