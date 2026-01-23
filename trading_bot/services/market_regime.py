import yfinance as yf
from tabulate import tabulate

def classify_market_regime():
    """Classifies environment based on 90-day trend and current VIX."""
    spy = yf.Ticker("SPY").history(period="90d")
    vix = yf.Ticker("^VIX").history(period="1d")['Close'].iloc[-1]
    
    # 30-day performance
    returns_30d = (spy['Close'].iloc[-1] / spy['Close'].iloc[-30]) - 1
    
    if vix > 25:
        regime, strat = "High Volatility / Bearish", "Long Puts / Bear Debit Spreads"
    elif returns_30d > 0.05 and vix < 15:
        regime, strat = "Low Vol / Bullish", "Short Puts / Bull Credit Spreads"
    else:
        regime, strat = "Neutral / Choppy", "Iron Condors / Butterflies"
        
    regime_data = [["Current Regime", regime], ["Target Strategy", strat], ["Current VIX", f"{vix:.2f}"]]
    
    print("\n[MARKET REGIME SUMMARY]")
    print(tabulate(regime_data, tablefmt="fancy_grid"))
    
    return {"regime": regime, "strategy": strat}
