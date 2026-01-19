
'''
"""Double Calendar Spread Strategy Module.

Sell Put short date
Buy put long date
Sell Call short date
Buy Call long date

You pick dates more that delta etc, you choose date and days combination based on vix levels

best combinartions are, check IV and expected move, in option chain.. this is called volatility term structure
THis is all about volatility term structure.. Option chain

# sell call and put for monday.. buy call and put for friday
Wednesday / Friday
Thursday / Friday
Friday /Monday
Friday / Friday

start with 20 delta
lower win rate during holiday weeks, seasonality has big impact on this strategy
Avoid november to December period
when vix goes low, you lose money on this strategy
when vix goes high, you make money on this strategy

check .vix chart..

stricke is same for put buy and call, same for call buy and call sell
Optionstrat will tell you will always lose money, not able to model this strategy, 
because these apps do not handle volatility term structure well.

we want the vix to go up
premium for our short leg should decay fast.

so we want iv to go up for 

contango (normal ) & backwardation
vix furues slopes up
short term iv cheaper than long term iv

vixcentral.com

when market is panic mode, backwardation happens, vix in short term is higher than long term

Backwardation is good for double calendar spread strategy
which means short term iv is now going to go down in near future (normal circumstances)

DC strategy works best on SPX.. (similar can work for spy and QQQ but Ravish has no experience 
with this.. this is totally vix term structure based, means what all expiries are 
even available.. SPX is cash settled lot of brokers dont allow spx double calendar)

Short/Long Ratio
perimum of short premium/long premium

S/L ratio should be more than 40%, preferably above 50%.. 

Strategy 2
Double Diagonal, dates are different and strikes are different

red sag between the 2 tents is not there.

Decreasing volatility has lesser negative impact.

on SPX wing should be 10 width.. or little bit more upto 25

$1 to 3 for SPY or QQQ

# Mechanical set up for trading double calendar and double diagonal calendar

SPX DC 14/17 .. Friday/Monday set up. delta is 20 for all... Trade at 1:30 PM on friday .. 
skip holiday week.
Entry when vix is 15 to 25.. if above 20 dont do, because vix tends to come
if vix below 15 overall trade will underperform
win percent 87.5% ..Profit target 25%.. . 
On the day of expiration close trade by 2 PM if profit trade not hit..

Allocate 10% of your total capital for this stratgy to this strategy.. Ravish has a seperate acccount of this..

SPX DC 6/7
Thursday/Friday combination.. no entry crieteria for Vix.. if vix goes up 
strategy will perform, but if goes down less impact..
20 delta.. 
This has higher gamma, so very sensitive to price change of SPX.. most of
the time price will land in the center, but still return is better for this 
short term set up.. Profit target is 70% target.. MAR Ratio is better here.

You can combine 1
'''

from tokenize import Double
from matplotlib.table import table


from matplotlib import table

# print

