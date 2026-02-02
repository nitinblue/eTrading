"""
Regime Detection with:
- Rolling Markov learning
- Multi-timeframe fusion
- Volatility regime

TA-Lib SAFE version (dimension-proof)
"""

import numpy as np
import pandas as pd
import yfinance as yf
import talib
from tabulate import tabulate

LOOKBACK_DAYS = 252

DIR_STATES = ["U", "F", "D"]
VOL_STATES = ["LOW", "NORMAL", "HIGH"]

DIR_IDX = {s: i for i, s in enumerate(DIR_STATES)}
VOL_IDX = {s: i for i, s in enumerate(VOL_STATES)}

# ======================================================
# DATA
# ======================================================

def fetch(symbol, period="2y", interval="1d"):
    df = yf.download(symbol, period=period, interval=interval, auto_adjust=True)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    return df

# ======================================================
# INDICATORS (FIXED)
# ======================================================

def indicators(df):
    close = df["Close"].to_numpy(dtype=np.float64).reshape(-1)
    high = df["High"].to_numpy(dtype=np.float64).reshape(-1)
    low  = df["Low"].to_numpy(dtype=np.float64).reshape(-1)

    return {
        "ema_fast": talib.EMA(close, timeperiod=20),
        "ema_slow": talib.EMA(close, timeperiod=50),
        "rsi": talib.RSI(close, timeperiod=14),
        "macd": talib.MACD(close)[2],
        "adx": talib.ADX(high, low, close, timeperiod=14),
        "atr": talib.ATR(high, low, close, timeperiod=14),
        "close": close
    }

# ======================================================
# REGIME LOGIC
# ======================================================

def directional_regime(ind, i):
    ema_diff = ind["ema_fast"][i] - ind["ema_slow"][i]
    trend = np.tanh((ema_diff / ind["ema_slow"][i]) * 20)
    momentum = (ind["rsi"][i] - 50) / 50
    accel = np.tanh(ind["macd"][i] * 5)
    strength = min(ind["adx"][i] / 40, 1)

    up = max(trend, 0) + max(momentum, 0) + max(accel, 0)
    down = max(-trend, 0) + max(-momentum, 0) + max(-accel, 0)
    flat = (1 - strength) * 2

    scores = {"U": up, "F": flat, "D": down}
    return max(scores, key=scores.get)

def volatility_regime(ind, i):
    atr_pct = ind["atr"][i] / ind["close"][i]
    if atr_pct < 0.012:
        return "LOW"
    elif atr_pct < 0.025:
        return "NORMAL"
    else:
        return "HIGH"

# ======================================================
# BUILD REGIME SERIES
# ======================================================

def build_regimes(df):
    ind = indicators(df)

    dir_r, vol_r = [], []
    start = 60  # indicator warmup

    for i in range(start, len(df)):
        if np.isnan(ind["ema_fast"][i]) or np.isnan(ind["atr"][i]):
            continue
        dir_r.append(directional_regime(ind, i))
        vol_r.append(volatility_regime(ind, i))

    return dir_r, vol_r

# ======================================================
# MARKOV
# ======================================================

def learn_markov(series, states, idx):
    mat = np.zeros((len(states), len(states)))
    for a, b in zip(series[:-1], series[1:]):
        mat[idx[a], idx[b]] += 1
    return mat / mat.sum(axis=1, keepdims=True)

# ======================================================
# TIMEFRAME
# ======================================================

def weekly(df):
    return df.resample("W-FRI").last().dropna()

# ======================================================
# MAIN
# ======================================================

def run(symbol):
    df_d = fetch(symbol)
    df_w = weekly(df_d)

    dir_d, vol_d = build_regimes(df_d)
    dir_w, _ = build_regimes(df_w)

    P_dir_d = learn_markov(dir_d[-LOOKBACK_DAYS:], DIR_STATES, DIR_IDX)
    P_dir_w = learn_markov(dir_w[-52:], DIR_STATES, DIR_IDX)
    P_vol_d = learn_markov(vol_d[-LOOKBACK_DAYS:], VOL_STATES, VOL_IDX)

    dir_prob = 0.7 * P_dir_d[DIR_IDX[dir_d[-1]]] + \
               0.3 * P_dir_w[DIR_IDX[dir_w[-1]]]

    vol_prob = P_vol_d[VOL_IDX[vol_d[-1]]]

    dir_probs = dict(zip(DIR_STATES, dir_prob))
    vol_probs = dict(zip(VOL_STATES, vol_prob))

    print(f"\n===== {symbol} =====\n")
    print("Directional Regime")
    print(tabulate(dir_probs.items(), headers=["State", "Prob"], tablefmt="github"))

    print("\nVolatility Regime")
    print(tabulate(vol_probs.items(), headers=["State", "Prob"], tablefmt="github"))

# ======================================================
# ENTRY
# ======================================================

if __name__ == "__main__":
    run("AAPL")
