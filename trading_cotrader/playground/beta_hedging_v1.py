import yfinance as yf
import pandas as pd
import numpy as np
from tabulate import tabulate

# ==========================================
# 1. CONFIGURATION & ALLOCATION RULES
# ==========================================
STARTING_CASH = 100000
DRY_POWDER_PCT = 0.30       # 30k reserved for adjustments
MARGIN_LIMIT_PCT = 0.40     # 40k max for initial entry
BENCHMARK = "SPY"
CORR_THRESHOLD = 0.65       # Threshold for Portfolio vs Individual bucket

# Mock Portfolio: 10 diverse trades
# 'est_margin': % of value for stocks, or flat BPR for shorts/futures
portfolio_config = [
    {"ticker": "AAPL", "qty": 100, "type": "Stock", "delta": 1.0, "est_margin": 0.20},
    {"ticker": "TSLA", "qty": 5, "type": "Option", "delta": 0.65, "premium": 2500, "dte": 15, "is_short": False},
    {"ticker": "NVDA", "qty": -2, "type": "Option", "delta": -0.40, "est_margin": 8000, "dte": 45, "is_short": True},
    {"ticker": "GC=F", "qty": 1, "type": "Future", "delta": 100, "est_margin": 9500},
    {"ticker": "CL=F", "qty": 1, "type": "Future", "delta": 1000, "est_margin": 7000},
    {"ticker": "EURUSD=X", "qty": 20000, "type": "Forex", "delta": 1.0, "est_margin": 0.05},
    {"ticker": "MSFT", "qty": 50, "type": "Stock", "delta": 1.0, "est_margin": 0.20},
    {"ticker": "BTC-USD", "qty": 0.2, "type": "Crypto", "delta": 1.0, "est_margin": 1.0},
    {"ticker": "TLT", "qty": 100, "type": "Bond ETF", "delta": 1.0, "est_margin": 0.20},
    {"ticker": "GME", "qty": 200, "type": "Stock", "delta": 1.0, "est_margin": 1.0}, # High risk/Non-marginable
]

# ==========================================
# 2. LOGIC ENGINES
# ==========================================
class RiskEngine:
    @staticmethod
    def get_individual_logic(ticker, item, corr, vol):
        """Dynamic reasoning for assets that do NOT move with SPY."""
        if item.get('dte', 100) < 21:
            return "CLOSE/ROLL", "Gamma risk too high for delta hedging; delta is unstable."
        if vol > 0.55:
            return "LONG PUT", f"High vol ({vol:.1%}). Direct protection needed to offset idiosyncratic risk."
        if abs(corr) < 0.2:
            return "IGNORE", "Noise. Correlation too low; asset does not impact portfolio delta risk."
        return "COVERED CALL", "Low correlation. Harvest yield to offset price drift."

    @staticmethod
    def get_portfolio_hedge_options(net_delta, available_cash, spy_price):
        """Determines best index hedge based on remaining capital."""
        abs_d = abs(round(net_delta))
        side = "Short" if net_delta > 0 else "Buy"
        
        # Option A: SPY Shares (High Capital Req)
        share_margin = (abs_d * spy_price) * 0.20 # 20% margin
        # Option B: SPY Puts (Low Capital Req)
        put_cost = (max(1, round(abs_d/60))) * 800 # Est. $800 per contract
        
        proposals = []
        # Shares Evaluation
        if share_margin < available_cash:
            proposals.append(["SPY Shares", f"{side} {abs_d}", "HIGH", "PREFERRED", 
                              f"Direct Delta Offset. Fits in budget (${share_margin:,.0f} margin)."])
        else:
            proposals.append(["SPY Shares", "N/A", "LOW", "AVOID", "Insufficient margin available for share hedge."])
            
        # Options Evaluation
        if put_cost < available_cash:
            rec = "ALTERNATIVE" if share_margin < available_cash else "PREFERRED"
            proposals.append(["SPY Options", f"Buy {max(1, round(abs_d/70))} Puts", "MED", rec, 
                              f"Capital efficient (${put_cost:,.0f}). Use to save dry powder."])
        
        return proposals

# ==========================================
# 3. MAIN EXECUTION PIPELINE
# ==========================================
def main():
    print(f"\n{'='*100}\nDELTA-NEUTRAL HYBRID PORTFOLIO ARCHITECT (2026)\n{'='*100}")
    
    # Data Fetching
    tickers = [i['ticker'] for i in portfolio_config] + [BENCHMARK]
    data = yf.download(tickers, period="7mo", auto_adjust=False, multi_level_index=False, progress=False)
    prices = data['Adj Close'].ffill().dropna()
    returns = prices.pct_change().dropna()
    last_prices = prices.iloc[-1]
    vols = returns.std() * np.sqrt(252)

    # Calculation Loops
    asset_data = []
    total_margin_blocked = 0
    portfolio_delta_sum = 0.0

    for item in portfolio_config:
        t = item['ticker']
        p = last_prices[t]
        
        # 1. Greeks & Correlation
        corr = returns[t].tail(30).corr(returns[BENCHMARK])
        beta = returns[t].cov(returns[BENCHMARK]) / returns[BENCHMARK].var()
        
        # 2. Capital Math
        if item['type'] == "Stock": margin = (p * item['qty']) * item['est_margin']
        elif item['type'] == "Option": margin = item['premium'] if not item['is_short'] else item['est_margin']
        else: margin = item['est_margin']
        total_margin_blocked += margin
        
        # 3. Delta Normalization (Beta-Weighting)
        bw_delta = (item['qty'] * item['delta']) * beta * (p / last_prices[BENCHMARK])
        
        # 4. Bucketing Logic
        if abs(corr) > CORR_THRESHOLD:
            bucket = "Portfolio"
            portfolio_delta_sum += bw_delta
            strategy, reason = "Index Hedge", "Highly correlated to market moves."
        else:
            bucket = "Individual"
            strategy, reason = RiskEngine.get_individual_logic(t, item, corr, vols[t])
            
        asset_data.append([t, item['type'], f"${margin:,.0f}", f"{corr:.2f}", f"{vols[t]:.1%}", f"{bw_delta:.1f}", bucket, strategy, reason])

    # Display Step 1
    print("\n[STEP 1] DYNAMIC ASSET BUCKETING & CAPITAL BLOCK")
    headers = ["Ticker", "Type", "Margin", "Corr", "Vol", "B-W Δ", "Bucket", "Strategy", "Dynamic Logic"]
    print(tabulate(asset_data, headers=headers, tablefmt="grid"))

    # Display Step 2
    dry_powder = STARTING_CASH * DRY_POWDER_PCT if 'DRY_POWDER_RESERVE' in globals() else STARTING_CASH * 0.3
    available_for_hedge = STARTING_CASH - total_margin_blocked - dry_powder
    
    print("\n[STEP 2] CAPITAL UTILIZATION SUMMARY")
    cap_summary = [
        ["Total Starting Capital", f"${STARTING_CASH:,.0f}"],
        ["Current Margin Blocked", f"${total_margin_blocked:,.0f}", f"{(total_margin_blocked/STARTING_CASH):.1%} Utilization"],
        ["Dry Powder Reserved", f"${dry_powder:,.0f}", "Mandatory for rebalancing"],
        ["Available for Hedges", f"${available_for_hedge:,.0f}", "Surplus for Delta neutralization"]
    ]
    print(tabulate(cap_summary, tablefmt="simple"))

    # Display Step 3
    print(f"\n[STEP 3] PORTFOLIO-LEVEL HEDGE SELECTION (Net Δ: {round(portfolio_delta_sum, 2)})")
    if available_for_hedge < 0:
        print("!!! WARNING: Capital Over-utilization. You must close positions before hedging is possible. !!!")
    else:
        hedge_options = RiskEngine.get_portfolio_hedge_options(portfolio_delta_sum, available_for_hedge, last_prices[BENCHMARK])
        print(tabulate(hedge_options, headers=["Instrument", "Action", "Liquidity", "Rec", "Rationale"], tablefmt="grid"))

if __name__ == "__main__":
    main()
