# trading_bot/utils/trade_utils.py
from datetime import date, datetime, timedelta
from tastytrade.instruments import get_option_chain
from tastytrade.market_data import get_market_data
from trading_bot.order_model import UniversalOrder, OrderLeg, OrderAction, PriceEffect, OrderType
from trading_bot.trade_execution import TradeExecutor
from tabulate import tabulate
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

TARGET_EXP = date(2026, 1, 30)   # 30-01-2026

def book_butterfly(underlying: str, broker_session, quantity: int = 1, limit_credit: float = 2.50, dry_run: bool = True):
    """
    Book a call butterfly on the given underlying.
    Selects an expiry with available call options (prefers ~45 DTE).
    """
    try:
        chain = get_option_chain(broker_session, underlying)
        logger.info(f"Option chain fetched for {underlying}: {len(chain)} expiries available")
        
        if not chain:
            raise ValueError(f"No option chain data for {underlying}")

        # Find expiries with at least 3 call options
        valid_expiries = []
        for exp, opts in chain.items():
            calls = [o for o in opts if o.option_type == 'call']
            if len(calls) >= 3:
                valid_expiries.append((exp, calls))

        if not valid_expiries:
            raise ValueError(f"No expiry with sufficient call options for {underlying}")

        # Prefer ~45 DTE
        target_date = datetime.now().date() + timedelta(days=4)
        selected_exp, calls = min(valid_expiries, key=lambda x: abs((x[0] - target_date).days))
        
        dte = (selected_exp - datetime.now().date()).days
        logger.info(f"Selected expiry: {selected_exp} (DTE: {dte} days, {len(calls)} calls available)")

        calls = sorted(calls, key=lambda x: x.strike_price)
        logger.info(f"Call strikes range: {calls[0].strike_price} - {calls[-1].strike_price}")

        # Get approximate underlying price for ATM centering
        try:
            from tastytrade.dxfeed.quote import Quote
            quote = Quote.get_quote(broker_session, underlying)
            underlying_price = quote.get('last_price') or quote.get('close_price')
            logger.info(f"{underlying} current price: ${underlying_price:.2f}")
        except Exception as e:
            logger.warning(f"Underlying price fetch failed: {e} — using middle strike")
            underlying_price = calls[len(calls)//2].strike_price

        # Find ATM strike
        atm_strike = min(calls, key=lambda x: abs(x.strike_price - underlying_price)).strike_price
        atm_index = next(i for i, c in enumerate(calls) if c.strike_price == atm_strike)

        # Build wings
        lower_index = max(0, atm_index - 1)
        higher_index = min(len(calls) - 1, atm_index + 1)

        lower = calls[lower_index]
        middle = calls[atm_index]
        higher = calls[higher_index]

        logger.info(f"Building {underlying} Call Butterfly:")
        logger.info(f"  Buy  {quantity} x {lower.strike_price} ({lower.symbol})")
        logger.info(f"  Sell {quantity*2} x {middle.strike_price} ({middle.symbol})")
        logger.info(f"  Buy  {quantity} x {higher.strike_price} ({higher.symbol})")
        logger.info(f"  Target credit: ${limit_credit:.2f}")

        legs = [
            OrderLeg(symbol=lower.symbol, quantity=quantity, action=OrderAction.BUY_TO_OPEN),
            OrderLeg(symbol=middle.symbol, quantity=quantity * 2, action=OrderAction.SELL_TO_OPEN),
            OrderLeg(symbol=higher.symbol, quantity=quantity, action=OrderAction.BUY_TO_OPEN),
        ]

        order = UniversalOrder(
            legs=legs,
            price_effect=PriceEffect.CREDIT,
            order_type=OrderType.LIMIT,
            limit_price=limit_credit,
            time_in_force="DAY",
            dry_run=dry_run
        )

        executor = TradeExecutor(broker_session)
        result = executor.execute(f"{underlying} Butterfly", order)
        logger.info(f"{underlying} Butterfly Order Result: {result}")
        return result

    except Exception as e:
        logger.error(f"Failed to book butterfly for {underlying}: {e}")
        raise
    



logger = logging.getLogger(__name__)

def print_option_chain(underlying: str, broker_session):
    """
    Fetch and print the option chain in a clean tabular format.
    Handles quote access correctly via .get_quote().
    """
    try:
        chain = get_option_chain(broker_session, underlying)
        logger.info(f"Option chain fetched for {underlying}: {len(chain)} expiries available")
        
        if not chain:
            raise ValueError(f"No option chain data for {underlying}")
        
         # Safety check
        if TARGET_EXP not in chain:
            print(f"No options for {TARGET_EXP} in chain for {underlying}")
            print("Available expiries:", list(chain.keys()))
            return

        opts = chain[TARGET_EXP]
        print(f"\n{TARGET_EXP}: {len(opts)} options")
        option_symbols = []

        for exp in chain.items():
            for strike in exp.strikes:
                if strike.call:
                    option_symbols.append(strike.call.symbol)
                if strike.put:
                    option_symbols.append(strike.put.symbol)
            quotes = get_market_data(broker_session, option_symbols)
        for sym, q in quotes.items():
         print(sym, q.bid, q.ask, q.last)
    
        all_options = []
        for exp, opts in chain.items():
            for opt in opts:
                # Get quote data
                try:
                    quote = opt.get_quote(broker_session)                   
                    bid = quote.bid_price or 0.0
                    ask = quote.ask_price or 0.0
                    last = quote.last_price or 0.0
                except:
                    bid = ask = last = 0.0  # Fallback if quote not available

                greeks = opt.greeks if hasattr(opt, 'greeks') and opt.greeks else None
                all_options.append({
                    'Expiry': exp,  # Already date
                    'Symbol': opt.symbol,
                    'Type': opt.option_type.capitalize(),
                    'Strike': opt.strike_price,
                    'Bid': bid,
                    'Ask': ask,
                    'Last': last,
                    'Delta': greeks.delta if greeks else 'N/A',
                    'Gamma': greeks.gamma if greeks else 'N/A',
                    'Theta': greeks.theta if greeks else 'N/A',
                    'Vega': greeks.vega if greeks else 'N/A',
                    'Rho': greeks.rho if greeks else 'N/A',
                    'IV': f"{(greeks.implied_volatility * 100 if greeks and greeks.implied_volatility else 0):.1f}%"
                })

        if not all_options:
            raise ValueError(f"No options found in chain for {underlying}")

        all_options = sorted(all_options, key=lambda x: (x['Expiry'], x['Strike']))

        table = tabulate(all_options[:10], headers="keys", tablefmt="grid", floatfmt=".2f")
        logger.info(f"\nOption Chain for {underlying} (showing {min(10, len(all_options))} of {len(all_options)} rows):\n{table}")

        if len(all_options) > 10:
            logger.info(f"... {len(all_options) - 10} additional rows not shown.")

    except Exception as e:
        logger.error(f"Failed to print option chain for {underlying}: {e}")
        raise