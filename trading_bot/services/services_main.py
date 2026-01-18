import json
import yaml
import os
from pathlib import Path
from tabulate import tabulate
import portfolio_linear_regression as plr 
import market_regime as regime
import crash_indicators as crash

# --- Data Loading and Helpers (Keep these functions in services_main.py) ---

# --- 1. Risk Arithmetic Helper ---
def calculate_strategy_bounds(strategy_type, legs):
    """Calculates Max Gain and Max Loss for 2026 Strategy Types."""
    net_basis = sum(l['cost_basis'] for l in legs)
    strikes = [l['strike'] for l in legs]
    
    # FIX: Use max() and min() instead of (int - list)
    if len(strikes) > 1:
        width = max(strikes) - min(strikes)
    else:
        width = 0
    
    if "Credit" in strategy_type or "Iron Condor" in strategy_type:
        max_gain = abs(net_basis)
        # Max loss for a spread is (Width * 100) - Credit Received
        max_loss = (width * 100) - max_gain
    elif "Debit" in strategy_type or "Butterfly" in strategy_type:
        max_loss = abs(net_basis)
        # Max gain for a spread is (Width * 100) - Debit Paid
        max_gain = (width * 100) - max_loss
    else:
        # Standard fallback for single legs
        max_loss, max_gain = abs(net_basis), 99999
        
    return max_loss, max_gain

def load_and_format_trades(filename="sample_trade.json"):
    script_dir = Path(__file__).parent.absolute()
    with open(script_dir / filename, 'r') as f:
        raw_data = json.load(f)
    flattened = []
    for strat in raw_data:
        u_open = strat.get('underlying_open_price', 0)
        u_curr = strat.get('underlying_current_price', 0)
        price_change = u_curr - u_open
        max_l, max_g = calculate_strategy_bounds(strat['strategy_type'], strat['legs'])
        for leg in strat['legs']:
            leg.update({
                'trade_id': strat['trade_id'], 'ticker': strat['ticker'],
                'u_open': u_open, 'u_curr': u_curr, 'price_change': price_change,
                'strat_max_loss': max_l, 'strat_max_gain': max_g, 'strategy_type': strat['strategy_type']
            })
            flattened.append(leg)
    return flattened

def aggregate_portfolio_greeks(trades):
    port_greeks = {'delta': 0, 'theta': 0, 'vega': 0}
    for leg in trades:
        curr = leg.get('current_greeks', {})
        port_greeks['delta'] += curr.get('delta', 0) * 100
        port_greeks['theta'] += curr.get('theta', 0) * 100
        port_greeks['vega'] += curr.get('vega', 0) * 100
    return port_greeks

def print_comprehensive_portfolio(trades, total_cap):
    # (Omitted here for brevity, use the full function provided in the previous step)
    pass 

# --- Main Execution Function ---
def main():
    # 1. SETUP PATHS
    base_path = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_path, "sample_portfolio_config.yaml")

    # 2. LOAD CONFIG
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    total_cap = config['portfolio_config']['total_account_capital']
    target_config = config['portfolio_config']['targets']  # Extracted for optimizer

    # 3. MARKET RADAR
    mkt_status = regime.classify_market_regime()
    crash_status = crash.get_crash_prewarning_indicators()

    # 4. LOAD & AGGREGATE TRADES
    trades = load_and_format_trades("sample_trade.json")
    port_greeks = aggregate_portfolio_greeks(trades)

    # 5. HEDGE SUGGESTIONS
    candidate_hedges = [
        {"name": "SPY_Put_Hedge", "delta": -0.5, "theta": -0.2, "vega": 0.4, "max_loss_per_unit": -400},
        {"name": "Income_Condor", "delta": 0.0, "theta": 0.4, "vega": -0.5, "max_loss_per_unit": -1200}
    ]
    
    # Correct call ensuring target_config is passed
    suggestions = plr.calculate_enhanced_hedge(
        portfolio_greeks=port_greeks,
        target_config=target_config,
        candidate_trades=candidate_hedges,
        total_capital=total_cap,
        current_regime=mkt_status
    )
    
    print("\n" + "?" * 40 + " HEDGE SUGGESTIONS " + "?" * 40)
    print(tabulate(suggestions, headers="keys", tablefmt="fancy_grid"))

if __name__ == "__main__":
    main()