# trading_bot/utils/trade_utils.py
from tabulate import tabulate
from datetime import datetime, timedelta
from tastytrade.market_data import get_market_data_by_type
from tastytrade.instruments import get_option_chain
from tastytrade.instruments import Equity
from trading_bot.order_model import UniversalOrder, OrderLeg, OrderAction, PriceEffect, OrderType
from trading_bot.trade_execution import TradeExecutor
import logging

logger = logging.getLogger(__name__)

def print_option_chain(underlying: str, broker_session):
    """
    Print ATM option chain (4 strikes below + ATM + 4 above)
    """
    # Get chain + underlying price
    chain = get_option_chain(broker_session, underlying)
    equity = get_market_data_by_type(broker_session, equities=underlying)
    logger.info(f"Equity data: {equity}")
    underlying_price = float(equity[0].last) if equity else 420.0
    
    # Pick expiry closest to 14 DTE
    today = datetime.now().date()
    expiries = []
    for exp_date, options in chain.items():
        dte = (exp_date - today).days
        if dte >= 0 and options:
            expiries.append((exp_date, dte, options))

    if not expiries:
        logger.warning("No valid expiries with options")
        return

    selected_exp, dte, options = min(expiries, key=lambda x: abs(x[1] - 14))
    logger.info(f"Selected expiry {selected_exp} (DTE {dte}) | Spot: ${underlying_price:.1f}")

    # Calls/Puts
    calls = [o for o in options if o.option_type == "C"]
    puts = [o for o in options if o.option_type == "P"]
    all_strikes = sorted(set(float(o.strike_price) for o in calls + puts))
    
    # 🎯 4 below + ATM + 4 above
    atm_index = min(range(len(all_strikes)), key=lambda i: abs(all_strikes[i] - underlying_price))
    atm_strike = all_strikes[atm_index]
    start_idx = max(0, atm_index - 4)
    end_idx = min(len(all_strikes), atm_index + 5)
    selected_strikes = all_strikes[start_idx:end_idx]
    
    logger.info(f"ATM: ${atm_strike:.1f} | Strikes: {[f'${s:.1f}' for s in selected_strikes]}")

    # 🚀 Symbols for SELECTED STRIKES ONLY
    call_symbols = [c.symbol.strip() for c in calls if float(c.strike_price) in selected_strikes]
    put_symbols = [p.symbol.strip() for p in puts if float(p.strike_price) in selected_strikes]
    all_selected_symbols = list(set(call_symbols + put_symbols))
    
    logger.info(f"Fetching quotes for {len(all_selected_symbols)} symbols: {all_selected_symbols[:3]}...")

    # Get quotes
    quotes_list = get_market_data_by_type(broker_session, options=all_selected_symbols)
    quotes = {q.symbol.strip(): q for q in quotes_list}
    logger.info(f"Quotes matched: {len(quotes_list)}/{len(all_selected_symbols)}")

    # Table
    headers = ["Symbol","Call Bid", "Call Ask", "Call Δ", "Strike", "Put Bid", "Put Ask", "Put Δ"]
    rows = []

    for strike in selected_strikes:
        call = next((c for c in calls if float(c.strike_price) == strike), None)
        put = next((p for p in puts if float(p.strike_price) == strike), None)
        
        call_sym = call.symbol.strip() if call else None
        put_sym = put.symbol.strip() if put else None
        
        call_q = quotes.get(call_sym) if call_sym else None
        put_q = quotes.get(put_sym) if put_sym else None
        
        logger.debug(f"${strike:.1f}: C={call_sym}={call_q is not None}, P={put_sym}={put_q is not None}")
        # logger.info(f"call_q:{call_q}, put_q:{put_q}")
        
        row = [
            f"{call_sym if call else '---'}",
            f"{float(call_q.bid):.2f}" if call_q and call_q.bid else "—",
            f"{float(call_q.ask):.2f}" if call_q and call_q.ask else "—",            
            f"{getattr(call_q, 'delta', 0):.3f}" if call_q else "—",
            f"${strike:.1f}",           
            f"{float(put_q.bid):.2f}" if put_q and put_q.bid else "—",
            f"{float(put_q.ask):.2f}" if put_q and put_q.ask else "—",
            f"{getattr(put_q, 'delta', 0):.3f}" if put_q else "—",
        ]
        rows.append(row)

    # Print
    table = tabulate(rows, headers=headers, tablefmt="grid")
    print(f"\n{underlying.upper()} | Exp: {selected_exp} | DTE: {dte} | Spot: ${underlying_price:.1f}")
    print(table)
    
    # Butterfly suggestion
    if len(selected_strikes) >= 5:
        body_idx = len(selected_strikes) // 2
        butterfly = selected_strikes[body_idx-1:body_idx+2]
        print(f"\n💎 Suggested Butterfly: {'/'.join([f'${s:.0f}' for s in butterfly])}P")



logger = logging.getLogger(__name__)

def sell_otm_put(underlying: str, broker_session, dte: int = 45, delta_target: float = -0.16, quantity: int = 1, dry_run: bool = True):
    """Sell a slightly OTM put at ~45 DTE."""
    chain = get_option_chain(broker_session, underlying)
    target_date = datetime.now().date() + timedelta(days=dte)
    expiries = sorted(chain.keys())
    
    # Find expiry with puts
    selected_expiry = None
    for exp in expiries:
        puts = [o for o in chain[exp] if o.option_type == 'put']
        if puts:
            selected_expiry = exp
            break
    
    if not selected_expiry:
        logger.warning(f"No expiry with put options for {underlying}")
        return {"status": "failed", "reason": "no_puts"}

    logger.info(f"Using expiry with puts: {selected_expiry} (DTE: {(selected_expiry - datetime.now().date()).days})")

    puts = sorted(puts, key=lambda x: x.greeks.delta if x.greeks else 0)

    if not puts:
        logger.warning("No puts found")
        return {"status": "failed", "reason": "no_puts"}

    # Find closest to delta_target
    put = min(puts, key=lambda x: abs((x.greeks.delta if x.greeks else 0) - delta_target))

    logger.info(f"Selling OTM put: {put.symbol} | Strike: {put.strike_price} | Delta: {put.greeks.delta if put.greeks else 'N/A'}")

    legs = [OrderLeg(symbol=put.symbol, quantity=quantity, action=OrderAction.SELL_TO_OPEN)]

    order = UniversalOrder(
        legs=legs,
        price_effect=PriceEffect.CREDIT,
        order_type=OrderType.LIMIT,
        limit_price=put.mid_price * 0.9 if hasattr(put, 'mid_price') else 0.0,
        time_in_force="DAY",
        dry_run=dry_run
    )

    executor = TradeExecutor(broker_session)
    result = executor.execute(f"{underlying} OTM Put Sell", order)
    logger.info(f"Sell Put Result: {result}")
    return result

def buy_atm_leap_call(underlying: str, broker_session, dte: int = 365, delta_target: float = 0.50, quantity: int = 1, dry_run: bool = True):
    """Buy ATM LEAP call at ~1 year DTE."""
    chain = get_option_chain(broker_session, underlying)
    target_date = datetime.now().date() + timedelta(days=dte)
    expiries = sorted(chain.keys())
    
    # Find expiry with calls
    selected_expiry = None
    for exp in expiries:
        calls = [o for o in chain[exp] if o.option_type == 'call']
        if calls:
            selected_expiry = exp
            break
    
    if not selected_expiry:
        logger.warning(f"No expiry with call options for {underlying}")
        return {"status": "failed", "reason": "no_calls"}

    logger.info(f"Using furthest expiry with calls: {selected_expiry} (DTE: {(selected_expiry - datetime.now().date()).days})")

    calls = sorted(calls, key=lambda x: x.greeks.delta if x.greeks else 0)

    if not calls:
        logger.warning("No calls found")
        return {"status": "failed", "reason": "no_calls"}

    # Find closest to delta_target
    call = min(calls, key=lambda x: abs((x.greeks.delta if x.greeks else 0.5) - delta_target))

    logger.info(f"Buying LEAP call: {call.symbol} | Strike: {call.strike_price} | Delta: {call.greeks.delta if call.greeks else 'N/A'}")

    legs = [OrderLeg(symbol=call.symbol, quantity=quantity, action=OrderAction.BUY_TO_OPEN)]

    order = UniversalOrder(
        legs=legs,
        price_effect=PriceEffect.DEBIT,
        order_type=OrderType.LIMIT,
        limit_price=call.mid_price * 1.1 if hasattr(call, 'mid_price') else 0.0,
        time_in_force="DAY",
        dry_run=dry_run
    )

    executor = TradeExecutor(broker_session)
    result = executor.execute(f"{underlying} ATM LEAP Call Buy", order)
    logger.info(f"Buy LEAP Call Result: {result}")
    return result