import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import norm
from tabulate import tabulate

# ==========================================
# 1. PARAMETERS & CAPITAL RULES
# ==========================================
STARTING_CASH = 100000
DRY_POWDER_RESERVE = 30000
BENCHMARK = "SPY"
CORR_THRESHOLD = 0.65 
RISK_FREE_RATE = 0.045 # 2026 Average

def get_bs_greeks(S, K, T, r, sigma, q, opt_type='call'):
    if T <= 0: return {"delta": 0, "gamma": 0, "theta": 0, "vega": 0}
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    delta = norm.cdf(d1) if opt_type == 'call' else norm.cdf(d1) - 1
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    theta = (-(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * norm.cdf(d2)) / 365
    vega = (S * norm.pdf(d1) * np.sqrt(T)) / 100
    return {k: v * q for k, v in {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega}.items()}

# ==========================================
# 2. PORTFOLIO DATA (The Learning Sandbox)
# ==========================================
portfolio_config = [
    {"ticker": "AAPL", "qty": 100, "type": "Stock"},
    {"ticker": "TSLA", "qty": 5, "type": "Option", "strike": 250, "dte": 10, "opt_type": "call", "is_short": False}, # High Gamma (Near Expiry)
    {"ticker": "NVDA", "qty": -2, "type": "Option", "strike": 115, "dte": 40, "opt_type": "put", "is_short": True}, # Income (Theta)
    {"ticker": "GC=F", "qty": 1, "type": "Future", "delta_per": 100, "margin": 9500}, # Low Correlation
    {"ticker": "BTC-USD", "qty": 0.2, "type": "Crypto", "delta_per": 1.0}, # Low Correlation
    {"ticker": "MSFT", "qty": -1, "type": "Option", "strike": 440, "dte": 25, "opt_type": "call", "is_short": True},
    {"ticker": "TLT", "qty": 200, "type": "Stock"},
    {"ticker": "AMZN", "qty": 3, "type": "Option", "strike": 170, "dte": 5, "opt_type": "put", "is_short": False}  # Deep ITM / Near Expiry
]

# ==========================================
# 3. THE DECISION ENGINE (The "Brain")
# ==========================================
class DecisionEngine:
    @staticmethod
    def get_action(item, greeks, corr, vol, available_cap):
        """Processes logic to decide: Hedge, Roll, Adjust, or Close."""
        
        # 1. EXTREME RISK: Gamma Pin (DTE < 7)
        if item.get('dte', 100) < 7:
            return "CLOSE POSITION", "Gamma is exploding. Delta changes too fast to hedge effectively. Take profits/losses."

        # 2. STRATEGIC RISK: Correlation Breakdown (Idiosyncratic)
        if abs(corr) < CORR_THRESHOLD:
            if vol > 0.60:
                return "INDIVIDUAL HEDGE", f"Low market correlation ({corr:.2f}) but high vol. Buy direct {item['ticker']} puts."
            return "ADJUST / REDUCE", "Asset is 'doing its own thing' with low vol. Not worth index hedging; reduce size."

        # 3. GREEK RISK: Short Vol (Vega)
        if greeks['vega'] < -100 and vol > 0.40:
            return "ADJUST (SPREAD)", "High Vega risk in volatile environment. Convert naked short to a spread to cap risk."

        # 4. OPPORTUNITY: Theta Harvesting
        if greeks['theta'] > 20 and abs(greeks['delta']) < 30:
            return "HOLD / MONITOR", "Delta is neutral and Theta is high. Position is performing its income function."

        # 5. SYSTEMATIC RISK: High Correlation
        if abs(corr) >= CORR_THRESHOLD:
            return "SYSTEMATIC HEDGE", "Move to Portfolio Bucket. Hedge Delta via SPY aggregate."

        return "NO ACTION", "Position is within normal risk parameters."

# ==========================================
# 4. MAIN PIPELINE
# ==========================================
def main():
    tickers = list(set([i['ticker'] for i in portfolio_config] + [BENCHMARK]))
    data = yf.download(tickers, period="1y", auto_adjust=False, multi_level_index=False, progress=False)
    prices = data['Adj Close'].ffill().dropna()
    returns = prices.pct_change().dropna()
    last_p, vols = prices.iloc[-1], returns.tail(30).std() * np.sqrt(252)

    asset_table, port_greeks, total_margin = [], {"Delta": 0, "Gamma": 0, "Theta": 0, "Vega": 0}, 0

    print("\n--- STEP 1: INDIVIDUAL ASSET ANALYSIS & GREEK DERIVATION ---")
    for item in portfolio_config:
        t, S, sigma = item['ticker'], last_p[item['ticker']], vols[item['ticker']]
        corr = returns[t].tail(30).corr(returns[BENCHMARK])
        beta = returns[t].cov(returns[BENCHMARK]) / returns[BENCHMARK].var()
        
        # Calculate Greeks & Margin
        if item['type'] == "Option":
            g = get_bs_greeks(S, item['strike'], item['dte']/365, RISK_FREE_RATE, sigma, item['qty']*100, item['opt_type'])
            margin = (S * 10) if item.get('is_short') else (item['qty'] * 1500)
        else:
            g = {"delta": item['qty'] * item.get('delta_per', 1), "gamma": 0, "theta": 0, "vega": 0}
            margin = (S * item['qty']) * 0.25 if item['type'] == "Stock" else item.get('margin', S * 0.1)

        total_margin += margin
        bw_delta = g['delta'] * beta * (S / last_p[BENCHMARK])
        
        # Bucket and Portfolio Aggregation
        bucket = "Portfolio (SPY)" if abs(corr) > CORR_THRESHOLD else "Individual"
        if bucket == "Portfolio (SPY)":
            for k in port_greeks: port_greeks[k] += g[k.lower()] if k != "Delta" else bw_delta

        # Call Decision Engine
        action, reason = DecisionEngine.get_action(item, g, corr, sigma, (STARTING_CASH - total_margin))

        asset_table.append([t, item['type'], f"${margin:,.0f}", f"{corr:.2f}", f"{bw_delta:.1f}", f"{g['theta']:.1f}", bucket, action, reason])

    print(tabulate(asset_table, headers=["Ticker", "Type", "Margin", "Corr", "B-W Δ", "Theta", "Bucket", "Proposed Action", "Reasoning"], tablefmt="grid"))

    # --- PORTFOLIO SUMMARY ---
    available_cap = STARTING_CASH - total_margin - DRY_POWDER_RESERVE
    print(f"\n--- STEP 2: AGGREGATE PORTFOLIO GREEKS | Surplus Capital: ${available_cap:,.0f} ---")
    summary = [[k, f"{v:.2f}"] for k, v in port_greeks.items()]
    print(tabulate(summary, tablefmt="simple"))

    # --- HEDGING DECISIONS ---
    print("\n--- STEP 3: FINAL EXECUTION PLAN (SYSTEMATIC HEDGING) ---")
    exec_plan = []
    if abs(port_greeks['Delta']) > 40:
        side = "Sell" if port_greeks['Delta'] > 0 else "Buy"
        shares = abs(round(port_greeks['Delta']))
        cost = shares * last_p[BENCHMARK] * 0.15
        feasibility = "YES" if cost < available_cap else "NO (Use OTM Puts)"
        exec_plan.append(["Delta Hedge", f"{side} {shares} SPY Shares", f"${cost:,.0f}", feasibility, "Neutralize market direction."])
    
    if port_greeks['Vega'] < -150:
        exec_plan.append(["Vega Hedge", "Long VIX Calls or SPY Straddle", "Variable", "YES", "Volatility risk is too high; hedge for VIX spike."])

    if not exec_plan: exec_plan.append(["General", "Neutral", "0", "YES", "Portfolio is within risk tolerances."])
    print(tabulate(exec_plan, headers=["Risk", "Action", "Margin Cost", "Feasible", "Logic"], tablefmt="fancy_grid"))

if __name__ == "__main__":
    main()
