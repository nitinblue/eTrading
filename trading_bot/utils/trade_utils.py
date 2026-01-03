# trading_bot/utils/trade_utils.py
from tabulate import tabulate
from datetime import datetime, timedelta
from tastytrade.instruments import get_option_chain
from tastytrade.instruments import Equity
import logging

logger = logging.getLogger(__name__)

def print_option_chain(underlying: str, broker_session):
    """
    Print option chain in centered format:
    - Selects expiry closest to 14 DTE with options.
    - Shows 10 strikes below and above ATM.
    - Centered table: Calls on left, Strike middle, Puts on right.
    - Filters strikes with bid/ask > 0.
    """
    try:
        chain = get_option_chain(broker_session, underlying)
        logger.info(f"Option chain fetched for {underlying}: {len(chain)} expiries available")

        if not chain:
            logger.warning(f"No option chain data for {underlying}")
            return

        # Get underlying price using Equity (fixed API)
        try:
            equity = Equity.get_equity(broker_session, underlying)
            quote = equity.get_quote(broker_session)
            underlying_price = quote.last_price or quote.close_price or quote.bid_price or quote.ask_price or 0.0
            logger.info(f"{underlying} current price: ${underlying_price:.2f}")
        except Exception as e:
            logger.warning(f"Underlying price fetch failed: {e} — using fallback")
            underlying_price = 0  # Fallback, will use mid strike

        # Find expiry closest to 14 DTE with options
        target_date = datetime.now().date() + timedelta(days=14)
        valid_expiries = []
        for exp in chain:
            options = chain[exp]
            if options:
                dte = (exp - datetime.now().date()).days
                valid_expiries.append((exp, dte, options))

        if not valid_expiries:
            logger.warning("No expiry with options found")
            return

        valid_expiries.sort(key=lambda x: abs(x[1] - 14))
        selected_expiry, selected_dte, options = valid_expiries[0]

        logger.info(f"Selected expiry: {selected_expiry} (DTE: {selected_dte} days)")

        # Separate calls and puts
        calls = sorted([o for o in options if o.option_type == 'call'], key=lambda x: x.strike_price)
        puts = sorted([o for o in options if o.option_type == 'put'], key=lambda x: x.strike_price, reverse=True)

        # All strikes
        all_strikes = sorted(set(o.strike_price for o in options))

        if underlying_price == 0:
            underlying_price = all_strikes[len(all_strikes) // 2] if all_strikes else 0

        # 10 below/above ATM
        atm_index = min(range(len(all_strikes)), key=lambda i: abs(all_strikes[i] - underlying_price))
        start = max(0, atm_index - 10)
        end = min(len(all_strikes), atm_index + 11)
        selected_strikes = all_strikes[start:end]

        # Build table
        rows = []
        headers = [
            "Call Bid", "Call Ask", "Call Delta", "Call Gamma", "Call Theta", "Call Vega",
            "Strike",
            "Put Bid", "Put Ask", "Put Delta", "Put Gamma", "Put Theta", "Put Vega"
        ]
        rows.append(headers)

        for strike in selected_strikes:
            call = next((c for c in calls if c.strike_price == strike), None)
            put = next((p for p in puts if p.strike_price == strike), None)

            # Get quotes
            call_bid = call.get_quote(broker_session).bid_price if call else 0.0
            call_ask = call.get_quote(broker_session).ask_price if call else 0.0
            put_bid = put.get_quote(broker_session).bid_price if put else 0.0
            put_ask = put.get_quote(broker_session).ask_price if put else 0.0

            # Skip if no bid/ask
            if call_bid == 0 and call_ask == 0 and put_bid == 0 and put_ask == 0:
                continue

            call_greeks = call.greeks if call and call.greeks else None
            put_greeks = put.greeks if put and put.greeks else None

            rows.append([
                f"{call_bid:.2f}" if call_bid > 0 else "-",
                f"{call_ask:.2f}" if call_ask > 0 else "-",
                f"{call_greeks.delta:.3f}" if call_greeks else "-",
                f"{call_greeks.gamma:.4f}" if call_greeks else "-",
                f"{call_greeks.theta:.2f}" if call_greeks else "-",
                f"{call_greeks.vega:.2f}" if call_greeks else "-",
                f"{strike:.1f}",
                f"{put_bid:.2f}" if put_bid > 0 else "-",
                f"{put_ask:.2f}" if put_ask > 0 else "-",
                f"{put_greeks.delta:.3f}" if put_greeks else "-",
                f"{put_greeks.gamma:.4f}" if put_greeks else "-",
                f"{put_greeks.theta:.2f}" if put_greeks else "-",
                f"{put_greeks.vega:.2f}" if put_greeks else "-",
            ])

        table = tabulate(rows, headers="firstrow", tablefmt="grid")
        logger.info(f"\n{underlying} Option Chain (Expiry: {selected_expiry} | DTE: {dte})\n{table}")

    except Exception as e:
        logger.error(f"Option chain print failed for {underlying}: {e}")
        raise