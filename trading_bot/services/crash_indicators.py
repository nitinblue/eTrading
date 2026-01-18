import yfinance as yf
from tabulate import tabulate
import pandas as pd
import os

def get_crash_prewarning_indicators():
    """Senses market stress for 2026 via plumbing metrics with .iloc indexing."""
    # 1. LIVE: VIX Spike (Fear Gauge)
    vix_ticker = yf.Ticker("^VIX")
    vix_data = vix_ticker.history(period="5d")['Close']
    vix_spike = (vix_data.iloc[-1] / vix_data.iloc[0] - 1) * 100 if len(vix_data) > 1 else 0

    # 2. LIVE: Credit Spreads Proxy (HYG vs IEI)
    hyg = yf.Ticker("HYG").history(period="5d")['Close']
    iei = yf.Ticker("IEI").history(period="5d")['Close']
    spread_trend = (hyg.pct_change().iloc[-1] - iei.pct_change().iloc[-1])

    # 3. LIVE: Valuation (SPY P/E Ratio)
    spy_info = yf.Ticker("SPY").info
    # Handle missing 2026 API data
    fwd_pe = spy_info.get('forwardPE') or spy_info.get('trailingPE') or 0.0
    pe_display = f"{fwd_pe:.2f}" if fwd_pe > 0 else "[DATA UNAVAILABLE]"
    pe_status = "OVERVALUED" if fwd_pe > 22 else "Fair" if fwd_pe > 0 else "UNKNOWN"

    radar_data = [
        ["VIX 5D Spike", f"{vix_spike:.2f}%", "LIVE", "ALERT" if vix_spike > 20 else "Normal"],
        ["Credit Spread (HYG/IEI)", f"{spread_trend:.4f}", "LIVE", "WIDENING" if spread_trend < -0.005 else "Stable"],
        ["SPY P/E Ratio", pe_display, "LIVE", pe_status],
        ["Insider Selling Ratio", "1.45", "[STATIC]", "Monitor for > 2.0"],
        ["Margin Debt Level", "820B", "[STATIC]", "Updated Monthly Only"]
    ]
    
    print("\n" + "!" * 30 + " CRASH RADAR INDICATORS " + "!" * 30)
    print(tabulate(radar_data, headers=["Metric", "Value", "Source", "Status"], tablefmt="fancy_grid"))
    return {"vix_spike": vix_spike, "fwd_pe": fwd_pe}
