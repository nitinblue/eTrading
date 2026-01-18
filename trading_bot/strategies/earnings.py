'''
January 11, 2026 Options trading classes

Earnings Strategies

Completely directionless
hold the trade overnight

- How to pick stocks
strategy seelction
modeling trade set up
Execution - entry and exit

Stock selection
Implied voltatility > realised volatility
clear and consistent pattern on price action
have a historic win rate of 70% or above.
    expected move on stock is 5.. but historic move is 2. means have an edge.
    
Strategy selection
if stock consistently goes higher
- sell 20 to 30 delta

MOMO earnings tool
expected move vs actual move

Neutral strategies - sell an iron

get credit atleast 1/3 of the width of the spread.. return on risk >= 33%.. credit on citi is 73 for below
200/73 --> 114,    ,        128
# trading_bot/strategies/earnings.py
"""             116, 126

Bank of america Earnings Strategy Examples .. 1% risk per trade of the total capital... position size is important

P 52.5                             C 58.5.  
       P 53.5              C 57.5
       credit 36.5.... win % 57%

To optimize for higher probability of profit, consider the following adjustments:
increase the spread. Increses chance of profit, but reduces credit. and max loss is more

Another way, is to sell iron fly

OPen earnings trade a day before just before market close earnings.. close it immediately after opening the next day
JPM (329 current price) .. in this chance of profit at least 50%, and credit should be higher than max loss

P 310                          C 350
        P 330               C 330
        credit 1058... win % 50%        
'''


'''
Earnings breakout strategy
if stock moves outside the epected move range after earnings, either skip trade.. or buy an iron fly or iron condor
Not suggested by Ravish at all, to do any trade.. .. Because in this case IV crush is going to go against you.


Now iron condor is better or iron fly is better?
if stock tends to stay in the middle, then iron fly will be better otherwise iron condor is better.
Iron condor will give more consistent results.
- open trade between 3:30 and 4
- only trades where you have a clear edge
- make multiple trades in a week
- you will win most and lose some
- this will give you a positive pnl over a period of time



'''

'''
cash secured puts..
We see that more number of times stocks open up after earnings than down.
So instead of buying call options, we can CSP
what was the highest stock went after open, 


Citi, Short put. IV crush will help us.

If cash secured, then return is 2.2 percent in one day.. If naked put sell, then return is 11% percent in one day.

instead of selling atm, sell 30 delta put credit spread.
1% on CSP, 11% on naked put sell.

you can also check what does the stock do a day after earnings.. if it tends to go up, then selling put credit spread is better.

You can also look at selling leveraged etfs puts.. like TQQQ, SOXL etc..


You call also go for Bull Put Spreads instead of cash secured puts.

very lucrative, very captical efficient strategy., high win rate strategy.. will benefit from IV crush as well.

OVerall earnings strategies, generally go with iron condor. for bearish stocks, go with CSP.. or bull put spreads.
'''

'''
Pre earnings strategy:

for stocks generally who are high 7 or 14 days before the earnings, go for BUll credit spreads
this is still 2 weeks out.
Buy call first that is 30 delta
then sell a put 2 to 5 point wide..

JPM is at 329
buy call 337.5, sell call 342.5
debit trade.. 154
max loss 122


so when playing earnings, to hedge broader market extreme moves you can have mix of bearish and bullish strategies.

TEsla does sales earnings couple of weeks berfore earnings.. it generally goes up... 

Unsual whales platform
''''''
