"""
Regime Detection with Technical Analysis + Markov Chain
Fully self-contained, debug-friendly, educational version

Dependencies:
pip install yfinance numpy pandas ta-lib tabulate
"""

import numpy as np
import pandas as pd
import yfinance as yf
import talib
from tabulate import tabulate

# =========================================================
# 1. MARKOV TRANSITION MATRIX
# =========================================================

STATES = ["U", "F", "D"]

MARKOV_P = {
    "U": np.array([0.60, 0.25, 0.15]),
    "F": np.array([0.30, 0.40, 0.30]),
    "D": np.array([0.15, 0.25, 0.60]),
}

# =========================================================
# 2. DATA FETCHING
# =========================================================

def fetch_price_data(symbol, period="1y", interval="1d"):
    df = yf.download(symbol, period=period, interval=interval, auto_adjust=True)
    df.dropna(inplace=True)
    return df

# =========================================================
# 3. SAFE PRICE EXTRACTION (CRITICAL FIX)
# =========================================================

def extract_price_arrays(df):
    close = df["Close"].astype(float).to_numpy()
    high = df["High"].astype(float).to_numpy()
    low = df["Low"].astype(float).to_numpy()

    # Remove NaNs
    mask = ~np.isnan(close) & ~np.isnan(high) & ~np.isnan(low)
    close, high, low = close[mask], high[mask], low[mask]

    if close.ndim != 1:
        raise ValueError("Close array is not 1-D")

    if len(close) < 60:
        raise ValueError("Not enough data for indicators")

    return close, high, low

# =========================================================
# 4. TECHNICAL INDICATORS
# =========================================================

def compute_indicators(close, high, low):
    return {
        "ema_fast": talib.EMA(close, timeperiod=20),
        "ema_slow": talib.EMA(close, timeperiod=50),
        "rsi": talib.RSI(close, timeperiod=14),
        "macd_hist": talib.MACD(close)[2],
        "adx": talib.ADX(high, low, close, timeperiod=14),
        "atr": talib.ATR(high, low, close, timeperiod=14),
    }

# =========================================================
# 5. INDICATOR → EVIDENCE
# =========================================================

def indicator_evidence(ind):
    ema_diff = ind["ema_fast"][-1] - ind["ema_slow"][-1]

    return {
        "trend": np.tanh((ema_diff / ind["ema_slow"][-1]) * 20),
        "momentum": (ind["rsi"][-1] - 50) / 50,
        "accel": np.tanh(ind["macd_hist"][-1] * 5),
        "trend_strength": min(ind["adx"][-1] / 40, 1.0),
    }

# =========================================================
# 6. EVIDENCE → RAW PROBABILITIES
# =========================================================

def evidence_to_probabilities(e):
    up = max(e["trend"], 0) + max(e["momentum"], 0) + max(e["accel"], 0)
    down = max(-e["trend"], 0) + max(-e["momentum"], 0) + max(-e["accel"], 0)
    flat = (1 - e["trend_strength"]) * 2

    scores = np.array([up, flat, down])
    probs = scores / scores.sum()

    return {"U": probs[0], "F": probs[1], "D": probs[2]}

# =========================================================
# 7. MARKOV UPDATE
# =========================================================

def markov_update(raw_probs, prev_state):
    prior = MARKOV_P[prev_state]
    likelihood = np.array([
        raw_probs["U"],
        raw_probs["F"],
        raw_probs["D"],
    ])

    posterior = prior * likelihood
    posterior /= posterior.sum()

    return {"U": posterior[0], "F": posterior[1], "D": posterior[2]}

# =========================================================
# 8. REGIME + CONFIDENCE
# =========================================================

def regime_and_confidence(probs):
    regime = max(probs, key=probs.get)
    confidence = probs[regime]
    return regime, confidence

# =========================================================
# 9. TABLE DISPLAY HELPERS
# =========================================================

def show_price_table(close, high, low, n=8):
    table = [
        [i, round(close[-n+i], 2), round(high[-n+i], 2), round(low[-n+i], 2)]
        for i in range(n)
    ]
    print("\nLAST PRICE SNAPSHOT")
    print(tabulate(table, headers=["Idx", "Close", "High", "Low"], tablefmt="github"))

def show_indicator_table(ind):
    table = [
        ["EMA Fast", ind["ema_fast"][-1]],
        ["EMA Slow", ind["ema_slow"][-1]],
        ["RSI", ind["rsi"][-1]],
        ["MACD Hist", ind["macd_hist"][-1]],
        ["ADX", ind["adx"][-1]],
        ["ATR", ind["atr"][-1]],
    ]
    print("\nINDICATORS")
    print(tabulate(table, headers=["Indicator", "Value"], tablefmt="github"))

def show_dict_table(title, d):
    table = [[k, round(v, 3)] for k, v in d.items()]
    print(f"\n{title}")
    print(tabulate(table, headers=["Key", "Value"], tablefmt="github"))

# =========================================================
# 10. FULL REGIME PIPELINE
# =========================================================

def detect_market_regime(symbol, prev_state="F"):
    print(f"\n================ {symbol} =================")

    df = fetch_price_data(symbol)
    close, high, low = extract_price_arrays(df)

    show_price_table(close, high, low)

    indicators = compute_indicators(close, high, low)
    show_indicator_table(indicators)

    evidence = indicator_evidence(indicators)
    show_dict_table("EVIDENCE SCORES", evidence)

    raw_probs = evidence_to_probabilities(evidence)
    show_dict_table("RAW PROBABILITIES", raw_probs)

    final_probs = markov_update(raw_probs, prev_state)
    show_dict_table("MARKOV-ADJUSTED PROBABILITIES", final_probs)

    regime, confidence = regime_and_confidence(final_probs)

    print("\nFINAL REGIME")
    print(tabulate(
        [[regime, round(confidence, 3)]],
        headers=["Regime", "Confidence"],
        tablefmt="github"
    ))

    return regime

# =========================================================
# 11. MAIN
# =========================================================

def main():
    symbols = {
        "Equity": "AAPL",
        "Metal": "GLD",
        "Crude": "CL=F",
    }

    prev_state = "F"

    for _, symbol in symbols.items():
        prev_state = detect_market_regime(symbol, prev_state)

if __name__ == "__main__":
    main()
