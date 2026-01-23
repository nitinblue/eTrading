import json
import os
import yaml
from tabulate import tabulate
from pathlib import Path
import portfolio_linear_regression as plr # Ensure this file exists in the same folder

# --- 1. Load Configuration ---
def load_config(filename="sample_portfolio_config.yml"):
    script_dir = Path(__file__).parent.absolute()
    file_path = script_dir / filename
    if not file_path.exists():
        raise FileNotFoundError(f"Config file not found at {file_path}")
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)

# --- 2. Load and Format Trades (MISSING FUNCTION ADDED) ---
def load_and_format_trades(filename="sample_trade.json"):
    script_dir = Path(__file__).parent.absolute()
    file_path = script_dir / filename
    if not file_path.exists():
        raise FileNotFoundError(f"Trades file not found at {file_path}")

    with open(file_path, 'r') as f:
        raw_data = json.load(f)

    # Flatten the Strategy -> Legs structure for the table
    flattened_legs = []
    for strat in raw_data:
        price_change = strat.get('underlying_current_price', 0) - strat.get('underlying_open_price', 0)
        for leg in strat['legs']:
            leg['trade_id'] = strat.get('trade_id', 'Unknown')
            leg['ticker'] = strat.get('ticker', '???')
            leg['strategy_type'] = strat.get('strategy_type', 'Spread')
            leg['underlying_price_change'] = price_change
            flattened_legs.append(leg)
    return flattened_legs

# --- 3. Analysis Table Printer ---
def analyze_strategies(trades, total_capital):
    # (Existing table printing logic from prior steps goes here)
    # For now, a simple placeholder to confirm it works:
    print(f"\nAnalyzing {len(trades)} legs with ${total_capital:,.2f} capital...")

# --- 4. Main Orchestrator ---
def main():
    try:
        # Load Config
        config = load_config("sample_portfolio_config.yaml")
        total_cap = config['portfolio_config']['total_account_capital']
        targets = config['portfolio_config']['targets']
        
        # Load Trades
        trades = load_and_format_trades("sample_trade.json")
        
        # Aggregate Greeks
        port_greeks = {'delta': 0.0, 'theta': 0.0, 'vega': 0.0}
        for leg in trades:
            port_greeks['delta'] += leg['current_greeks'].get('delta', 0) * 100
            port_greeks['theta'] += leg['current_greeks'].get('theta', 0) * 100
            port_greeks['vega'] += leg['current_greeks'].get('vega', 0) * 100

        # Run Regression
        candidate_hedges = [
            {"name": "SPY_Put_Hedge", "delta": -0.40, "theta": -0.10, "vega": 0.40},
            {"name": "Neutral_Iron_Condor", "delta": 0.01, "theta": 0.30, "vega": -0.35}
        ]
        
        suggestions = plr.calculate_target_hedge(port_greeks, targets, candidate_hedges)
        
        print("\n--- Portfolio Optimizer Suggestions ---")
        print(tabulate(suggestions, headers="keys", tablefmt="fancy_grid"))
        
        analyze_strategies(trades, total_cap)

    except Exception as e:
        print(f"Detailed Error: {e}")

if __name__ == "__main__":
    main()
