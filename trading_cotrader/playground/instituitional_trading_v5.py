
import pandas as pd
import numpy as np
from tabulate import tabulate
from scipy.stats import norm
import matplotlib.pyplot as plt
import argparse

def black_scholes_greeks(S, K, T, r, sigma, option_type='call'):
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == 'call':
        delta = norm.cdf(d1)
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        theta = - (S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * norm.cdf(d2)
        vega = S * np.sqrt(T) * norm.pdf(d1)
        rho = K * T * np.exp(-r * T) * norm.cdf(d2)
    elif option_type == 'put':
        delta = -norm.cdf(-d1)
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        theta = - (S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) + r * K * np.exp(-r * T) * norm.cdf(-d2)
        vega = S * np.sqrt(T) * norm.pdf(d1)
        rho = -K * T * np.exp(-r * T) * norm.cdf(-d2)
    else:
        raise ValueError("Invalid option type")
    
    return delta, gamma, theta, vega, rho

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
        'Silver_Delta': 1,
        'Expiry': 30/365,  # Added for option hedging demos
        'Volatility_Gold': 0.20,
        'Volatility_Silver': 0.30,
        'Risk_Free_Rate': 0.05
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
        {'Underlying': 'Gold', 'Opening_Price': gold_silver_data['Gold_Price'], 'Volatility': gold_silver_data['Volatility_Gold']},
        {'Underlying': 'Silver', 'Opening_Price': gold_silver_data['Silver_Price'], 'Volatility': gold_silver_data['Volatility_Silver']},
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
    delta_msft, gamma_msft, theta_msft, vega_msft, rho_msft = black_scholes_greeks(S, K, T, r, sigma, msft_data['Option_Type'])

    # Gold/Silver Spread Greeks (linear, no gamma/vega/theta/rho)
    # Separate Delta_Gold and Delta_Silver because Gold and Silver prices are distinct risk factors.
    # Each instrument can expose to multiple risk factors: here, the spread exposes to Gold price and Silver price separately.
    # This allows tracking exposure at risk factor level (e.g., aggregate all Gold exposures across portfolio).
    spread_delta_gold = 1
    spread_delta_silver = -1
    spread_gamma = 0
    spread_theta = 0
    spread_vega = 0
    spread_rho = 0  # Futures have negligible rho for short terms

    # Crude Vertical Spread Net Greeks
    long_delta, long_gamma, long_theta, long_vega, long_rho = black_scholes_greeks(
        crude_vertical_data['Current_Price'], crude_vertical_data['Long_Strike'], crude_vertical_data['Expiry'],
        crude_vertical_data['Risk_Free_Rate'], crude_vertical_data['Volatility'], crude_vertical_data['Option_Type']
    )
    short_delta, short_gamma, short_theta, short_vega, short_rho = black_scholes_greeks(
        crude_vertical_data['Current_Price'], crude_vertical_data['Short_Strike'], crude_vertical_data['Expiry'],
        crude_vertical_data['Risk_Free_Rate'], crude_vertical_data['Volatility'], crude_vertical_data['Option_Type']
    )
    net_delta_crude = long_delta - short_delta
    net_gamma_crude = long_gamma - short_gamma
    net_theta_crude = long_theta - short_theta
    net_vega_crude = long_vega - short_vega
    net_rho_crude = long_rho - short_rho

    greeks_data = [
        {'Instrument': 'MSFT_Call', 'Delta_MSFT': delta_msft, 'Gamma_MSFT': gamma_msft, 'Theta': theta_msft, 'Vega_MSFT': vega_msft, 'Rho_MSFT': rho_msft},  # Risk factors: MSFT price, MSFT vol, time, rates
        {'Instrument': 'Gold_Silver_Spread', 'Delta_Gold': spread_delta_gold, 'Delta_Silver': spread_delta_silver, 'Gamma': spread_gamma, 'Theta': spread_theta, 'Vega': spread_vega, 'Rho': spread_rho},  # Risk factors: Gold price, Silver price
        {'Instrument': 'Crude_Vertical_Spread', 'Delta_Crude': net_delta_crude, 'Gamma_Crude': net_gamma_crude, 'Theta': net_theta_crude, 'Vega_Crude': net_vega_crude, 'Rho_Crude': net_rho_crude}  # Risk factors: Crude price, Crude vol, time, rates
    ]

    greeks_df = pd.DataFrame(greeks_data)
    print("\nStep 2: Calculating Sensitivities (Greeks) for Each Instrument at Risk Factor Level")
    print(tabulate(greeks_df, headers='keys', tablefmt='psql'))

    return greeks_df, delta_msft, gamma_msft, theta_msft, vega_msft, rho_msft, spread_delta_gold, spread_delta_silver, spread_gamma, spread_theta, spread_vega, spread_rho, net_delta_crude, net_gamma_crude, net_theta_crude, net_vega_crude, net_rho_crude

def calculate_portfolio_risks(portfolio_df, delta_msft, gamma_msft, theta_msft, vega_msft, rho_msft, spread_delta_gold, spread_delta_silver, spread_gamma, spread_theta, spread_vega, spread_rho, net_delta_crude, net_gamma_crude, net_theta_crude, net_vega_crude, net_rho_crude):
    portfolio_risks = []
    for idx, row in portfolio_df.iterrows():
        instr = row['Instrument']
        pos = row['Position']
        if instr == 'MSFT_Call':
            delta = pos * delta_msft
            gamma = pos * gamma_msft
            theta = pos * theta_msft
            vega = pos * vega_msft
            rho = pos * rho_msft
            portfolio_risks.append({'Instrument': instr, 'Total_Delta_MSFT': delta, 'Total_Gamma_MSFT': gamma, 'Total_Theta': theta, 'Total_Vega_MSFT': vega, 'Total_Rho_MSFT': rho})
        elif instr == 'Gold_Silver_Spread':
            delta_gold = pos * spread_delta_gold
            delta_silver = pos * spread_delta_silver
            portfolio_risks.append({'Instrument': instr, 'Total_Delta_Gold': delta_gold, 'Total_Delta_Silver': delta_silver, 'Total_Gamma': 0, 'Total_Theta': 0, 'Total_Vega': 0, 'Total_Rho': 0})
        elif instr == 'Crude_Vertical_Spread':
            delta = pos * net_delta_crude
            gamma = pos * net_gamma_crude
            theta = pos * net_theta_crude
            vega = pos * net_vega_crude
            rho = pos * net_rho_crude
            portfolio_risks.append({'Instrument': instr, 'Total_Delta_Crude': delta, 'Total_Gamma_Crude': gamma, 'Total_Theta': theta, 'Total_Vega_Crude': vega, 'Total_Rho_Crude': rho})

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

    total_msft_rho = portfolio_risks_df.get('Total_Rho_MSFT', pd.Series([0])).sum()
    total_crude_rho = portfolio_risks_df.get('Total_Rho_Crude', pd.Series([0])).sum()
    total_rho = total_msft_rho + total_crude_rho

    total_theta = portfolio_risks_df.get('Total_Theta', pd.Series([0])).sum()

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
        {'Risk_Factor': 'MSFT_Rho', 'Aggregated_Value': total_msft_rho, 'Explanation': 'Aggregated rho to interest rate changes for MSFT options.'},
        {'Risk_Factor': 'Crude_Rho', 'Aggregated_Value': total_crude_rho, 'Explanation': 'Aggregated rho for Crude options.'},
        {'Risk_Factor': 'Total_Rho', 'Aggregated_Value': total_rho, 'Explanation': 'Total rho across options.'},
        {'Risk_Factor': 'Total_Theta', 'Aggregated_Value': total_theta, 'Explanation': 'Aggregated time decay across all options.'}
    ]

    aggregated_df = pd.DataFrame(aggregated_data)
    print("\nAggregated Risks at Risk Factor Level with Explanations")
    print(tabulate(aggregated_df, headers='keys', tablefmt='psql'))

    return total_msft_delta, total_crude_delta, total_gold_delta, total_silver_delta, total_msft_gamma, total_crude_gamma, total_gamma, total_msft_vega, total_crude_vega, total_vega, total_msft_rho, total_crude_rho, total_rho, total_theta, aggregated_df

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
    # Note on Gamma Hedging: Adding ATM options for gamma hedge does introduce additional delta (approximately 0.5 for ATM). However, this is not a vicious cycle. After adding the gamma hedge, you can adjust the delta hedge (using stocks or futures, which have zero gamma) to neutralize the new delta without affecting the gamma hedge. Hedging is done in layers: higher-order greeks first, then delta.

    # MSFT hedge: ATM call at strike 410
    hedge_strike_msft = msft_data['Current_Price']
    _, hedge_gamma_msft, _, _, _ = black_scholes_greeks(msft_data['Current_Price'], hedge_strike_msft, msft_data['Expiry'], msft_data['Risk_Free_Rate'], msft_data['Volatility'], 'call')
    msft_gamma_hedge_pos = -total_msft_gamma / hedge_gamma_msft if hedge_gamma_msft != 0 else 0

    # Crude hedge: ATM call at strike 72
    hedge_strike_crude = crude_vertical_data['Current_Price']
    _, hedge_gamma_crude, _, _, _ = black_scholes_greeks(crude_vertical_data['Current_Price'], hedge_strike_crude, crude_vertical_data['Expiry'], crude_vertical_data['Risk_Free_Rate'], crude_vertical_data['Volatility'], 'call')
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
    _, _, _, hedge_vega_msft, _ = black_scholes_greeks(msft_data['Current_Price'], hedge_strike_msft, msft_data['Expiry'], msft_data['Risk_Free_Rate'], msft_data['Volatility'], 'put')
    msft_vega_hedge_pos = -total_msft_vega / hedge_vega_msft if hedge_vega_msft != 0 else 0

    hedge_strike_crude = crude_vertical_data['Current_Price']
    _, _, _, hedge_vega_crude, _ = black_scholes_greeks(crude_vertical_data['Current_Price'], hedge_strike_crude, crude_vertical_data['Expiry'], crude_vertical_data['Risk_Free_Rate'], crude_vertical_data['Volatility'], 'put')
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
    _, _, hedge_theta_msft, _, _ = black_scholes_greeks(msft_data['Current_Price'], hedge_strike_msft, msft_data['Expiry'], msft_data['Risk_Free_Rate'], msft_data['Volatility'], 'call')
    msft_theta_hedge_pos = -total_theta / 2 / hedge_theta_msft if hedge_theta_msft != 0 else 0  # Split between MSFT and Crude

    hedge_strike_crude = crude_vertical_data['Current_Price']
    _, _, hedge_theta_crude, _, _ = black_scholes_greeks(crude_vertical_data['Current_Price'], hedge_strike_crude, crude_vertical_data['Expiry'], crude_vertical_data['Risk_Free_Rate'], crude_vertical_data['Volatility'], 'call')
    crude_theta_hedge_pos = -total_theta / 2 / hedge_theta_crude if hedge_theta_crude != 0 else 0

    theta_hedges = [
        {'Hedge_Instrument': 'MSFT_ATM_Call_Short', 'Hedge_Position': msft_theta_hedge_pos, 'Hedge_Theta_Per_Unit': hedge_theta_msft, 'Explanation': f'Sell {abs(msft_theta_hedge_pos)} MSFT ATM calls (positive position means short) to offset theta. Rationale: Theta measures time decay; hedging balances daily decay/gain. Entry: If theta loss > $100/day. Short calls better than longs: Collect premium to offset decay.'},
        {'Hedge_Instrument': 'Crude_ATM_Call_Short', 'Hedge_Position': crude_theta_hedge_pos, 'Hedge_Theta_Per_Unit': hedge_theta_crude, 'Explanation': f'Sell {abs(crude_theta_hedge_pos)} Crude ATM calls (positive position means short) to offset theta. Rationale: Neutralizes time-based PnL erosion. Entry: Near expiry. Better in low vol: Higher theta collection.'}
    ]

    theta_hedges_df = pd.DataFrame(theta_hedges)
    print("\nStep 4.3: Hedging to Theta Neutral")
    print(tabulate(theta_hedges_df, headers='keys', tablefmt='psql'))

    return theta_hedges_df

def hedge_rho(total_msft_rho, total_crude_rho, msft_data, crude_vertical_data):
    # Rho hedging: Sensitivity to interest rates. Hedge with interest rate instruments or longer-dated options.
    # For demo, use long-dated ATM calls (higher rho).
    long_expiry = 1.0  # 1 year for higher rho
    hedge_strike_msft = msft_data['Current_Price']
    _, _, _, _, hedge_rho_msft = black_scholes_greeks(msft_data['Current_Price'], hedge_strike_msft, long_expiry, msft_data['Risk_Free_Rate'], msft_data['Volatility'], 'call')
    msft_rho_hedge_pos = -total_msft_rho / hedge_rho_msft if hedge_rho_msft != 0 else 0

    hedge_strike_crude = crude_vertical_data['Current_Price']
    _, _, _, _, hedge_rho_crude = black_scholes_greeks(crude_vertical_data['Current_Price'], hedge_strike_crude, long_expiry, crude_vertical_data['Risk_Free_Rate'], crude_vertical_data['Volatility'], 'call')
    crude_rho_hedge_pos = -total_crude_rho / hedge_rho_crude if hedge_rho_crude != 0 else 0

    rho_hedges = [
        {'Hedge_Instrument': 'MSFT_Long_Dated_Call', 'Hedge_Position': msft_rho_hedge_pos, 'Hedge_Rho_Per_Unit': hedge_rho_msft, 'Explanation': f'Trade {msft_rho_hedge_pos} long-dated MSFT calls (negative means sell, positive buy) to offset rho. Rationale: Rho measures rate sensitivity; longer options have higher rho for hedging. Entry: If rates expected to change >0.5%. Better than bonds: Specific to equity rates exposure.'},
        {'Hedge_Instrument': 'Crude_Long_Dated_Call', 'Hedge_Position': crude_rho_hedge_pos, 'Hedge_Rho_Per_Unit': hedge_rho_crude, 'Explanation': f'Trade {crude_rho_hedge_pos} long-dated Crude calls to offset rho. Rationale: Neutralizes rate impact on option values. Entry: In rising rate environment. Options vs rate futures: Tied to underlying.'}
    ]

    rho_hedges_df = pd.DataFrame(rho_hedges)
    print("\nStep 4.4: Hedging to Rho Neutral")
    print(tabulate(rho_hedges_df, headers='keys', tablefmt='psql'))

    return rho_hedges_df

def generate_hedge_trades(greek_type, underlying, exposure, expiry, volatility, current_price, risk_free_rate, hedge_options=4):
    hedges = []
    recommended_index = 0
    rec_explain = ""
    optimizing = ""
    why_not_list = []

    if greek_type == 'delta':
        optimizing = "minimizing transaction costs while achieving delta neutrality without introducing additional risks like time decay."
        rec_explain = f"Recommend direct futures/ETF/stock hedge for {underlying}: lowest cost, no time decay, precise delta offset. Ideal for retail $200k portfolios."
        why_not_list = [
            "Rolling adds transaction costs and slippage without changing net delta significantly.",
            "Partial adjustment leaves residual directional risk; not true neutral.",
            "Booking loss realizes unnecessary loss when the core thesis is still valid."
        ]
        for i in range(hedge_options):
            if i == 0:
                instrument = f'{underlying}_Future_or_Stock'
                pos = f'{-exposure:.2f}' if isinstance(exposure, (int, float)) else '-exposure'
                comment = f'Hedge with futures/stock: Position {pos}. Pros: Low cost, high liquidity, direct offset.'
            elif i == 1:
                instrument = f'{underlying}_Option_Roll'
                pos = 'Roll to higher/lower strike based on direction'
                comment = f'Roll existing option position to adjust delta exposure.'
            elif i == 2:
                instrument = f'{underlying}_Adjust_Size'
                pos = f'Reduce position by {exposure / 2:.2f}' if isinstance(exposure, (int, float)) else 'Reduce by half'
                comment = f'Partially unwind the position to reduce delta.'
            elif i == 3:
                instrument = f'{underlying}_Close_Trade'
                pos = 'Close entire position'
                comment = f'Exit the trade completely to eliminate delta exposure.'
            hedges.append({'Hedge_Instrument': instrument, 'Position_Action': pos, 'Comment': comment, 'Recommended': 'No', 'Why_Not': ''})
    elif greek_type == 'gamma':
        optimizing = "balancing convexity protection with premium costs and avoiding unnecessary volatility exposure."
        rec_explain = f"Recommend ATM option hedge for {underlying}: highest gamma per contract, targeted convexity protection without excessive premium."
        why_not_list = [
            "Straddle is expensive and adds unnecessary vega exposure.",
            "Rolling to shorter expiry increases theta bleed and transaction costs.",
            "Booking loss removes positive convexity potential if volatility is expected."
        ]
        # Calculate sample hedge position for demo
        _, sample_gamma, _, _, _ = black_scholes_greeks(current_price, current_price, expiry, risk_free_rate, volatility, 'call')
        hedge_pos = -exposure / sample_gamma if sample_gamma != 0 else 0
        for i in range(hedge_options):
            if i == 0:
                instrument = f'{underlying}_ATM_Call_or_Put'
                pos = f'{hedge_pos:.2f} (negative=sell, positive=buy)'
                comment = f'Hedge with ATM options: High gamma efficiency, stabilizes delta changes.'
            elif i == 1:
                instrument = f'{underlying}_Straddle'
                pos = f'Buy/sell straddle equivalent to offset {exposure:.2f} gamma'
                comment = f'Use straddle for gamma hedge with vega component.'
            elif i == 2:
                instrument = f'{underlying}_Roll_to_Shorter_Expiry'
                pos = 'Roll to nearer expiry'
                comment = f'Roll position to shorter expiry to adjust gamma.'
            elif i == 3:
                instrument = f'{underlying}_Close_Trade'
                pos = 'Close entire position'
                comment = f'Exit the trade to eliminate gamma exposure.'
            hedges.append({'Hedge_Instrument': instrument, 'Position_Action': pos, 'Comment': comment, 'Recommended': 'No', 'Why_Not': ''})
    elif greek_type == 'vega':
        optimizing = "protecting against volatility shifts with minimal delta/gamma side effects and cost efficiency."
        rec_explain = f"Recommend longer-dated option hedge for {underlying}: higher vega exposure, better ratio for vol protection, minimal delta impact."
        why_not_list = [
            "Calendar spreads introduce complex theta and carry risks.",
            "Adding opposing positions increases overall position size and margin.",
            "Booking loss is premature if implied vol is still expected to rise."
        ]
        # Calculate sample
        long_expiry = 0.5  # Longer for higher vega
        _, _, _, sample_vega, _ = black_scholes_greeks(current_price, current_price, long_expiry, risk_free_rate, volatility, 'put')
        hedge_pos = -exposure / sample_vega if sample_vega != 0 else 0
        for i in range(hedge_options):
            if i == 0:
                instrument = f'{underlying}_Long_Dated_Put_or_Call'
                pos = f'{hedge_pos:.2f} (negative=sell, positive=buy)'
                comment = f'Hedge with longer-dated options: High vega per unit, targeted vol protection.'
            elif i == 1:
                instrument = f'{underlying}_Calendar_Spread'
                pos = 'Buy/sell calendar spread'
                comment = f'Use calendar spread for vega adjustment.'
            elif i == 2:
                instrument = f'{underlying}_Add_Opposing_Position'
                pos = f'Add position to offset {exposure:.2f} vega'
                comment = f'Add counter positions to net out vega.'
            elif i == 3:
                instrument = f'{underlying}_Close_Trade'
                pos = 'Close entire position'
                comment = f'Exit the trade to eliminate vega exposure.'
            hedges.append({'Hedge_Instrument': instrument, 'Position_Action': pos, 'Comment': comment, 'Recommended': 'No', 'Why_Not': ''})
    elif greek_type == 'theta':
        optimizing = "offsetting time decay with income generation while limiting downside risk."
        rec_explain = f"Recommend short option (or iron condor) for {underlying}: positive theta collection, defined risk when using condor."
        why_not_list = [
            "Naked short options carry unlimited risk, unsuitable for most retail traders.",
            "Rolling extends exposure but adds costs and may chase decaying value.",
            "Booking loss removes income stream when time decay is the strategy edge."
        ]
        # Calculate sample
        _, _, sample_theta, _, _ = black_scholes_greeks(current_price, current_price, expiry, risk_free_rate, volatility, 'call')
        hedge_pos = -exposure / sample_theta if sample_theta != 0 else 0
        for i in range(hedge_options):
            if i == 0:
                instrument = f'{underlying}_Iron_Condor_or_Short_Option'
                pos = f'{hedge_pos:.2f} (positive=short)'
                comment = f'Sell options or iron condor: Collect theta, defined risk.'
            elif i == 1:
                instrument = f'{underlying}_Naked_Short'
                pos = 'Sell naked options'
                comment = f'Naked short for high theta collection (high risk).'
            elif i == 2:
                instrument = f'{underlying}_Roll_Position'
                pos = 'Roll to new expiry'
                comment = f'Roll to manage theta decay.'
            elif i == 3:
                instrument = f'{underlying}_Close_Trade'
                pos = 'Close entire position'
                comment = f'Exit to stop theta bleed.'
            hedges.append({'Hedge_Instrument': instrument, 'Position_Action': pos, 'Comment': comment, 'Recommended': 'No', 'Why_Not': ''})
    elif greek_type == 'rho':
        optimizing = "neutralizing interest rate sensitivity with low cost and minimal impact on other greeks."
        rec_explain = f"Recommend interest rate futures or long-dated options for {underlying}: direct rate exposure hedge, especially in rising rate environment."
        why_not_list = [
            "Long-dated options are capital intensive and add unwanted gamma/vega.",
            "Adjusting expiry reduces rho but also changes delta and theta.",
            "Booking loss is too aggressive if rates movement is temporary."
        ]
        # Calculate sample
        long_expiry = 1.0
        _, _, _, _, sample_rho = black_scholes_greeks(current_price, current_price, long_expiry, risk_free_rate, volatility, 'call')
        hedge_pos = -exposure / sample_rho if sample_rho != 0 else 0
        for i in range(hedge_options):
            if i == 0:
                instrument = f'{underlying}_Rate_Future_or_Long_Dated_Option'
                pos = f'{hedge_pos:.2f}'
                comment = f'Hedge with rate futures or long-dated options: Direct rho offset.'
            elif i == 1:
                instrument = f'{underlying}_Long_Dated_Option_Only'
                pos = f'{hedge_pos:.2f}'
                comment = f'Use long-dated options for rho hedge.'
            elif i == 2:
                instrument = f'{underlying}_Adjust_Expiry'
                pos = 'Shift to different expiry'
                comment = f'Adjust option expiry to modify rho.'
            elif i == 3:
                instrument = f'{underlying}_Close_Trade'
                pos = 'Close entire position'
                comment = f'Exit to eliminate rho exposure.'
            hedges.append({'Hedge_Instrument': instrument, 'Position_Action': pos, 'Comment': comment, 'Recommended': 'No', 'Why_Not': ''})

    # Set recommended and why_not
    hedges[recommended_index]['Recommended'] = 'Yes'
    hedges[recommended_index]['Why_Not'] = 'This is the recommended hedge.'
    for j, why_not in enumerate(why_not_list, start=1):
        if j < len(hedges):
            hedges[j]['Why_Not'] = why_not

    hedges_df = pd.DataFrame(hedges)
    print(f"\nHedging Options for {greek_type.upper()} on {underlying}")
    print(f"Optimizing for: {optimizing}")
    print(rec_explain)
    print(tabulate(hedges_df, headers='keys', tablefmt='psql'))

def print_market_changes(msft_data, gold_silver_data, crude_vertical_data, new_msft_price, new_gold_price, new_silver_price, new_crude_price, dvol=0, dr=0, delta_t=1/365):
    market_changes = [
        {'Underlying': 'MSFT', 'Opening_Price': msft_data['Current_Price'], 'Current_Price': new_msft_price, 'Price_Change': new_msft_price - msft_data['Current_Price'], 'Vol_Change': dvol, 'Rate_Change': dr},
        {'Underlying': 'Gold', 'Opening_Price': gold_silver_data['Gold_Price'], 'Current_Price': new_gold_price, 'Price_Change': new_gold_price - gold_silver_data['Gold_Price'], 'Vol_Change': None, 'Rate_Change': None},
        {'Underlying': 'Silver', 'Opening_Price': gold_silver_data['Silver_Price'], 'Current_Price': new_silver_price, 'Price_Change': new_silver_price - gold_silver_data['Silver_Price'], 'Vol_Change': None, 'Rate_Change': None},
        {'Underlying': 'Crude', 'Opening_Price': crude_vertical_data['Current_Price'], 'Current_Price': new_crude_price, 'Price_Change': new_crude_price - crude_vertical_data['Current_Price'], 'Vol_Change': dvol, 'Rate_Change': dr}
    ]
    changes_df = pd.DataFrame(market_changes)
    print("\nMarket Data Changes (Including Time Passage: {:.4f} years, Rate Change: {:.4f})".format(delta_t, dr))
    print(tabulate(changes_df, headers='keys', tablefmt='psql'))

    return changes_df

def simulate_market_change_and_pnl(portfolio_df, msft_data, gold_silver_data, crude_vertical_data, delta_msft, gamma_msft, theta_msft, vega_msft, rho_msft, net_delta_crude, net_gamma_crude, net_theta_crude, net_vega_crude, net_rho_crude, total_msft_delta, total_crude_delta, total_gold_delta, total_silver_delta, total_msft_gamma, total_crude_gamma, total_msft_vega, total_crude_vega, total_msft_rho, total_crude_rho, total_theta):
    # New market prices and changes
    new_msft_price = 415
    new_gold_price = 2010
    new_silver_price = 26
    new_crude_price = 74
    dvol = 0.01  # Small vol change for demo
    dr = 0.001  # 10 bps rate change
    delta_t = 1/365

    # Print market changes
    changes_df = print_market_changes(msft_data, gold_silver_data, crude_vertical_data, new_msft_price, new_gold_price, new_silver_price, new_crude_price, dvol, dr, delta_t)

    # Core Portfolio PnL (add rho * dr)
    ds_msft = new_msft_price - msft_data['Current_Price']
    pos_msft = portfolio_df[portfolio_df['Instrument'] == 'MSFT_Call']['Position'].values[0]
    pnl_msft = pos_msft * (delta_msft * ds_msft + 0.5 * gamma_msft * ds_msft**2 + theta_msft * delta_t + vega_msft * dvol + rho_msft * dr)

    d_gold = new_gold_price - gold_silver_data['Gold_Price']
    d_silver = new_silver_price - gold_silver_data['Silver_Price']
    pos_spread = portfolio_df[portfolio_df['Instrument'] == 'Gold_Silver_Spread']['Position'].values[0]
    pnl_spread = pos_spread * (d_gold - d_silver * gold_silver_data['Ratio'])

    ds_crude = new_crude_price - crude_vertical_data['Current_Price']
    pos_crude = portfolio_df[portfolio_df['Instrument'] == 'Crude_Vertical_Spread']['Position'].values[0]
    pnl_crude = pos_crude * (net_delta_crude * ds_crude + 0.5 * net_gamma_crude * ds_crude**2 + net_theta_crude * delta_t + net_vega_crude * dvol + net_rho_crude * dr)

    total_core_pnl = pnl_msft + pnl_spread + pnl_crude

    pnl_attrib = [
        {'Instrument': 'MSFT_Call', 'Delta_PnL': delta_msft * ds_msft * pos_msft, 'Gamma_PnL': 0.5 * gamma_msft * ds_msft**2 * pos_msft,
         'Theta_PnL': theta_msft * delta_t * pos_msft, 'Vega_PnL': vega_msft * dvol * pos_msft, 'Rho_PnL': rho_msft * dr * pos_msft, 'Total_PnL': pnl_msft},
        {'Instrument': 'Gold_Silver_Spread', 'Gold_PnL': d_gold * pos_spread, 'Silver_PnL': -d_silver * pos_spread, 'Total_PnL': pnl_spread},
        {'Instrument': 'Crude_Vertical_Spread', 'Delta_PnL': net_delta_crude * ds_crude * pos_crude, 'Gamma_PnL': 0.5 * net_gamma_crude * ds_crude**2 * pos_crude,
         'Theta_PnL': net_theta_crude * delta_t * pos_crude, 'Vega_PnL': net_vega_crude * dvol * pos_crude, 'Rho_PnL': net_rho_crude * dr * pos_crude, 'Total_PnL': pnl_crude}
    ]

    pnl_df = pd.DataFrame(pnl_attrib)
    print("\nStep 5: Simulate Market Change and Core Portfolio PnL Attribution")
    print(tabulate(pnl_df, headers='keys', tablefmt='psql'))
    print(f"Total Core PnL: {total_core_pnl}")

    # Demonstrate with more hedge trades: Delta, Gamma, Vega, Theta, Rho for MSFT and Crude
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

    # Gamma hedges
    msft_gamma_hedge_strike = msft_data['Current_Price']
    hedge_delta_msft, hedge_gamma_msft, hedge_theta_msft, hedge_vega_msft, hedge_rho_msft = black_scholes_greeks(msft_data['Current_Price'], msft_gamma_hedge_strike, msft_data['Expiry'], msft_data['Risk_Free_Rate'], msft_data['Volatility'], 'call')
    msft_gamma_hedge_pos = -total_msft_gamma / hedge_gamma_msft if hedge_gamma_msft != 0 else 0
    msft_gamma_hedge_pnl = msft_gamma_hedge_pos * (hedge_delta_msft * ds_msft + 0.5 * hedge_gamma_msft * ds_msft**2 + hedge_theta_msft * delta_t + hedge_vega_msft * dvol + hedge_rho_msft * dr)

    crude_gamma_hedge_strike = crude_vertical_data['Current_Price']
    hedge_delta_crude, hedge_gamma_crude, hedge_theta_crude, hedge_vega_crude, hedge_rho_crude = black_scholes_greeks(crude_vertical_data['Current_Price'], crude_gamma_hedge_strike, crude_vertical_data['Expiry'], crude_vertical_data['Risk_Free_Rate'], crude_vertical_data['Volatility'], 'call')
    crude_gamma_hedge_pos = -total_crude_gamma / hedge_gamma_crude if hedge_gamma_crude != 0 else 0
    crude_gamma_hedge_pnl = crude_gamma_hedge_pos * (hedge_delta_crude * ds_crude + 0.5 * hedge_gamma_crude * ds_crude**2 + hedge_theta_crude * delta_t + hedge_vega_crude * dvol + hedge_rho_crude * dr)

    # Vega hedges
    msft_vega_hedge_strike = msft_data['Current_Price']
    hedge_delta_msft_v, hedge_gamma_msft_v, hedge_theta_msft_v, hedge_vega_msft, hedge_rho_msft_v = black_scholes_greeks(msft_data['Current_Price'], msft_vega_hedge_strike, msft_data['Expiry'], msft_data['Risk_Free_Rate'], msft_data['Volatility'], 'put')
    msft_vega_hedge_pos = -total_msft_vega / hedge_vega_msft if hedge_vega_msft != 0 else 0
    msft_vega_hedge_pnl = msft_vega_hedge_pos * (hedge_delta_msft_v * ds_msft + 0.5 * hedge_gamma_msft_v * ds_msft**2 + hedge_theta_msft_v * delta_t + hedge_vega_msft * dvol + hedge_rho_msft_v * dr)

    crude_vega_hedge_strike = crude_vertical_data['Current_Price']
    hedge_delta_crude_v, hedge_gamma_crude_v, hedge_theta_crude_v, hedge_vega_crude, hedge_rho_crude_v = black_scholes_greeks(crude_vertical_data['Current_Price'], crude_vega_hedge_strike, crude_vertical_data['Expiry'], crude_vertical_data['Risk_Free_Rate'], crude_vertical_data['Volatility'], 'put')
    crude_vega_hedge_pos = -total_crude_vega / hedge_vega_crude if hedge_vega_crude != 0 else 0
    crude_vega_hedge_pnl = crude_vega_hedge_pos * (hedge_delta_crude_v * ds_crude + 0.5 * hedge_gamma_crude_v * ds_crude**2 + hedge_theta_crude_v * delta_t + hedge_vega_crude * dvol + hedge_rho_crude_v * dr)

    # Theta hedges
    msft_theta_hedge_strike = msft_data['Current_Price']
    hedge_delta_msft_t, hedge_gamma_msft_t, hedge_theta_msft, hedge_vega_msft_t, hedge_rho_msft_t = black_scholes_greeks(msft_data['Current_Price'], msft_theta_hedge_strike, msft_data['Expiry'], msft_data['Risk_Free_Rate'], msft_data['Volatility'], 'call')
    msft_theta_hedge_pos = -total_theta / 2 / hedge_theta_msft if hedge_theta_msft != 0 else 0
    msft_theta_hedge_pnl = msft_theta_hedge_pos * (hedge_delta_msft_t * ds_msft + 0.5 * hedge_gamma_msft_t * ds_msft**2 + hedge_theta_msft * delta_t + hedge_vega_msft_t * dvol + hedge_rho_msft_t * dr)

    crude_theta_hedge_strike = crude_vertical_data['Current_Price']
    hedge_delta_crude_t, hedge_gamma_crude_t, hedge_theta_crude, hedge_vega_crude_t, hedge_rho_crude_t = black_scholes_greeks(crude_vertical_data['Current_Price'], crude_theta_hedge_strike, crude_vertical_data['Expiry'], crude_vertical_data['Risk_Free_Rate'], crude_vertical_data['Volatility'], 'call')
    crude_theta_hedge_pos = -total_theta / 2 / hedge_theta_crude if hedge_theta_crude != 0 else 0
    crude_theta_hedge_pnl = crude_theta_hedge_pos * (hedge_delta_crude_t * ds_crude + 0.5 * hedge_gamma_crude_t * ds_crude**2 + hedge_theta_crude * delta_t + hedge_vega_crude_t * dvol + hedge_rho_crude_t * dr)

    # Rho hedges
    long_expiry = 1.0
    msft_rho_hedge_strike = msft_data['Current_Price']
    hedge_delta_msft_r, hedge_gamma_msft_r, hedge_theta_msft_r, hedge_vega_msft_r, hedge_rho_msft = black_scholes_greeks(msft_data['Current_Price'], msft_rho_hedge_strike, long_expiry, msft_data['Risk_Free_Rate'], msft_data['Volatility'], 'call')
    msft_rho_hedge_pos = -total_msft_rho / hedge_rho_msft if hedge_rho_msft != 0 else 0
    msft_rho_hedge_pnl = msft_rho_hedge_pos * (hedge_delta_msft_r * ds_msft + 0.5 * hedge_gamma_msft_r * ds_msft**2 + hedge_theta_msft_r * delta_t + hedge_vega_msft_r * dvol + hedge_rho_msft * dr)

    crude_rho_hedge_strike = crude_vertical_data['Current_Price']
    hedge_delta_crude_r, hedge_gamma_crude_r, hedge_theta_crude_r, hedge_vega_crude_r, hedge_rho_crude = black_scholes_greeks(crude_vertical_data['Current_Price'], crude_rho_hedge_strike, long_expiry, crude_vertical_data['Risk_Free_Rate'], crude_vertical_data['Volatility'], 'call')
    crude_rho_hedge_pos = -total_crude_rho / hedge_rho_crude if hedge_rho_crude != 0 else 0
    crude_rho_hedge_pnl = crude_rho_hedge_pos * (hedge_delta_crude_r * ds_crude + 0.5 * hedge_gamma_crude_r * ds_crude**2 + hedge_theta_crude_r * delta_t + hedge_vega_crude_r * dvol + hedge_rho_crude * dr)

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
        {'Hedge': 'Crude_ATM_Call_Theta', 'Position': crude_theta_hedge_pos, 'Price_Change': ds_crude, 'Hedge_PnL': crude_theta_hedge_pnl},
        {'Hedge': 'MSFT_Long_Call_Rho', 'Position': msft_rho_hedge_pos, 'Price_Change': ds_msft, 'Hedge_PnL': msft_rho_hedge_pnl},
        {'Hedge': 'Crude_Long_Call_Rho', 'Position': crude_rho_hedge_pos, 'Price_Change': ds_crude, 'Hedge_PnL': crude_rho_hedge_pnl}
    ]

    hedge_pnl_df = pd.DataFrame(hedge_pnl_data)
    total_hedge_pnl = hedge_pnl_df['Hedge_PnL'].sum()
    print("\nDemonstration: PnL from Executed Hedges (Delta, Gamma, Vega, Theta, Rho)")
    print(tabulate(hedge_pnl_df, headers='keys', tablefmt='psql'))
    print(f"Total Hedge PnL: {total_hedge_pnl}")
    print(f"Net Portfolio PnL (Core + All Hedges): {total_core_pnl + total_hedge_pnl}")

    return pnl_df, pnl_msft, pnl_spread, pnl_crude, new_msft_price, new_gold_price, new_silver_price, new_crude_price, total_core_pnl, total_hedge_pnl

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

def final_aggregated_risk_table_including_hedges(portfolio_risks_df, delta_hedges_df, gamma_hedges_df, vega_hedges_df, theta_hedges_df, rho_hedges_df, msft_data, gold_silver_data, crude_vertical_data, total_core_pnl, total_hedge_pnl):
    hedge_risks = []
    hedge_dfs = [delta_hedges_df, gamma_hedges_df, vega_hedges_df, theta_hedges_df, rho_hedges_df]

    for df in hedge_dfs:
        for _, row in df.iterrows():
            instr = row['Hedge_Instrument']
            pos = row['Hedge_Position']
            if 'MSFT_Stock' in instr or 'MSFT_Future' in instr:
                hedge_risks.append({'Instrument': instr, 'Total_Delta_MSFT': pos, 'Total_Gamma_MSFT': 0, 'Total_Theta': 0, 'Total_Vega_MSFT': 0, 'Total_Rho_MSFT': 0})
            elif 'Crude_Future' in instr:
                hedge_risks.append({'Instrument': instr, 'Total_Delta_Crude': pos, 'Total_Gamma_Crude': 0, 'Total_Theta': 0, 'Total_Vega_Crude': 0, 'Total_Rho_Crude': 0})
            elif 'Gold_Future' in instr:
                hedge_risks.append({'Instrument': instr, 'Total_Delta_Gold': pos, 'Total_Gamma': 0, 'Total_Theta': 0, 'Total_Vega': 0, 'Total_Rho': 0})
            elif 'Silver_Future' in instr:
                hedge_risks.append({'Instrument': instr, 'Total_Delta_Silver': pos, 'Total_Gamma': 0, 'Total_Theta': 0, 'Total_Vega': 0, 'Total_Rho': 0})
            elif ('ATM_Call' in instr or 'ATM_Put' in instr or 'Long_Dated_Call' in instr or 'Call_Short' in instr or 'Put' in instr):
                if 'MSFT' in instr:
                    und = msft_data
                    underlying_key = 'MSFT'
                    S = msft_data['Current_Price']
                    sigma = msft_data['Volatility']
                elif 'Crude' in instr:
                    und = crude_vertical_data
                    underlying_key = 'Crude'
                    S = crude_vertical_data['Current_Price']
                    sigma = crude_vertical_data['Volatility']
                elif 'Gold' in instr:
                    und = gold_silver_data
                    underlying_key = 'Gold'
                    S = gold_silver_data['Gold_Price']
                    sigma = gold_silver_data['Volatility_Gold']
                elif 'Silver' in instr:
                    und = gold_silver_data
                    underlying_key = 'Silver'
                    S = gold_silver_data['Silver_Price']
                    sigma = gold_silver_data['Volatility_Silver']
                else:
                    continue

                option_type = 'call' if 'Call' in instr else 'put'
                expiry = und['Expiry'] if 'Long_Dated' not in instr else 1.0
                strike = S  # ATM
                r = und['Risk_Free_Rate']
                delta_h, gamma_h, theta_h, vega_h, rho_h = black_scholes_greeks(S, strike, expiry, r, sigma, option_type)
                if '_Short' in instr:
                    # For short, greeks are negative of long
                    delta_h *= -1
                    gamma_h *= -1
                    theta_h *= -1
                    vega_h *= -1
                    rho_h *= -1

                hedge_risks.append({'Instrument': instr, f'Total_Delta_{underlying_key}': pos * delta_h, f'Total_Gamma_{underlying_key}': pos * gamma_h, 'Total_Theta': pos * theta_h, f'Total_Vega_{underlying_key}': pos * vega_h, f'Total_Rho_{underlying_key}': pos * rho_h})
            else:
                continue

    hedge_risks_df = pd.DataFrame(hedge_risks)
    extended_risks_df = pd.concat([portfolio_risks_df, hedge_risks_df], ignore_index=True)

    print("\nConsolidated Portfolio Risks Including Hedges (Positions and Sensitivities)")
    print(tabulate(extended_risks_df, headers='keys', tablefmt='psql'))

    # Now aggregate the extended risks
    total_msft_delta = extended_risks_df.get('Total_Delta_MSFT', pd.Series([0])).sum()
    total_crude_delta = extended_risks_df.get('Total_Delta_Crude', pd.Series([0])).sum()
    total_gold_delta = extended_risks_df.get('Total_Delta_Gold', pd.Series([0])).sum()
    total_silver_delta = extended_risks_df.get('Total_Delta_Silver', pd.Series([0])).sum()

    total_msft_gamma = extended_risks_df.get('Total_Gamma_MSFT', pd.Series([0])).sum()
    total_crude_gamma = extended_risks_df.get('Total_Gamma_Crude', pd.Series([0])).sum()
    total_gamma = total_msft_gamma + total_crude_gamma

    total_msft_vega = extended_risks_df.get('Total_Vega_MSFT', pd.Series([0])).sum()
    total_crude_vega = extended_risks_df.get('Total_Vega_Crude', pd.Series([0])).sum()
    total_vega = total_msft_vega + total_crude_vega

    total_msft_rho = extended_risks_df.get('Total_Rho_MSFT', pd.Series([0])).sum()
    total_crude_rho = extended_risks_df.get('Total_Rho_Crude', pd.Series([0])).sum()
    total_rho = total_msft_rho + total_crude_rho

    total_theta = extended_risks_df.get('Total_Theta', pd.Series([0])).sum()

    aggregated_data = [
        {'Risk_Factor': 'MSFT_Delta', 'Aggregated_Value': total_msft_delta, 'Explanation': 'Net delta to MSFT after hedges.'},
        {'Risk_Factor': 'Crude_Delta', 'Aggregated_Value': total_crude_delta, 'Explanation': 'Net delta to Crude after hedges.'},
        {'Risk_Factor': 'Gold_Delta', 'Aggregated_Value': total_gold_delta, 'Explanation': 'Net delta to Gold after hedges.'},
        {'Risk_Factor': 'Silver_Delta', 'Aggregated_Value': total_silver_delta, 'Explanation': 'Net delta to Silver after hedges.'},
        {'Risk_Factor': 'MSFT_Gamma', 'Aggregated_Value': total_msft_gamma, 'Explanation': 'Net gamma for MSFT after hedges.'},
        {'Risk_Factor': 'Crude_Gamma', 'Aggregated_Value': total_crude_gamma, 'Explanation': 'Net gamma for Crude after hedges.'},
        {'Risk_Factor': 'Total_Gamma', 'Aggregated_Value': total_gamma, 'Explanation': 'Net total gamma after hedges.'},
        {'Risk_Factor': 'MSFT_Vega', 'Aggregated_Value': total_msft_vega, 'Explanation': 'Net vega to MSFT after hedges.'},
        {'Risk_Factor': 'Crude_Vega', 'Aggregated_Value': total_crude_vega, 'Explanation': 'Net vega to Crude after hedges.'},
        {'Risk_Factor': 'Total_Vega', 'Aggregated_Value': total_vega, 'Explanation': 'Net total vega after hedges.'},
        {'Risk_Factor': 'MSFT_Rho', 'Aggregated_Value': total_msft_rho, 'Explanation': 'Net rho for MSFT after hedges.'},
        {'Risk_Factor': 'Crude_Rho', 'Aggregated_Value': total_crude_rho, 'Explanation': 'Net rho for Crude after hedges.'},
        {'Risk_Factor': 'Total_Rho', 'Aggregated_Value': total_rho, 'Explanation': 'Net total rho after hedges.'},
        {'Risk_Factor': 'Total_Theta', 'Aggregated_Value': total_theta, 'Explanation': 'Net theta after hedges.'}
    ]

    aggregated_df = pd.DataFrame(aggregated_data)
    print("\nAggregated Risks Including Hedges with Explanations")
    print(tabulate(aggregated_df, headers='keys', tablefmt='psql'))

    return total_msft_delta, total_crude_delta, total_gold_delta, total_silver_delta, total_msft_gamma, total_crude_gamma, total_gamma, total_msft_vega, total_crude_vega, total_vega, total_msft_rho, total_crude_rho, total_rho, total_theta, aggregated_data

def concise_summary(initial_aggregated_df, after_aggregated_df, total_core_pnl, total_hedge_pnl):
    summary_data = []
    for i, row in initial_aggregated_df.iterrows():
        risk_factor = row['Risk_Factor']
        initial_value = row['Aggregated_Value']
        after_value = after_aggregated_df[after_aggregated_df['Risk_Factor'] == risk_factor]['Aggregated_Value'].values[0] if not after_aggregated_df[after_aggregated_df['Risk_Factor'] == risk_factor].empty else 0
        summary_data.append({'Risk_Factor': risk_factor, 'Initial_Value': initial_value, 'After_Hedges': after_value})

    summary_data.append({'Risk_Factor': 'Core_PnL', 'Initial_Value': total_core_pnl, 'After_Hedges': total_core_pnl})
    summary_data.append({'Risk_Factor': 'Hedge_PnL', 'Initial_Value': 0, 'After_Hedges': total_hedge_pnl})
    summary_data.append({'Risk_Factor': 'Net_PnL', 'Initial_Value': total_core_pnl, 'After_Hedges': total_core_pnl + total_hedge_pnl})

    summary_df = pd.DataFrame(summary_data)
    print("\nConcise Summary Table: Sensitivities and PnL Before/After Hedges")
    print(tabulate(summary_df, headers='keys', tablefmt='psql'))

    # Visualize PnL chart for hedging cost
    pnls = {'Core PnL': total_core_pnl, 'Hedge PnL': total_hedge_pnl, 'Net PnL': total_core_pnl + total_hedge_pnl}
    fig, ax = plt.subplots()
    ax.bar(pnls.keys(), pnls.values())
    ax.set_ylabel('PnL')
    ax.set_title('Hedging Cost Visualization')
    plt.show()  # Or save to file if needed: plt.savefig('hedging_cost_chart.png')

def main():
    parser = argparse.ArgumentParser(description="Trading Simulation Script")
    parser.add_argument('--mode', type=str, default='detailed', choices=['detailed', 'concise'], help='Mode: detailed or concise')
    args = parser.parse_args()
    mode = args.mode

    msft_data, gold_silver_data, crude_vertical_data, portfolio_df = define_instruments_and_portfolio()
    
    initial_market_df = print_initial_market_data(msft_data, gold_silver_data, crude_vertical_data)
    
    greeks_df, delta_msft, gamma_msft, theta_msft, vega_msft, rho_msft, spread_delta_gold, spread_delta_silver, spread_gamma, spread_theta, spread_vega, spread_rho, net_delta_crude, net_gamma_crude, net_theta_crude, net_vega_crude, net_rho_crude = calculate_greeks(msft_data, gold_silver_data, crude_vertical_data)
    
    portfolio_risks_df = calculate_portfolio_risks(portfolio_df, delta_msft, gamma_msft, theta_msft, vega_msft, rho_msft, spread_delta_gold, spread_delta_silver, spread_gamma, spread_theta, spread_vega, spread_rho, net_delta_crude, net_gamma_crude, net_theta_crude, net_vega_crude, net_rho_crude)
    
    initial_aggregated_df = pd.DataFrame(aggregate_risks(portfolio_risks_df)[-1])  # Get the aggregated_data from aggregate_risks

    total_msft_delta, total_crude_delta, total_gold_delta, total_silver_delta, total_msft_gamma, total_crude_gamma, total_gamma, total_msft_vega, total_crude_vega, total_vega, total_msft_rho, total_crude_rho, total_rho, total_theta, initial_aggregated_df = aggregate_risks(portfolio_risks_df)    
    
    delta_hedges_df = hedge_delta(total_msft_delta, total_crude_delta, total_gold_delta, total_silver_delta)
    
    gamma_hedges_df = hedge_gamma(total_msft_gamma, total_crude_gamma, msft_data, crude_vertical_data)
    
    theta_hedges_df = hedge_theta(total_theta, msft_data, crude_vertical_data)
    
    rho_hedges_df = hedge_rho(total_msft_rho, total_crude_rho, msft_data, crude_vertical_data)
    
    vega_hedges_df = hedge_vega(total_msft_vega, total_crude_vega, msft_data, crude_vertical_data)
    
    if mode == 'detailed':
        # Enhanced generate_hedge_trades usage with more demonstrations
        # Original calls
        generate_hedge_trades('delta', 'MSFT', total_msft_delta, msft_data['Expiry'], msft_data['Volatility'], msft_data['Current_Price'], msft_data['Risk_Free_Rate'])
        generate_hedge_trades('gamma', 'Crude', total_crude_gamma, crude_vertical_data['Expiry'], crude_vertical_data['Volatility'], crude_vertical_data['Current_Price'], crude_vertical_data['Risk_Free_Rate'])
        generate_hedge_trades('vega', 'MSFT', total_msft_vega, msft_data['Expiry'], msft_data['Volatility'], msft_data['Current_Price'], msft_data['Risk_Free_Rate'])
        generate_hedge_trades('theta', 'Crude', total_theta / 2, crude_vertical_data['Expiry'], crude_vertical_data['Volatility'], crude_vertical_data['Current_Price'], crude_vertical_data['Risk_Free_Rate'])  # Split theta
        generate_hedge_trades('rho', 'MSFT', total_msft_rho, msft_data['Expiry'], msft_data['Volatility'], msft_data['Current_Price'], msft_data['Risk_Free_Rate'])
        
        # Additional demonstrations for more trades (using actual or fictional exposures for Gold/Silver options hedging)
        generate_hedge_trades('delta', 'Gold', total_gold_delta, gold_silver_data['Expiry'], gold_silver_data['Volatility_Gold'], gold_silver_data['Gold_Price'], gold_silver_data['Risk_Free_Rate'])
        generate_hedge_trades('delta', 'Silver', total_silver_delta, gold_silver_data['Expiry'], gold_silver_data['Volatility_Silver'], gold_silver_data['Silver_Price'], gold_silver_data['Risk_Free_Rate'])
        generate_hedge_trades('gamma', 'MSFT', total_msft_gamma, msft_data['Expiry'], msft_data['Volatility'], msft_data['Current_Price'], msft_data['Risk_Free_Rate'])
        generate_hedge_trades('vega', 'Crude', total_crude_vega, crude_vertical_data['Expiry'], crude_vertical_data['Volatility'], crude_vertical_data['Current_Price'], crude_vertical_data['Risk_Free_Rate'])
        generate_hedge_trades('theta', 'MSFT', total_theta / 2, msft_data['Expiry'], msft_data['Volatility'], msft_data['Current_Price'], msft_data['Risk_Free_Rate'])
        generate_hedge_trades('rho', 'Crude', total_crude_rho, crude_vertical_data['Expiry'], crude_vertical_data['Volatility'], crude_vertical_data['Current_Price'], crude_vertical_data['Risk_Free_Rate'])
        # Fictional exposures for Gold/Silver gamma/vega/theta demos (since futures have 0, but demonstrating option hedges)
        generate_hedge_trades('gamma', 'Gold', 0.05, gold_silver_data['Expiry'], gold_silver_data['Volatility_Gold'], gold_silver_data['Gold_Price'], gold_silver_data['Risk_Free_Rate'])  # Fictional gamma
        generate_hedge_trades('vega', 'Gold', 10.0, gold_silver_data['Expiry'], gold_silver_data['Volatility_Gold'], gold_silver_data['Gold_Price'], gold_silver_data['Risk_Free_Rate'])  # Fictional vega
        generate_hedge_trades('theta', 'Gold', -5.0, gold_silver_data['Expiry'], gold_silver_data['Volatility_Gold'], gold_silver_data['Gold_Price'], gold_silver_data['Risk_Free_Rate'])  # Fictional theta
        generate_hedge_trades('gamma', 'Silver', 0.07, gold_silver_data['Expiry'], gold_silver_data['Volatility_Silver'], gold_silver_data['Silver_Price'], gold_silver_data['Risk_Free_Rate'])  # Fictional
        generate_hedge_trades('vega', 'Silver', 15.0, gold_silver_data['Expiry'], gold_silver_data['Volatility_Silver'], gold_silver_data['Silver_Price'], gold_silver_data['Risk_Free_Rate'])
        generate_hedge_trades('theta', 'Silver', -7.0, gold_silver_data['Expiry'], gold_silver_data['Volatility_Silver'], gold_silver_data['Silver_Price'], gold_silver_data['Risk_Free_Rate'])
        generate_hedge_trades('rho', 'Gold', 2.0, gold_silver_data['Expiry'], gold_silver_data['Volatility_Gold'], gold_silver_data['Gold_Price'], gold_silver_data['Risk_Free_Rate'])  # Fictional rho
        generate_hedge_trades('rho', 'Silver', 3.0, gold_silver_data['Expiry'], gold_silver_data['Volatility_Silver'], gold_silver_data['Silver_Price'], gold_silver_data['Risk_Free_Rate'])

    pnl_df, pnl_msft, pnl_spread, pnl_crude, new_msft_price, new_gold_price, new_silver_price, new_crude_price, total_core_pnl, total_hedge_pnl = simulate_market_change_and_pnl(portfolio_df, msft_data, gold_silver_data, crude_vertical_data, delta_msft, gamma_msft, theta_msft, vega_msft, rho_msft, net_delta_crude, net_gamma_crude, net_theta_crude, net_vega_crude, net_rho_crude, total_msft_delta, total_crude_delta, total_gold_delta, total_silver_delta, total_msft_gamma, total_crude_gamma, total_msft_vega, total_crude_vega, total_msft_rho, total_crude_rho, total_theta)
    
    close_df, total_pnl = close_trades(portfolio_df, pnl_msft, pnl_spread, pnl_crude, new_msft_price, new_gold_price, new_silver_price, new_crude_price)

    after_aggregated_df = pd.DataFrame(final_aggregated_risk_table_including_hedges(portfolio_risks_df, delta_hedges_df, gamma_hedges_df, vega_hedges_df, theta_hedges_df, rho_hedges_df, msft_data, gold_silver_data, crude_vertical_data, total_core_pnl, total_hedge_pnl)[-1])  # Get aggregated_data from function

    if mode == 'concise':
        concise_summary(initial_aggregated_df, after_aggregated_df, total_core_pnl, total_hedge_pnl)

if __name__ == "__main__":
    main()

# Note: For a $200K portfolio, this is realistic for retail traders using brokers like Interactive Brokers or ThinkOrSwim, which provide Greeks and risk analytics. Track daily via scripts or broker tools. Hedging reduces risk but adds costs; start with delta, then higher Greeks if needed.
