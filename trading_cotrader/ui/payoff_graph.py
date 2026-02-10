import opstrat as op
from tabulate import tabulate


# 1. Define your trade details (Example: Bull Call Spread)
# You would replace these with data from your app's user input
trade_details = [
    {'op_type': 'c', 'strike': 100, 'tr_type': 'b', 'op_pr': 5},  # Long Call
    {'op_type': 'c', 'strike': 110, 'tr_type': 's', 'op_pr': 2}   # Short Call
]

# 2. Generate the payoff graph
# This function creates a Matplotlib plot and calculates P&L automatically
op.multi_plotter(spot=105, spot_range=20, op_list=trade_details)

# 3. Accessing calculated P&L data for your table
# Libraries like 'profitnloss' can also be used for raw numeric extraction
# Max Profit: (110 - 100) - (5 - 2) = 7
# Max Loss: (5 - 2) = 3


# Full set of 14 key strategies with safety-focused entry criteria
options_data = [
    # BULLISH STRATEGIES
    ["Long Call", "Bullish", "Unlimited", "Net Debit", "__/", "IVR < 20, RSI < 30", "Low IV prevents overpaying for 'theta'"],
    ["Bull Put Spread", "Bullish", "Net Credit", "Width - Cr", "__/￣", "IVR > 40, RSI 35-45", "Defined risk with high probability"],
    ["Cash-Secured Put", "Bullish", "Net Credit", "Strike - Cr", "__/", "IVR > 30, RSI < 40", "Protects against small price drops"],
    
    # BEARISH STRATEGIES
    ["Long Put", "Bearish", "K - Debit", "Net Debit", "\\__", "IVR < 20, RSI > 70", "Cheap premium for downside protection"],
    ["Bear Call Spread", "Bearish", "Net Credit", "Width - Cr", "￣\\__", "IVR > 40, RSI 60-65", "Profit if stock stays flat or drops"],
    
    # NEUTRAL / RANGE-BOUND
    ["Iron Condor", "Neutral", "Net Credit", "Width - Cr", "__/￣\\__", "IVR > 50, RSI 45-55", "Wide wings allow for error margin"],
    ["Iron Butterfly", "Neutral", "Net Credit", "Width - Cr", "_/\\_", "IVR > 70, RSI ~50", "High credit offsets risk of pin"],
    ["Covered Call", "Neutral/Bull", "K-S0 + Cr", "S0 - Cr", "--/￣", "IVR > 20, RSI ~50", "Stock ownership buffers the option"],
    
    # VOLATILITY / CALENDAR (SAFETY-FOCUSED)
    ["Calendar Spread", "Neutral/Vol", "Variable", "Net Debit", "_/\\_", "IVR < 15, VIX < 16", "Buying low vol before expansion"],
    ["Double Calendar", "Neutral/Vol", "Variable", "Net Debit", "_/\\_/\\_", "IVR < 20, VIX < 18", "Wider profit zone than single calendar"],
    ["Diagonal Spread", "Trend + Vol", "Variable", "Net Debit", "_/￣", "IVR < 25, RSI ~45", "Uses time decay to subsidize a trend"],
    
    # ADVANCED / VOLATILITY
    ["Long Straddle", "High Vol", "Unlimited", "Net Debit", "\\ /", "IVR < 10, Pre-Event", "Cheap 'lottery' for huge moves"],
    ["Long Strangle", "High Vol", "Unlimited", "Net Debit", "\\___/", "IVR < 10, Pre-Event", "Cheaper entry than straddle"],
    ["Ratio Put Spread", "Neutral/Bull", "Variable", "Net Credit*", "__/ \\_", "IVR > 50, RSI < 40", "Can result in zero cost if right strike"]
]

headers = [
    "Strategy", 
    "Outlook", 
    "Max Profit", 
    "Max Loss", 
    "Payoff", 
    "Conservative Entry (IVR/RSI)", 
    "Safety Reasoning"
]

# Print using grid format for best readability in terminal/apps
print(tabulate(options_data, headers=headers, tablefmt="grid"))
