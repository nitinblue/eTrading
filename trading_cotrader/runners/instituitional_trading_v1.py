
import pandas as pd
import numpy as np
from tabulate import tabulate
from scipy.stats import norm

def black_scholes_greeks(S, K, T, r, sigma, option_type='call'):
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == 'call':
        delta = norm.cdf(d1)
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        theta = - (S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * norm.cdf(d2)
        vega = S * np.sqrt(T) * norm.pdf(d1)
    elif option_type == 'put':
        delta = -norm.cdf(-d1)
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        theta = - (S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) + r * K * np.exp(-r * T) * norm.cdf(-d2)
        vega = S * np.sqrt(T) * norm.pdf(d1)
    else:
        raise ValueError("Invalid option type")
    
    return delta, gamma, theta, vega

def define_instruments_and_portfolio():
    # Instrument 1: MSFT Call Option (expiring in 1 month = 30/365 years)
    msft_data = {
        'Instrument': 'MSFT_Call',
        'Type': 'Option',
        'Underlying': 'MSFT',
        'Strike': 400,
        'Expiry': 30/365,
        'Option_Type': 'call',
        'Current_Price': 410,  # Spot price of MSFT
        'Volatility': 0.25,
        'Risk_Free_Rate': 0.05
    }

    # Instrument 2: Gold/Silver Spread (long Gold, short Silver)
    gold_silver_data = {
        'Instrument': 'Gold_Silver_Spread',
        'Type': 'Spread',
        'Long_Leg': 'Gold_Future',
        'Short_Leg': 'Silver_Future',
        'Ratio': 1,  # Simplified
        'Gold_Price': 2000,
        'Silver_Price': 25,
        'Gold_Delta': 1,
        'Silver_Delta': 1
    }

    # Instrument 3: Vertical Spread on Crude (Bull Call Spread)
    crude_vertical_data = {
        'Instrument': 'Crude_Vertical_Spread',
        'Type': 'Option_Spread',
        'Underlying': 'Crude',
        'Long_Strike': 70,
        'Short_Strike': 75,
        'Expiry': 30/365,
        'Option_Type': 'call',
        'Current_Price': 72,  # Spot price of Crude
        'Volatility': 0.30,
        'Risk_Free_Rate': 0.05
    }

    # Portfolio positions (scaled roughly for ~200K portfolio; assume multipliers: options 100 shares, futures standard)
    # MSFT_Call: assume 100 contracts * 100 shares * 15 premium = 150,000
    # Adjust: Position 100 -> 100 contracts, but premium 15 per share, total 150,000
    # Gold_Silver: 10 -> say 10 gold futures (100oz) but spread, simplify
    # For demo, keep small, but note in comments for scaling.
    portfolio = [
        {'Instrument': 'MSFT_Call', 'Position': 100, 'Entry_Price': 15.0},
        {'Instrument': 'Gold_Silver_Spread', 'Position': 10, 'Entry_Price': 1975.0},
        {'Instrument': 'Crude_Vertical_Spread', 'Position': 50, 'Entry_Price': 2.0}
    ]

    portfolio_df = pd.DataFrame(portfolio)
    print("Step 1: Defining Instruments and Initial Market Data")
    print(tabulate(portfolio_df, headers='keys', tablefmt='psql'))

    return msft_data, gold_silver_data, crude_vertical_data, portfolio_df

def print_initial_market_data(msft_data, gold_silver_data, crude_vertical_data):
    market_data = [
        {'Underlying': 'MSFT', 'Opening_Price': msft_data['Current_Price'], 'Volatility': msft_data['Volatility']},
        {'Underlying': 'Gold', 'Opening_Price': gold_silver_data['Gold_Price'], 'Volatility': None},
        {'Underlying': 'Silver', 'Opening_Price': gold_silver_data['Silver_Price'], 'Volatility': None},
        {'Underlying': 'Crude', 'Opening_Price': crude_vertical_data['Current_Price'], 'Volatility': crude_vertical_data['Volatility']}
    ]
    market_df = pd.DataFrame(market_data)
    print("\nInitial Market Data")
    print(tabulate(market_df, headers='keys', tablefmt='psql'))

    return market_df

def calculate_greeks(msft_data, gold_silver_data, crude_vertical_data):
    # MSFT Option Greeks
    S = msft_data['Current_Price']
    K = msft_data['Strike']
    T = msft_data['Expiry']
    r = msft_data['Risk_Free_Rate']
    sigma = msft_data['Volatility']
    delta_msft, gamma_msft, theta_msft, vega_msft = black_scholes_greeks(S, K, T, r, sigma, msft_data['Option_Type'])

    # Gold/Silver Spread Greeks (linear, no gamma/vega/theta)
    # Separate Delta_Gold and Delta_Silver because Gold and Silver prices are distinct risk factors.
    # Each instrument can expose to multiple risk factors: here, the spread exposes to Gold price and Silver price separately.
    # This allows tracking exposure at risk factor level (e.g., aggregate all Gold exposures across portfolio).
    spread_delta_gold = 1
    spread_delta_silver = -1
    spread_gamma = 0
    spread_theta = 0
    spread_vega = 0

    # Crude Vertical Spread Net Greeks
    long_delta, long_gamma, long_theta, long_vega = black_scholes_greeks(
        crude_vertical_data['Current_Price'], crude_vertical_data['Long_Strike'], crude_vertical_data['Expiry'],
        crude_vertical_data['Risk_Free_Rate'], crude_vertical_data['Volatility'], crude_vertical_data['Option_Type']
    )
    short_delta, short_gamma, short_theta, short_vega = black_scholes_greeks(
        crude_vertical_data['Current_Price'], crude_vertical_data['Short_Strike'], crude_vertical_data['Expiry'],
        crude_vertical_data['Risk_Free_Rate'], crude_vertical_data['Volatility'], crude_vertical_data['Option_Type']
    )
    net_delta_crude = long_delta - short_delta
    net_gamma_crude = long_gamma - short_gamma
    net_theta_crude = long_theta - short_theta
    net_vega_crude = long_vega - short_vega

    greeks_data = [
        {'Instrument': 'MSFT_Call', 'Delta_MSFT': delta_msft, 'Gamma_MSFT': gamma_msft, 'Theta': theta_msft, 'Vega_MSFT': vega_msft},  # Risk factors: MSFT price, MSFT vol, time
        {'Instrument': 'Gold_Silver_Spread', 'Delta_Gold': spread_delta_gold, 'Delta_Silver': spread_delta_silver, 'Gamma': spread_gamma, 'Theta': spread_theta, 'Vega': spread_vega},  # Risk factors: Gold price, Silver price
        {'Instrument': 'Crude_Vertical_Spread', 'Delta_Crude': net_delta_crude, 'Gamma_Crude': net_gamma_crude, 'Theta': net_theta_crude, 'Vega_Crude': net_vega_crude}  # Risk factors: Crude price, Crude vol, time
    ]

    greeks_df = pd.DataFrame(greeks_data)
    print("\nStep 2: Calculating Sensitivities (Greeks) for Each Instrument at Risk Factor Level")
    print(tabulate(greeks_df, headers='keys', tablefmt='psql'))

    return greeks_df, delta_msft, gamma_msft, theta_msft, vega_msft, spread_delta_gold, spread_delta_silver, spread_gamma, spread_theta, spread_vega, net_delta_crude, net_gamma_crude, net_theta_crude, net_vega_crude

def calculate_portfolio_risks(portfolio_df, delta_msft, gamma_msft, theta_msft, vega_msft, spread_delta_gold, spread_delta_silver, spread_gamma, spread_theta, spread_vega, net_delta_crude, net_gamma_crude, net_theta_crude, net_vega_crude):
    portfolio_risks = []
    for idx, row in portfolio_df.iterrows():
        instr = row['Instrument']
        pos = row['Position']
        if instr == 'MSFT_Call':
            delta = pos * delta_msft
            gamma = pos * gamma_msft
            theta = pos * theta_msft
            vega = pos * vega_msft
            portfolio_risks.append({'Instrument': instr, 'Total_Delta_MSFT': delta, 'Total_Gamma_MSFT': gamma, 'Total_Theta': theta, 'Total_Vega_MSFT': vega})
        elif instr == 'Gold_Silver_Spread':
            delta_gold = pos * spread_delta_gold
            delta_silver = pos * spread_delta_silver
            portfolio_risks.append({'Instrument': instr, 'Total_Delta_Gold': delta_gold, 'Total_Delta_Silver': delta_silver, 'Total_Gamma': 0, 'Total_Theta': 0, 'Total_Vega': 0})
        elif instr == 'Crude_Vertical_Spread':
            delta = pos * net_delta_crude
            gamma = pos * net_gamma_crude
            theta = pos * net_theta_crude
            vega = pos * net_vega_crude
            portfolio_risks.append({'Instrument': instr, 'Total_Delta_Crude': delta, 'Total_Gamma_Crude': gamma, 'Total_Theta': theta, 'Total_Vega_Crude': vega})

    portfolio_risks_df = pd.DataFrame(portfolio_risks)
    print("\nStep 3: Portfolio-Level Risks (Sensitivities)")
    print(tabulate(portfolio_risks_df, headers='keys', tablefmt='psql'))

    return portfolio_risks_df

def aggregate_risks(portfolio_risks_df):
    # Risk Factor Aggregation: This process involves summing up the sensitivities (Greeks) across all instruments for each common risk factor.
    # For example, all exposures to MSFT price (Delta_MSFT) are aggregated to get the total portfolio delta to MSFT.
    # This helps identify net exposures to specific market variables (e.g., prices, vols) and decide on hedges.
    # Benefits: Allows holistic risk management, spotting concentrations, and efficient hedging at factor level rather than per instrument.

    # Aggregate at risk factor level
    total_msft_delta = portfolio_risks_df.get('Total_Delta_MSFT', pd.Series([0])).sum()
    total_crude_delta = portfolio_risks_df.get('Total_Delta_Crude', pd.Series([0])).sum()
    total_gold_delta = portfolio_risks_df.get('Total_Delta_Gold', pd.Series([0])).sum()
    total_silver_delta = portfolio_risks_df.get('Total_Delta_Silver', pd.Series([0])).sum()

    total_msft_gamma = portfolio_risks_df.get('Total_Gamma_MSFT', pd.Series([0])).sum()
    total_crude_gamma = portfolio_risks_df.get('Total_Gamma_Crude', pd.Series([0])).sum()
    total_gamma = total_msft_gamma + total_crude_gamma

    total_msft_vega = portfolio_risks_df.get('Total_Vega_MSFT', pd.Series([0])).sum()
    total_crude_vega = portfolio_risks_df.get('Total_Vega_Crude', pd.Series([0])).sum()
    total_vega = total_msft_vega + total_crude_vega

    total_theta = portfolio_risks_df['Total_Theta'].sum()

    # Create a table with aggregated risks and explanations
    aggregated_data = [
        {'Risk_Factor': 'MSFT_Delta', 'Aggregated_Value': total_msft_delta, 'Explanation': 'Sum of all deltas to MSFT price across portfolio. High value indicates directional bias to MSFT moves.'},
        {'Risk_Factor': 'Crude_Delta', 'Aggregated_Value': total_crude_delta, 'Explanation': 'Sum of deltas to Crude price. Aggregated to manage commodity exposure.'},
        {'Risk_Factor': 'Gold_Delta', 'Aggregated_Value': total_gold_delta, 'Explanation': 'Sum of deltas to Gold price from spreads or other instruments.'},
        {'Risk_Factor': 'Silver_Delta', 'Aggregated_Value': total_silver_delta, 'Explanation': 'Sum of deltas to Silver price.'},
        {'Risk_Factor': 'MSFT_Gamma', 'Aggregated_Value': total_msft_gamma, 'Explanation': 'Aggregated gamma for MSFT; measures how delta changes with price.'},
        {'Risk_Factor': 'Crude_Gamma', 'Aggregated_Value': total_crude_gamma, 'Explanation': 'Aggregated gamma for Crude.'},
        {'Risk_Factor': 'Total_Gamma', 'Aggregated_Value': total_gamma, 'Explanation': 'Total gamma across underlyings (additive assumption for demo).'},
        {'Risk_Factor': 'MSFT_Vega', 'Aggregated_Value': total_msft_vega, 'Explanation': 'Aggregated vega to MSFT vol changes.'},
        {'Risk_Factor': 'Crude_Vega', 'Aggregated_Value': total_crude_vega, 'Explanation': 'Aggregated vega to Crude vol.'},
        {'Risk_Factor': 'Total_Vega', 'Aggregated_Value': total_vega, 'Explanation': 'Total vega (additive).'},
        {'Risk_Factor': 'Total_Theta', 'Aggregated_Value': total_theta, 'Explanation': 'Aggregated time decay across all options.'}
    ]

    aggregated_df = pd.DataFrame(aggregated_data)
    print("\nAggregated Risks at Risk Factor Level with Explanations")
    print(tabulate(aggregated_df, headers='keys', tablefmt='psql'))

    return total_msft_delta, total_crude_delta, total_gold_delta, total_silver_delta, total_msft_gamma, total_crude_gamma, total_gamma, total_msft_vega, total_crude_vega, total_vega, total_theta

def hedge_delta(total_msft_delta, total_crude_delta, total_gold_delta, total_silver_delta):
    msft_hedge = -total_msft_delta
    crude_hedge = -total_crude_delta
    gold_hedge = -total_gold_delta
    silver_hedge = -total_silver_delta

    hedges = [
        {'Hedge_Instrument': 'MSFT_Stock', 'Hedge_Position': msft_hedge, 'Explanation': f'Sell {abs(msft_hedge)} shares of MSFT if positive, or buy if negative, to offset delta exposure to MSFT price changes. Rationale: Delta measures price sensitivity; hedging neutralizes directional risk. Entry criteria: When total_msft_delta > threshold (e.g., 100), to avoid over-hedging small exposures. Better than options hedge: Lower cost, no time decay.'},
        {'Hedge_Instrument': 'Crude_Future', 'Hedge_Position': crude_hedge, 'Explanation': f'Sell {abs(crude_hedge)} Crude futures if positive, or buy if negative, to offset delta exposure to Crude price changes. Rationale: Keeps portfolio neutral to Crude price movements. Entry: If exposure exceeds 5% of portfolio value. Futures better than ETFs: Tighter tracking, lower fees.'},
        {'Hedge_Instrument': 'Gold_Future', 'Hedge_Position': gold_hedge, 'Explanation': f'Sell {abs(gold_hedge)} Gold futures if positive, or buy if negative, to offset exposure to Gold price. Rationale: Neutralizes specific commodity risk. Entry: During high vol periods. Better than physical gold: Liquidity, no storage costs.'},
        {'Hedge_Instrument': 'Silver_Future', 'Hedge_Position': silver_hedge, 'Explanation': f'Sell {abs(silver_hedge)} Silver futures if positive, or buy if negative, to offset exposure to Silver price. Rationale: Balances the spread trade risk. Entry: If spread delta imbalanced >10%. Futures vs options: Simpler for delta hedge, but options if gamma needed.'}
    ]

    hedges_df = pd.DataFrame(hedges)
    print("\nStep 4: Hedging to Delta Neutral")
    print(tabulate(hedges_df, headers='keys', tablefmt='psql'))

    return hedges_df

def hedge_gamma(total_msft_gamma, total_crude_gamma, msft_data, crude_vertical_data):
    # MSFT hedge: ATM call at strike 410
    hedge_strike_msft = msft_data['Current_Price']
    _, hedge_gamma_msft, _, _ = black_scholes_greeks(msft_data['Current_Price'], hedge_strike_msft, msft_data['Expiry'], msft_data['Risk_Free_Rate'], msft_data['Volatility'], 'call')
    msft_gamma_hedge_pos = -total_msft_gamma / hedge_gamma_msft if hedge_gamma_msft != 0 else 0

    # Crude hedge: ATM call at strike 72
    hedge_strike_crude = crude_vertical_data['Current_Price']
    _, hedge_gamma_crude, _, _ = black_scholes_greeks(crude_vertical_data['Current_Price'], hedge_strike_crude, crude_vertical_data['Expiry'], crude_vertical_data['Risk_Free_Rate'], crude_vertical_data['Volatility'], 'call')
    crude_gamma_hedge_pos = -total_crude_gamma / hedge_gamma_crude if hedge_gamma_crude != 0 else 0

    gamma_hedges = [
        {'Hedge_Instrument': 'MSFT_ATM_Call', 'Hedge_Position': msft_gamma_hedge_pos, 'Hedge_Gamma_Per_Unit': hedge_gamma_msft, 'Explanation': f'Trade {msft_gamma_hedge_pos} MSFT ATM calls (negative means sell, positive buy) to offset gamma. Rationale: Gamma measures convexity; hedging stabilizes delta as price changes. Entry: If gamma > 0.1, during volatile markets. Better than straddle: Targeted to underlying, lower premium.'},
        {'Hedge_Instrument': 'Crude_ATM_Call', 'Hedge_Position': crude_gamma_hedge_pos, 'Hedge_Gamma_Per_Unit': hedge_gamma_crude, 'Explanation': f'Trade {crude_gamma_hedge_pos} Crude ATM calls (negative means sell, positive buy) to offset gamma. Rationale: Reduces risk from large price swings affecting delta. Entry: Pre-earnings or news events. Calls vs puts: Similar gamma, but calls if bullish bias.'}
    ]

    gamma_hedges_df = pd.DataFrame(gamma_hedges)
    print("\nStep 4.2: Hedging to Gamma Neutral")
    print(tabulate(gamma_hedges_df, headers='keys', tablefmt='psql'))

    return gamma_hedges_df

def hedge_vega(total_msft_vega, total_crude_vega, msft_data, crude_vertical_data):
    hedge_strike_msft = msft_data['Current_Price']
    _, _, _, hedge_vega_msft = black_scholes_greeks(msft_data['Current_Price'], hedge_strike_msft, msft_data['Expiry'], msft_data['Risk_Free_Rate'], msft_data['Volatility'], 'put')
    msft_vega_hedge_pos = -total_msft_vega / hedge_vega_msft if hedge_vega_msft != 0 else 0

    hedge_strike_crude = crude_vertical_data['Current_Price']
    _, _, _, hedge_vega_crude = black_scholes_greeks(crude_vertical_data['Current_Price'], hedge_strike_crude, crude_vertical_data['Expiry'], crude_vertical_data['Risk_Free_Rate'], crude_vertical_data['Volatility'], 'put')
    crude_vega_hedge_pos = -total_crude_vega / hedge_vega_crude if hedge_vega_crude != 0 else 0

    vega_hedges = [
        {'Hedge_Instrument': 'MSFT_ATM_Put', 'Hedge_Position': msft_vega_hedge_pos, 'Hedge_Vega_Per_Unit': hedge_vega_msft, 'Explanation': f'Trade {msft_vega_hedge_pos} MSFT ATM puts (negative means sell, positive buy) to offset vega. Rationale: Vega measures vol sensitivity; hedging protects against volatility changes. Entry: Before vol events like earnings. Puts vs calls: Similar vega, but puts if expecting downside.'},
        {'Hedge_Instrument': 'Crude_ATM_Put', 'Hedge_Position': crude_vega_hedge_pos, 'Hedge_Vega_Per_Unit': hedge_vega_crude, 'Explanation': f'Trade {crude_vega_hedge_pos} Crude ATM puts (negative means sell, positive buy) to offset vega. Rationale: Neutralizes impact from implied vol shifts. Entry: If vega > portfolio limit. Better than VIX: Specific to underlying vol.'}
    ]

    vega_hedges_df = pd.DataFrame(vega_hedges)
    print("\nStep 4.5: Hedging to Vega Neutral")
    print(tabulate(vega_hedges_df, headers='keys', tablefmt='psql'))

    return vega_hedges_df

def hedge_theta(total_theta, msft_data, crude_vertical_data):
    # Theta hedging: Use options with opposite theta (e.g., if negative theta, sell options with positive theta, but theta is usually negative for long options).
    # For demo, assume hedging with short ATM calls (which have positive theta).
    hedge_strike_msft = msft_data['Current_Price']
    _, _, hedge_theta_msft, _ = black_scholes_greeks(msft_data['Current_Price'], hedge_strike_msft, msft_data['Expiry'], msft_data['Risk_Free_Rate'], msft_data['Volatility'], 'call')
    msft_theta_hedge_pos = -total_theta / 2 / hedge_theta_msft if hedge_theta_msft != 0 else 0  # Split between MSFT and Crude

    hedge_strike_crude = crude_vertical_data['Current_Price']
    _, _, hedge_theta_crude, _ = black_scholes_greeks(crude_vertical_data['Current_Price'], hedge_strike_crude, crude_vertical_data['Expiry'], crude_vertical_data['Risk_Free_Rate'], crude_vertical_data['Volatility'], 'call')
    crude_theta_hedge_pos = -total_theta / 2 / hedge_theta_crude if hedge_theta_crude != 0 else 0

    theta_hedges = [
        {'Hedge_Instrument': 'MSFT_ATM_Call_Short', 'Hedge_Position': msft_theta_hedge_pos, 'Hedge_Theta_Per_Unit': hedge_theta_msft, 'Explanation': f'Sell {abs(msft_theta_hedge_pos)} MSFT ATM calls (positive position means short) to offset theta. Rationale: Theta measures time decay; hedging balances daily decay/gain. Entry: If theta loss > $100/day. Short calls better than longs: Collect premium to offset decay.'},
        {'Hedge_Instrument': 'Crude_ATM_Call_Short', 'Hedge_Position': crude_theta_hedge_pos, 'Hedge_Theta_Per_Unit': hedge_theta_crude, 'Explanation': f'Sell {abs(crude_theta_hedge_pos)} Crude ATM calls (positive position means short) to offset theta. Rationale: Neutralizes time-based PnL erosion. Entry: Near expiry. Better in low vol: Higher theta collection.'}
    ]

    theta_hedges_df = pd.DataFrame(theta_hedges)
    print("\nStep 4.3: Hedging to Theta Neutral")
    print(tabulate(theta_hedges_df, headers='keys', tablefmt='psql'))

    return theta_hedges_df

def generate_hedge_trades(greek_type, underlying, exposure, expiry, volatility, current_price, risk_free_rate, hedge_options=2):
    # Function to generate a few hedge trade ideas for given parameters.
    # Parameters:
    # - greek_type: 'delta', 'gamma', 'vega', 'theta'
    # - underlying: e.g., 'MSFT', 'Crude'
    # - exposure: The current aggregated exposure (e.g., total_delta)
    # - expiry, volatility, current_price, risk_free_rate: For calculating Greeks of hedges
    # - hedge_options: Number of alternative hedges to generate
    # Outputs a DataFrame with hedge ideas, positions, and comments on why one better or entry criteria.

    hedges = []
    for i in range(hedge_options):
        if greek_type == 'delta':
            instrument = f'{underlying}_Future' if i == 0 else f'{underlying}_ETF'
            pos = -exposure
            comment = f'Entry: If exposure > 5% NAV. Futures better: High liquidity, low cost; ETF alternative: Easier for retail, but tracking error.'
        elif greek_type == 'gamma':
            option_type = 'call' if i == 0 else 'put'
            strike = current_price * (1 + 0.05 * i)  # Slight OTM for variety
            _, gamma, _, _ = black_scholes_greeks(current_price, strike, expiry, risk_free_rate, volatility, option_type)
            pos = -exposure / gamma if gamma != 0 else 0
            instrument = f'{underlying}_OTM_{option_type.capitalize()}'
            comment = f'Entry: During high vol (>30%). Call better if bullish; put if bearish bias. Balances gamma with directional view.'
        elif greek_type == 'vega':
            option_type = 'put' if i == 0 else 'call'
            strike = current_price
            _, _, _, vega = black_scholes_greeks(current_price, strike, expiry, risk_free_rate, volatility, option_type)
            pos = -exposure / vega if vega != 0 else 0
            instrument = f'{underlying}_ATM_{option_type.capitalize()}'
            comment = f'Entry: Pre-vol event. Put better for downside protection; call for upside. Longer expiry for higher vega.'
        elif greek_type == 'theta':
            option_type = 'call' if i == 0 else 'put'
            strike = current_price * (1 - 0.05 * i)  # Slight ITM for theta
            _, _, theta, _ = black_scholes_greeks(current_price, strike, expiry, risk_free_rate, volatility, option_type)
            pos = -exposure / theta if theta != 0 else 0
            instrument = f'{underlying}_Short_{option_type.capitalize()}'
            comment = f'Entry: If theta > daily target. Short call better in range-bound; short put if support levels hold. Risk: Unlimited loss if wrong.'
        else:
            raise ValueError("Invalid greek_type")

        hedges.append({'Hedge_Instrument': instrument, 'Hedge_Position': pos, 'Comment': comment})

    hedges_df = pd.DataFrame(hedges)
    print(f"\nGenerated Hedge Trades for {greek_type.upper()} on {underlying}")
    print(tabulate(hedges_df, headers='keys', tablefmt='psql'))

    return hedges_df

def print_market_changes(msft_data, gold_silver_data, crude_vertical_data, new_msft_price, new_gold_price, new_silver_price, new_crude_price, dvol=0, delta_t=1/365):
    market_changes = [
        {'Underlying': 'MSFT', 'Opening_Price': msft_data['Current_Price'], 'Current_Price': new_msft_price, 'Price_Change': new_msft_price - msft_data['Current_Price'], 'Vol_Change': dvol},
        {'Underlying': 'Gold', 'Opening_Price': gold_silver_data['Gold_Price'], 'Current_Price': new_gold_price, 'Price_Change': new_gold_price - gold_silver_data['Gold_Price'], 'Vol_Change': None},
        {'Underlying': 'Silver', 'Opening_Price': gold_silver_data['Silver_Price'], 'Current_Price': new_silver_price, 'Price_Change': new_silver_price - gold_silver_data['Silver_Price'], 'Vol_Change': None},
        {'Underlying': 'Crude', 'Opening_Price': crude_vertical_data['Current_Price'], 'Current_Price': new_crude_price, 'Price_Change': new_crude_price - crude_vertical_data['Current_Price'], 'Vol_Change': dvol}
    ]
    changes_df = pd.DataFrame(market_changes)
    print("\nMarket Data Changes (Including Time Passage: {:.4f} years)".format(delta_t))
    print(tabulate(changes_df, headers='keys', tablefmt='psql'))

    return changes_df

def simulate_market_change_and_pnl(portfolio_df, msft_data, gold_silver_data, crude_vertical_data, delta_msft, gamma_msft, theta_msft, vega_msft, net_delta_crude, net_gamma_crude, net_theta_crude, net_vega_crude, total_msft_delta, total_crude_delta, total_gold_delta, total_silver_delta, total_msft_gamma, total_crude_gamma, total_msft_vega, total_crude_vega, total_theta):
    # New market prices and changes
    new_msft_price = 415
    new_gold_price = 2010
    new_silver_price = 26
    new_crude_price = 74
    dvol = 0.01  # Small vol change for demo
    delta_t = 1/365

    # Print market changes
    changes_df = print_market_changes(msft_data, gold_silver_data, crude_vertical_data, new_msft_price, new_gold_price, new_silver_price, new_crude_price, dvol, delta_t)

    # Core Portfolio PnL
    ds_msft = new_msft_price - msft_data['Current_Price']
    pos_msft = portfolio_df[portfolio_df['Instrument'] == 'MSFT_Call']['Position'].values[0]
    pnl_msft = pos_msft * (delta_msft * ds_msft + 0.5 * gamma_msft * ds_msft**2 + theta_msft * delta_t + vega_msft * dvol)

    d_gold = new_gold_price - gold_silver_data['Gold_Price']
    d_silver = new_silver_price - gold_silver_data['Silver_Price']
    pos_spread = portfolio_df[portfolio_df['Instrument'] == 'Gold_Silver_Spread']['Position'].values[0]
    pnl_spread = pos_spread * (d_gold - d_silver * gold_silver_data['Ratio'])

    ds_crude = new_crude_price - crude_vertical_data['Current_Price']
    pos_crude = portfolio_df[portfolio_df['Instrument'] == 'Crude_Vertical_Spread']['Position'].values[0]
    pnl_crude = pos_crude * (net_delta_crude * ds_crude + 0.5 * net_gamma_crude * ds_crude**2 + net_theta_crude * delta_t + net_vega_crude * dvol)

    total_core_pnl = pnl_msft + pnl_spread + pnl_crude

    pnl_attrib = [
        {'Instrument': 'MSFT_Call', 'Delta_PnL': delta_msft * ds_msft * pos_msft, 'Gamma_PnL': 0.5 * gamma_msft * ds_msft**2 * pos_msft,
         'Theta_PnL': theta_msft * delta_t * pos_msft, 'Vega_PnL': vega_msft * dvol * pos_msft, 'Total_PnL': pnl_msft},
        {'Instrument': 'Gold_Silver_Spread', 'Gold_PnL': d_gold * pos_spread, 'Silver_PnL': -d_silver * pos_spread, 'Total_PnL': pnl_spread},
        {'Instrument': 'Crude_Vertical_Spread', 'Delta_PnL': net_delta_crude * ds_crude * pos_crude, 'Gamma_PnL': 0.5 * net_gamma_crude * ds_crude**2 * pos_crude,
         'Theta_PnL': net_theta_crude * delta_t * pos_crude, 'Vega_PnL': net_vega_crude * dvol * pos_crude, 'Total_PnL': pnl_crude}
    ]

    pnl_df = pd.DataFrame(pnl_attrib)
    print("\nStep 5: Simulate Market Change and Core Portfolio PnL Attribution")
    print(tabulate(pnl_df, headers='keys', tablefmt='psql'))
    print(f"Total Core PnL: {total_core_pnl}")

    # Demonstrate with more hedge trades: Delta, Gamma, Vega for MSFT and Crude
    # Hedge PnL calculations
    # Delta hedges (linear)
    msft_delta_hedge_pos = -total_msft_delta
    msft_delta_hedge_pnl = msft_delta_hedge_pos * ds_msft

    crude_delta_hedge_pos = -total_crude_delta
    crude_delta_hedge_pnl = crude_delta_hedge_pos * ds_crude

    gold_delta_hedge_pos = -total_gold_delta
    gold_delta_hedge_pnl = gold_delta_hedge_pos * d_gold

    silver_delta_hedge_pos = -total_silver_delta
    silver_delta_hedge_pnl = silver_delta_hedge_pos * d_silver

    # Gamma hedges (use approx PnL: delta*ds + 0.5*gamma*ds^2, but since hedge is option, full BS approx)
    # For simplicity, assume hedge option PnL using same Taylor
    msft_gamma_hedge_strike = msft_data['Current_Price']
    hedge_delta_msft, hedge_gamma_msft, hedge_theta_msft, hedge_vega_msft = black_scholes_greeks(msft_data['Current_Price'], msft_gamma_hedge_strike, msft_data['Expiry'], msft_data['Risk_Free_Rate'], msft_data['Volatility'], 'call')
    msft_gamma_hedge_pos = -total_msft_gamma / hedge_gamma_msft if hedge_gamma_msft != 0 else 0
    msft_gamma_hedge_pnl = msft_gamma_hedge_pos * (hedge_delta_msft * ds_msft + 0.5 * hedge_gamma_msft * ds_msft**2 + hedge_theta_msft * delta_t + hedge_vega_msft * dvol)

    crude_gamma_hedge_strike = crude_vertical_data['Current_Price']
    hedge_delta_crude, hedge_gamma_crude, hedge_theta_crude, hedge_vega_crude = black_scholes_greeks(crude_vertical_data['Current_Price'], crude_gamma_hedge_strike, crude_vertical_data['Expiry'], crude_vertical_data['Risk_Free_Rate'], crude_vertical_data['Volatility'], 'call')
    crude_gamma_hedge_pos = -total_crude_gamma / hedge_gamma_crude if hedge_gamma_crude != 0 else 0
    crude_gamma_hedge_pnl = crude_gamma_hedge_pos * (hedge_delta_crude * ds_crude + 0.5 * hedge_gamma_crude * ds_crude**2 + hedge_theta_crude * delta_t + hedge_vega_crude * dvol)

    # Vega hedges
    msft_vega_hedge_strike = msft_data['Current_Price']
    _, _, _, hedge_vega_msft = black_scholes_greeks(msft_data['Current_Price'], msft_vega_hedge_strike, msft_data['Expiry'], msft_data['Risk_Free_Rate'], msft_data['Volatility'], 'put')
    msft_vega_hedge_pos = -total_msft_vega / hedge_vega_msft if hedge_vega_msft != 0 else 0
    # For vega hedge PnL, but since vega is main, approx full
    hedge_delta_msft_v, hedge_gamma_msft_v, hedge_theta_msft_v, _ = black_scholes_greeks(msft_data['Current_Price'], msft_vega_hedge_strike, msft_data['Expiry'], msft_data['Risk_Free_Rate'], msft_data['Volatility'], 'put')
    msft_vega_hedge_pnl = msft_vega_hedge_pos * (hedge_delta_msft_v * ds_msft + 0.5 * hedge_gamma_msft_v * ds_msft**2 + hedge_theta_msft_v * delta_t + hedge_vega_msft * dvol)

    crude_vega_hedge_strike = crude_vertical_data['Current_Price']
    _, _, _, hedge_vega_crude = black_scholes_greeks(crude_vertical_data['Current_Price'], crude_vega_hedge_strike, crude_vertical_data['Expiry'], crude_vertical_data['Risk_Free_Rate'], crude_vertical_data['Volatility'], 'put')
    crude_vega_hedge_pos = -total_crude_vega / hedge_vega_crude if hedge_vega_crude != 0 else 0
    hedge_delta_crude_v, hedge_gamma_crude_v, hedge_theta_crude_v, _ = black_scholes_greeks(crude_vertical_data['Current_Price'], crude_vega_hedge_strike, crude_vertical_data['Expiry'], crude_vertical_data['Risk_Free_Rate'], crude_vertical_data['Volatility'], 'put')
    crude_vega_hedge_pnl = crude_vega_hedge_pos * (hedge_delta_crude_v * ds_crude + 0.5 * hedge_gamma_crude_v * ds_crude**2 + hedge_theta_crude_v * delta_t + hedge_vega_crude * dvol)

    # Theta hedges
    msft_theta_hedge_strike = msft_data['Current_Price']
    _, _, hedge_theta_msft, _ = black_scholes_greeks(msft_data['Current_Price'], msft_theta_hedge_strike, msft_data['Expiry'], msft_data['Risk_Free_Rate'], msft_data['Volatility'], 'call')
    msft_theta_hedge_pos = -total_theta / 2 / hedge_theta_msft if hedge_theta_msft != 0 else 0
    hedge_delta_msft_t, hedge_gamma_msft_t, _, hedge_vega_msft_t = black_scholes_greeks(msft_data['Current_Price'], msft_theta_hedge_strike, msft_data['Expiry'], msft_data['Risk_Free_Rate'], msft_data['Volatility'], 'call')
    msft_theta_hedge_pnl = msft_theta_hedge_pos * (hedge_delta_msft_t * ds_msft + 0.5 * hedge_gamma_msft_t * ds_msft**2 + hedge_theta_msft * delta_t + hedge_vega_msft_t * dvol)

    crude_theta_hedge_strike = crude_vertical_data['Current_Price']
    _, _, hedge_theta_crude, _ = black_scholes_greeks(crude_vertical_data['Current_Price'], crude_theta_hedge_strike, crude_vertical_data['Expiry'], crude_vertical_data['Risk_Free_Rate'], crude_vertical_data['Volatility'], 'call')
    crude_theta_hedge_pos = -total_theta / 2 / hedge_theta_crude if hedge_theta_crude != 0 else 0
    hedge_delta_crude_t, hedge_gamma_crude_t, _, hedge_vega_crude_t = black_scholes_greeks(crude_vertical_data['Current_Price'], crude_theta_hedge_strike, crude_vertical_data['Expiry'], crude_vertical_data['Risk_Free_Rate'], crude_vertical_data['Volatility'], 'call')
    crude_theta_hedge_pnl = crude_theta_hedge_pos * (hedge_delta_crude_t * ds_crude + 0.5 * hedge_gamma_crude_t * ds_crude**2 + hedge_theta_crude * delta_t + hedge_vega_crude_t * dvol)

    hedge_pnl_data = [
        {'Hedge': 'MSFT_Stock_Delta', 'Position': msft_delta_hedge_pos, 'Price_Change': ds_msft, 'Hedge_PnL': msft_delta_hedge_pnl},
        {'Hedge': 'Crude_Future_Delta', 'Position': crude_delta_hedge_pos, 'Price_Change': ds_crude, 'Hedge_PnL': crude_delta_hedge_pnl},
        {'Hedge': 'Gold_Future_Delta', 'Position': gold_delta_hedge_pos, 'Price_Change': d_gold, 'Hedge_PnL': gold_delta_hedge_pnl},
        {'Hedge': 'Silver_Future_Delta', 'Position': silver_delta_hedge_pos, 'Price_Change': d_silver, 'Hedge_PnL': silver_delta_hedge_pnl},
        {'Hedge': 'MSFT_ATM_Call_Gamma', 'Position': msft_gamma_hedge_pos, 'Price_Change': ds_msft, 'Hedge_PnL': msft_gamma_hedge_pnl},
        {'Hedge': 'Crude_ATM_Call_Gamma', 'Position': crude_gamma_hedge_pos, 'Price_Change': ds_crude, 'Hedge_PnL': crude_gamma_hedge_pnl},
        {'Hedge': 'MSFT_ATM_Put_Vega', 'Position': msft_vega_hedge_pos, 'Price_Change': ds_msft, 'Hedge_PnL': msft_vega_hedge_pnl},
        {'Hedge': 'Crude_ATM_Put_Vega', 'Position': crude_vega_hedge_pos, 'Price_Change': ds_crude, 'Hedge_PnL': crude_vega_hedge_pnl},
        {'Hedge': 'MSFT_ATM_Call_Theta', 'Position': msft_theta_hedge_pos, 'Price_Change': ds_msft, 'Hedge_PnL': msft_theta_hedge_pnl},
        {'Hedge': 'Crude_ATM_Call_Theta', 'Position': crude_theta_hedge_pos, 'Price_Change': ds_crude, 'Hedge_PnL': crude_theta_hedge_pnl}
    ]

    hedge_pnl_df = pd.DataFrame(hedge_pnl_data)
    total_hedge_pnl = hedge_pnl_df['Hedge_PnL'].sum()
    print("\nDemonstration: PnL from Executed Hedges (Delta, Gamma, Vega, Theta)")
    print(tabulate(hedge_pnl_df, headers='keys', tablefmt='psql'))
    print(f"Total Hedge PnL: {total_hedge_pnl}")
    print(f"Net Portfolio PnL (Core + All Hedges): {total_core_pnl + total_hedge_pnl}")

    return pnl_df, pnl_msft, pnl_spread, pnl_crude, new_msft_price, new_gold_price, new_silver_price, new_crude_price

def close_trades(portfolio_df, pnl_msft, pnl_spread, pnl_crude, new_msft_price, new_gold_price, new_silver_price, new_crude_price):
    # Approximate close prices
    msft_close_price = portfolio_df[portfolio_df['Instrument'] == 'MSFT_Call']['Entry_Price'].values[0] + pnl_msft / portfolio_df[portfolio_df['Instrument'] == 'MSFT_Call']['Position'].values[0]
    spread_close_price = (new_gold_price - new_silver_price)
    crude_close_price = portfolio_df[portfolio_df['Instrument'] == 'Crude_Vertical_Spread']['Entry_Price'].values[0] + pnl_crude / portfolio_df[portfolio_df['Instrument'] == 'Crude_Vertical_Spread']['Position'].values[0]

    close_data = [
        {'Instrument': 'MSFT_Call', 'Close_Price': msft_close_price, 'PnL': pnl_msft},
        {'Instrument': 'Gold_Silver_Spread', 'Close_Price': spread_close_price, 'PnL': pnl_spread},
        {'Instrument': 'Crude_Vertical_Spread', 'Close_Price': crude_close_price, 'PnL': pnl_crude}
    ]

    close_df = pd.DataFrame(close_data)
    print("\nStep 6: Closing Trades (Core Portfolio Only)")
    print(tabulate(close_df, headers='keys', tablefmt='psql'))

    total_pnl = pnl_msft + pnl_spread + pnl_crude
    print(f"\nTotal Core Portfolio PnL: {total_pnl}")

    return close_df, total_pnl

def main():
    msft_data, gold_silver_data, crude_vertical_data, portfolio_df = define_instruments_and_portfolio()
    
    initial_market_df = print_initial_market_data(msft_data, gold_silver_data, crude_vertical_data)
    
    greeks_df, delta_msft, gamma_msft, theta_msft, vega_msft, spread_delta_gold, spread_delta_silver, spread_gamma, spread_theta, spread_vega, net_delta_crude, net_gamma_crude, net_theta_crude, net_vega_crude = calculate_greeks(msft_data, gold_silver_data, crude_vertical_data)
    
    portfolio_risks_df = calculate_portfolio_risks(portfolio_df, delta_msft, gamma_msft, theta_msft, vega_msft, spread_delta_gold, spread_delta_silver, spread_gamma, spread_theta, spread_vega, net_delta_crude, net_gamma_crude, net_theta_crude, net_vega_crude)
    
    total_msft_delta, total_crude_delta, total_gold_delta, total_silver_delta, total_msft_gamma, total_crude_gamma, total_gamma, total_msft_vega, total_crude_vega, total_vega, total_theta = aggregate_risks(portfolio_risks_df)
    
    delta_hedges_df = hedge_delta(total_msft_delta, total_crude_delta, total_gold_delta, total_silver_delta)
    
    gamma_hedges_df = hedge_gamma(total_msft_gamma, total_crude_gamma, msft_data, crude_vertical_data)
    
    theta_hedges_df = hedge_theta(total_theta, msft_data, crude_vertical_data)
    
    vega_hedges_df = hedge_vega(total_msft_vega, total_crude_vega, msft_data, crude_vertical_data)
    
    # Example usage of generate_hedge_trades
    generate_hedge_trades('delta', 'MSFT', total_msft_delta, msft_data['Expiry'], msft_data['Volatility'], msft_data['Current_Price'], msft_data['Risk_Free_Rate'])
    generate_hedge_trades('gamma', 'Crude', total_crude_gamma, crude_vertical_data['Expiry'], crude_vertical_data['Volatility'], crude_vertical_data['Current_Price'], crude_vertical_data['Risk_Free_Rate'])
    generate_hedge_trades('vega', 'MSFT', total_msft_vega, msft_data['Expiry'], msft_data['Volatility'], msft_data['Current_Price'], msft_data['Risk_Free_Rate'])
    generate_hedge_trades('theta', 'Crude', total_theta / 2, crude_vertical_data['Expiry'], crude_vertical_data['Volatility'], crude_vertical_data['Current_Price'], crude_vertical_data['Risk_Free_Rate'])  # Split theta
    
    pnl_df, pnl_msft, pnl_spread, pnl_crude, new_msft_price, new_gold_price, new_silver_price, new_crude_price = simulate_market_change_and_pnl(portfolio_df, msft_data, gold_silver_data, crude_vertical_data, delta_msft, gamma_msft, theta_msft, vega_msft, net_delta_crude, net_gamma_crude, net_theta_crude, net_vega_crude, total_msft_delta, total_crude_delta, total_gold_delta, total_silver_delta, total_msft_gamma, total_crude_gamma, total_msft_vega, total_crude_vega, total_theta)
    
    close_df, total_pnl = close_trades(portfolio_df, pnl_msft, pnl_spread, pnl_crude, new_msft_price, new_gold_price, new_silver_price, new_crude_price)

if __name__ == "__main__":
    main()

# Note: For a $200K portfolio, this is realistic for retail traders using brokers like Interactive Brokers or ThinkOrSwim, which provide Greeks and risk analytics. Track daily via scripts or broker tools. Hedging reduces risk but adds costs; start with delta, then higher Greeks if needed.
