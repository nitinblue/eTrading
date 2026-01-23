# trading_bot/trades.py
from decimal import Decimal
from trading_bot.order_model import UniversalOrder, OrderLeg, OrderAction, PriceEffect, OrderType
from trading_bot.trade_execution import TradeExecutor
from tastytrade.instruments import get_option_chain
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def sell_otm_put(execution_broker, underlying: str = "AAPL", dte: int = 46, delta_target: float = -0.16, quantity: int = 1, dry_run: bool = False):
    """Hard-coded sell of AAPL Feb 20 2026 $110 Put."""  
    logger.info(f"BOOKING: Selling put {underlying} | Qty: {quantity} | Dry Run: {dry_run}")   
    chain = get_option_chain(execution_broker.session, underlying)  
    today = datetime.now().date()
    target_date = today + timedelta(days=dte)  
    strikes = [110.0, 105.0, 100.0]  # Hard-coded strikes for butterfly
    print(f"{target_date} expiry")
    if target_date not in chain:
        print(f"No {target_date} expiry")
        return None
    
    options = chain[target_date]
    
    # Find legs
    wing1_put = next((o for o in options if float(o.strike_price) == strikes[0] and o.option_type == "P"), None)
    body_put = next((o for o in options if float(o.strike_price) == strikes[1] and o.option_type == "P"), None)
    wing2_put = next((o for o in options if float(o.strike_price) == strikes[2] and o.option_type == "P"), None)
          
    tt_legs=[wing1_put.build_leg(Decimal(quantity), OrderAction.SELL_TO_OPEN),]  
    order = UniversalOrder(
        legs=tt_legs,
        price_effect=PriceEffect.CREDIT,
        order_type=OrderType.LIMIT,
        limit_price=1.50,
        time_in_force="DAY",
        dry_run=dry_run
    )

    executor = TradeExecutor(execution_broker)
    result = executor.execute("Hardcoded Put Sell", order)
    logger.info(f"Result: {result}")
    return result

def buy_atm_leap_call(execution_broker, underlying: str = "MSFT", dte: int = 365, delta_target: float = 0.50, quantity: int = 1, dry_run: bool = False):
    """Hard-coded buy of MSFT Sep 18 2026 $470 Call."""
    symbol = "MSFT  260918C00470000"
    logger.info(f"BOOKING: Buying LEAP call {symbol} | Qty: {quantity} | Dry Run: {dry_run}")

    legs = [OrderLeg(symbol=symbol, quantity=quantity, action=OrderAction.BUY_TO_OPEN)]

    order = UniversalOrder(
        legs=legs,
        price_effect=PriceEffect.DEBIT,
        order_type=OrderType.LIMIT,
        limit_price=60.00,  # Adjust based on current price
        time_in_force="DAY",
        dry_run=dry_run
    )

    executor = TradeExecutor(execution_broker)
    result = executor.execute("Hardcoded LEAP Call Buy", order)
    logger.info(f"Result: {result}")
    return result

def sell_otm_put_actual(execution_broker, underlying: str = "MSFT", dte: int = 45, delta_target: float = -0.16, quantity: int = 1, dry_run=True):
    # HARD-CODED FOR TESTING
    hardcoded_put = ".MSFT260918P00470000"  # Sep 18 2026 $470 Put
    logger.info(f"Using hard-coded put {hardcoded_put} & Dry Run : {dry_run}")
    
    return {"status": "test", "symbol": hardcoded_put}

    """Sell slightly OTM put (~45 DTE)."""
    chain = market_data.get_option_chain(underlying)
    target_date = datetime.now().date() + timedelta(days=dte)
    expiries = sorted(chain.keys())
    selected_expiry = min(expiries, key=lambda d: abs((d - target_date).days))

    puts = [o for o in chain[selected_expiry] if o.option_type == 'put']
    if not puts:
        logger.warning(f"No puts found for {underlying} on {selected_expiry}")
        return

    puts = sorted(puts, key=lambda x: x.greeks.delta if x.greeks else 0)
    put = min(puts, key=lambda x: abs((x.greeks.delta if x.greeks else 0) - delta_target))

    logger.info(f"Selling OTM put: {put.symbol} | Strike: {put.strike_price} | Delta: {put.greeks.delta:.3f if put.greeks else 'N/A'}")

    legs = [OrderLeg(symbol=put.symbol, quantity=quantity, action=OrderAction.SELL_TO_OPEN)]

    order = UniversalOrder(
        legs=legs,
        price_effect=PriceEffect.CREDIT,
        order_type=OrderType.LIMIT,
        limit_price=put.mid_price * 0.9 if hasattr(put, 'mid_price') else 0.0,
        time_in_force="DAY",
        dry_run=dry_run
    )

    executor = TradeExecutor(execution_broker)
    result = executor.execute(f"{underlying} OTM Put Sell", order)
    logger.info(f"Result: {result}")
    return result

def buy_atm_leap_call_actual(execution_broker, underlying: str = "MSFT", dte: int = 365, delta_target: float = 0.50, quantity: int = 1, dry_run: bool = True):
    # HARD-CODED FOR TESTING
    hardcoded_call = ".MSFT260918C00470000"  # Sep 18 2026 $470 Call (ATM)
    logger.info(f"TESTING: Using hard-coded LEAP call {hardcoded_call} & Dry Run : {dry_run}")
    return {"status": "test", "symbol": hardcoded_call}

    """Buy ATM LEAP call (~1 year)."""
    chain = market_data.get_option_chain(underlying)
    target_date = datetime.now().date() + timedelta(days=dte)
    expiries = sorted(chain.keys())
    selected_expiry = min(expiries, key=lambda d: abs((d - target_date).days))

    calls = [o for o in chain[selected_expiry] if o.option_type == 'call']
    if not calls:
        logger.warning(f"No calls found for {underlying} on {selected_expiry}")
        return

    calls = sorted(calls, key=lambda x: x.greeks.delta if x.greeks else 0)
    call = min(calls, key=lambda x: abs((x.greeks.delta if x.greeks else 0.5) - delta_target))

    logger.info(f"Buying ATM LEAP call: {call.symbol} | Strike: {call.strike_price} | Delta: {call.greeks.delta:.3f if call.greeks else 'N/A'}")

    legs = [OrderLeg(symbol=call.symbol, quantity=quantity, action=OrderAction.BUY_TO_OPEN)]

    order = UniversalOrder(
        legs=legs,
        price_effect=PriceEffect.DEBIT,
        order_type=OrderType.LIMIT,
        limit_price=call.mid_price * 1.1 if hasattr(call, 'mid_price') else 0.0,
        time_in_force="DAY",
        dry_run=dry_run
    )

    executor = TradeExecutor(execution_broker)
    result = executor.execute(f"{underlying} ATM LEAP Call Buy", order)
    logger.info(f"Result: {result}")
    return result

# Add more templates here later (iron condor, butterfly, wheel entry, etc.)
def book_butterfly(session,preview, underlying: str, quantity: int = 1,max_debit: float = 1.00):
    """
    SUBMIT live paper order (use with caution!)
    """        
    logger.info(f"Booking butterfly for {underlying}")
  
    legs = [
        preview[0].build_leg(Decimal(quantity), OrderAction.BUY_TO_OPEN),    # Wing 1
        preview[1].build_leg(Decimal(quantity * 2), OrderAction.SELL_TO_OPEN),  # Body 2x
        preview[2].build_leg(Decimal(quantity), OrderAction.BUY_TO_OPEN),    # Wing 2
    ]
    order =UniversalOrder(
        legs=legs,
        price_effect=PriceEffect.DEBIT,
        order_type=OrderType.LIMIT,
        limit_price=max_debit,
        time_in_force="DAY",
        dry_run=False
    )
    executor = TradeExecutor(session)
    result = executor.execute(f"{underlying} Butterfly", order)
    logger.info(f"Result: {result}")
    return result