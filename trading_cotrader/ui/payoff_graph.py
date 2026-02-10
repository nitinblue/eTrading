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


# Define the strategy data
# Format: [Strategy, Market Outlook, Max Profit, Max Loss, Payoff Graph]
options_cheatsheet = [
    ["Long Call", "Bullish", "Unlimited", "Net Debit", "__/"],
    ["Long Put", "Bearish", "Strike - Net Debit", "Net Debit", "\\__"],
    ["Covered Call", "Neutral/Bullish", "Net Credit + (K - S0)", "S0 - Net Credit", "--/￣"],
    ["Bull Call Spread", "Modestly Bullish", "Width - Net Debit", "Net Debit", "__/￣"],
    ["Bear Put Spread", "Modestly Bearish", "Width - Net Debit", "Net Debit", "￣\\__"],
    ["Long Straddle", "High Volatility", "Unlimited", "Net Debit", "\\ /"],
    ["Short Straddle", "Low Volatility", "Net Credit", "Unlimited", "/ \\"],
    ["Iron Condor", "Rangebound", "Net Credit", "Width - Net Credit", "__/￣\\__"],
    ["Long Butterfly", "Target Price", "Width - Net Debit", "Net Debit", "_/\\_"]
]

headers = ["Strategy", "Market Outlook", "Max Profit", "Max Loss", "Payoff (Visual)"]

# Generate the table using 'grid' format for a clean look
print(tabulate(options_cheatsheet, headers=headers, tablefmt="grid"))