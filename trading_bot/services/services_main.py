import json
import yaml
import os
from pathlib import Path
from tabulate import tabulate
import portfolio_linear_regression as plr 
import market_regime as regime
import crash_indicators as crash

def calculate_strategy_bounds_dynamic(strategy_type, legs, strat_config):
    """Processes formulas from YAML to calculate risk/reward for 2026."""
    net_basis = sum(l['cost_basis'] for l in legs)
    strikes = [l['strike'] for l in legs]
    
    # Locate formulas in config
    s_cfg = strat_config.get(strategy_type, {})
    f_loss = s_cfg.get('formula_max_loss', 'abs(net_basis)')
    f_gain = s_cfg.get('formula_max_gain', '0')

    # Safe namespace for formula evaluation
    ns = {"max": max, "min": min, "strikes": strikes, "abs": abs, "net_basis": net_basis}
    try:
        max_loss = eval(f_loss, {"__builtins__": None}, ns)
        max_gain = eval(f_gain, {"__builtins__": None}, ns)
    except:
        max_loss, max_gain = abs(net_basis), 0
    return max_loss, max_gain

def load_and_format_trades(filename="sample_trade.json"):
    script_dir = Path(__file__).parent.absolute()
    with open(script_dir / filename, 'r') as f:
        raw_data = json.load(f)
    
    base_path = os.path.dirname(os.path.abspath(__file__))
    strat_config_path = os.path.join(base_path, "services_strategy_config.yaml")
    
    with open(strat_config_path, 'r') as f:
        strat_cfg = yaml.safe_load(f)['strategies']
        
        
    flattened = []
    for strat in raw_data:
        u_open = strat.get('underlying_open_price', 0)
        u_curr = strat.get('underlying_current_price', 0)
        price_change = u_curr - u_open
       # max_l, max_g = calculate_strategy_bounds(strat['strategy_type'], strat['legs'])
        max_l, max_g = calculate_strategy_bounds_dynamic(strat['strategy_type'], strat['legs'], strat_cfg)
        
        for leg in strat['legs']:
            leg.update({
                'trade_id': strat['trade_id'], 'ticker': strat['ticker'],
                'u_open': u_open, 'u_curr': u_curr,
                'price_change': price_change, 'strat_max_loss': max_l, 
                'strat_max_gain': max_g, 'strategy_type': strat['strategy_type']
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
    # Callout that Capital and Max Risk are calculated by local logic, not broker
    print("\n" + "#"*165)
    print(f"COMPREHENSIVE 2026 RISK REPORT | PORTFOLIO CAPITAL: ${total_cap:,.2f} [SOURCE: YAML]")
    print("NOTE: Max Loss/Gain and Risk % columns are [CALCULATED LOCALLY] based on strategy structure.")
    print("#"*165)

    headers = [
        "Trade/Leg ID", "Ticker", "U.Open", "U.Curr", "Actual P/L", 
        "Op/Cu Delt", "Op/Cu Thta", "Delt P/L", "Thta P/L", "Unexpl", 
        "Max Loss [CALC]", "Max Gain [CALC]", "Risk % [CALC]"
    ]
    table_data = []
    strategies = {}
    for l in trades: strategies.setdefault(l['trade_id'], []).append(l)

    for s_id, s_legs in strategies.items():
        # Strategy level Aggregates
        actual_pnl = sum(l['current_value'] - l['cost_basis'] for l in s_legs)
        delta_pnl = sum(l['open_greeks'].get('delta', 0) * l['price_change'] * 100 for l in s_legs)
        theta_pnl = sum(l['open_greeks'].get('theta', 0) * 100 for l in s_legs)
        unexpl = actual_pnl - (delta_pnl + theta_pnl)
        max_l, max_g = s_legs[0]['strat_max_loss'], s_legs[0]['strat_max_gain']

        # Add Strategy Summary Row
        table_data.append([
            f"STRAT: {s_id}", s_legs[0]['ticker'], f"{s_legs[0]['u_open']:.2f}", f"{s_legs[0]['u_curr']:.2f}",
            f"{actual_pnl:,.2f}", "---", "---", f"{delta_pnl:,.2f}", f"{theta_pnl:,.2f}", 
            f"{unexpl:,.2f}", f"{max_l:,.2f}", f"{max_g:,.2f}", f"{(max_l/total_cap)*100:.2f}%"
        ])

        # Add Detailed Leg Rows
        for l in s_legs:
            leg_pnl = l['current_value'] - l['cost_basis']
            ld_pnl = l['open_greeks'].get('delta', 0) * l['price_change'] * 100
            lt_pnl = l['open_greeks'].get('theta', 0) * 100
            table_data.append([
                f"  ↳ {l.get('leg_id','L')}", "", "", "", f"{leg_pnl:,.2f}",
                f"{l['open_greeks'].get('delta'):.2f}/{l['current_greeks'].get('delta'):.2f}",
                f"{l['open_greeks'].get('theta'):.2f}/{l['current_greeks'].get('theta'):.2f}",
                f"{ld_pnl:.2f}", f"{lt_pnl:.2f}", f"{leg_pnl-(ld_pnl+lt_pnl):.2f}", "", "", ""
            ])
        table_data.append(["-"*10] * len(headers))

    print("\n" + "="*165)
    print(f"COMPREHENSIVE 2026 RISK & ATTRIBUTION REPORT | PORTFOLIO CAPITAL: ${total_cap:,.2f}")
    print("="*165)
    print(tabulate(table_data, headers=headers, tablefmt="fancy_grid", stralign="right"))

def main():
    # --- STEP 1: PATH & CONFIG LOADING (PRESERVED) ---
    base_path = os.path.dirname(os.path.abspath(__file__))
    port_config_path = os.path.join(base_path, "services_portfolio_config.yaml")
    strat_config_path = os.path.join(base_path, "services_strategy_config.yaml")
    trades_path = os.path.join(base_path, "sample_trade.json")

    with open(port_config_path, 'r') as f:
        port_cfg = yaml.safe_load(f)['portfolio_config']
    with open(strat_config_path, 'r') as f:
        strat_cfg = yaml.safe_load(f)['strategies']
    with open(trades_path, 'r') as f:
        raw_trades = json.load(f)

    # --- STEP 2: MARKET CONTEXT ---
    mkt_status = regime.classify_market_regime()
    crash_status = crash.get_crash_prewarning_indicators()
    curr_regime = mkt_status['regime']

    # --- STEP 3: DATA PREP & DYNAMIC RISK ---
    total_cap = port_cfg['total_account_capital']
    target_config = port_cfg['targets']  # Extracted for optimizer

    processed_legs = []
    strat_risk_sums = {name: 0.0 for name in strat_cfg.keys()}

    for strat in raw_trades:
        s_type = strat['strategy_type']
        # Use dynamic formulas for risk
        max_l, max_g = calculate_strategy_bounds_dynamic(s_type, strat['legs'], strat_cfg)
        strat_risk_sums[s_type] = strat_risk_sums.get(s_type, 0.0) + max_l
        
        for leg in strat['legs']:
            leg.update({
                'trade_id': strat['trade_id'], 'ticker': strat['ticker'],
                'strategy_type': s_type, 'strat_max_loss': max_l, 'strat_max_gain': max_g,
                'price_change': strat.get('underlying_current_price', 0) - strat.get('underlying_open_price', 0)
            })
            processed_legs.append(leg)
    
    # 2. MARKET REGIME & RECOMMENDATIONS
    mkt_status = regime.classify_market_regime()
    curr_regime = mkt_status['regime']
    
    print("\n" + "="*80)
    print(f"REGIME-STRATEGY ALIGNMENT | CURRENT: {curr_regime}")
    print("="*80)
    
    # Identify suitable strategies and current risk used up
    recommendations = []
    # (Note: In a real run, 'trades' must be loaded here to sum current risk)
    # Placeholder: Current Risk % calculation for each type
    for s_name, s_val in strat_cfg.items():
        suitability = "✅ MATCH" if curr_regime in s_val['regimes'] else "❌ MISMATCH"
        limit = port_cfg['strategy_concentration_limits'].get(s_name, 0)
        # Current risk used (summed from existing positions)
        current_risk_used = 1.25 # Replace with actual sum(strat_max_loss)/total_cap
        
        recommendations.append([
            s_name, suitability, f"{limit}%", f"{current_risk_used:.2f}%", s_val['description']
        ])
        
    print(tabulate(recommendations, headers=["Strategy", "Regime Suitability", "Concentration Limit", "Current Risk Used", "Description"], tablefmt="fancy_grid"))

    # 4. LOAD & AGGREGATE TRADES
    trades = load_and_format_trades("sample_trade.json")
    port_greeks = aggregate_portfolio_greeks(trades)

    # 3. Print the Existing Portfolio Analysis
    print_comprehensive_portfolio(trades, total_cap) # Use this when fully ready


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