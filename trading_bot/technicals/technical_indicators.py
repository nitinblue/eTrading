import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy.stats import norm

def compute_vwap(intraday):
    today = intraday.iloc[-26:]
    pv = (today["Close"] * today["Volume"]).cumsum()
    vol = today["Volume"].cumsum()
    return pv / vol


def opening_range_15m(intraday):
    today = intraday.iloc[-26:]  # approx today (6.5 hrs)
    first_bar = today.iloc[0]
    return first_bar["High"] - first_bar["Low"]

def expected_move(spot, vix):
    """
    VIX is annualized %
    """
    iv = vix / 100
    return spot * iv * np.sqrt(1 / 252)

def compute_gap_pct(daily):
    today = daily.iloc[-1]
    prev = daily.iloc[-2]
    return (today["Open"] - prev["Close"]) / prev["Close"] * 100

def fetch_vix():
    vix = yf.download("^VIX", period="1mo", interval="1d", progress=False)
    return vix

def fetch_market_data(symbol="^GSPC", lookback_days=5):
    """
    Fetch 15m intraday and daily data for any index or ETF
    """
    intraday = yf.download(
        symbol,
        period=f"{lookback_days}d",
        interval="15m",
        auto_adjust=True,
        progress=False
    )

    daily = yf.download(
        symbol,
        period="1mo",
        interval="1d",
        auto_adjust=True,
        progress=False
    )

    return intraday, daily

def classify_regime(symbol="^GSPC"):
    intraday, daily = fetch_market_data(symbol)

    spot_now = scalar(intraday["Close"].iloc[-1])
    gap_pct = compute_gap_pct(daily)

    vix_today = fetch_vix()
    exp_move = expected_move(spot_now, vix_today)

    or_15m = opening_range_15m(intraday)
    vwap_now = compute_vwap(intraday)

    if abs(gap_pct) < 0.4 and or_15m < (0.6 * exp_move) and vix_today > 15:
        regime = "NEUTRAL_PIN"
    elif spot_now > vwap_now and gap_pct > 0.3:
        regime = "BULLISH_DIRECTIONAL"
    elif spot_now < vwap_now and gap_pct < -0.3:
        regime = "BEARISH_DIRECTIONAL"
    else:
        regime = "NO_TRADE"

    return {
        "symbol": symbol,
        "spot": round(spot_now, 2),
        "gap_pct": round(gap_pct, 2),
        "vix": round(vix_today, 2),
        "expected_move": round(exp_move, 2),
        "opening_range_15m": round(or_15m, 2),
        "vwap": round(vwap_now, 2),
        "regime": regime
    }
