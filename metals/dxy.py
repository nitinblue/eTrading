# dxy.py
import yfinance as yf

def get_dxy_trend(lookback=20):
    dxy = yf.download(
        "DX-Y.NYB",
        period="3mo",
        interval="1d",
        auto_adjust=True,
        progress=False
    )

    if dxy.empty:
        return "flat"

    # --- GUARANTEE scalar close series ---
    if isinstance(dxy["Close"], list):
        close = dxy["Close"]
    else:
        close = dxy["Close"].squeeze()  # <- critical

    if len(close) < lookback + 1:
        return "flat"

    last = float(close.iloc[-1])
    prev = float(close.iloc[-lookback])

    if last < prev:
        return "down"
    elif last > prev:
        return "up"
    else:
        return "flat"
