import asyncio
import yfinance as yf
import pandas as pd
from datetime import datetime
from pathlib import Path

from tastytrade import DXLinkStreamer
from tastytrade.dxfeed import Quote
from tastytrade.instruments import get_option_chain

from trading_cotrader.adapters.tastytrade_adapter import TastytradeAdapter
from trading_cotrader.config.settings import setup_logging, get_settings

from indicators import calculate_rsi, calculate_macd
from dxy import get_dxy_trend

from option_models import TradeIdea
from metals.idea_engine import generate_leaps, generate_diagonal
from idea_evaluator import evaluate_trade

# =============================
# CONFIG
# =============================

METALS = {
    "Gold": "GLD",
    "Silver": "SLV",
    "Copper": "CPER"
}

BASE_DIR = Path(__file__).parent
CYCLE_SLEEP = 300  # seconds

# =============================
# PRICE FETCH (SAFE)
# =============================

async def get_underlying_price(session, symbol):
    async with DXLinkStreamer(session) as streamer:
        await streamer.subscribe(Quote, [symbol])
        event = await streamer.get_event(Quote)

        if not event or event.bid_price is None or event.ask_price is None:
            return None

        return float((event.bid_price + event.ask_price) / 2)

# =============================
# MAIN LOOP
# =============================

def main():
    import asyncio
    from metals.market_data import get_market_state
    from metals.idea_engine import generate_all_ideas
    from metals.idea_evaluator import evaluate_trade


    symbols = ["SLV", "CPER"]

    broker = TastytradeAdapter()
    


    if broker.session is None:
        raise RuntimeError(
            "Broker session is None. "
            "Authentication did not complete successfully."
        )
    session = broker.session
    return broker

    for symbol in symbols:
        try:
            print("\n" + "=" * 80)
            state = get_market_state(symbol)

            print(f"{symbol}")
            print(
                f"Price: {state.price:.2f} | "
                f"RSI: {state.rsi:.1f} | "
                f"MACD: {state.macd:.2f}/{state.macd_signal:.2f}"
            )

            ideas = asyncio.run(
                generate_all_ideas(
                    symbol=symbol,
                    price=state.price,
                    session=session
                )
            )

            for idea in ideas:
                evaluated = evaluate_trade(idea, state)

                print("\n--- OPTION IDEA ---")
                print(f"Strategy: {evaluated.strategy}")
                print(f"Verdict: {evaluated.verdict}")

                if evaluated.legs:
                    for leg in evaluated.legs:
                        print(
                            f"  {leg.symbol} | "
                            f"Strike: {leg.strike} | "
                            f"Δ {leg.delta:.2f} | "
                            f"IV {leg.iv:.1%}"
                        )
                else:
                    print("  No viable option legs")

                print("WHY:")
                for reason in evaluated.why:
                    print(f" - {reason}")

                if evaluated.notes:
                    print("NOTES:")
                    for note in evaluated.notes:
                        print(f" * {note}")

        except Exception as e:
            print(f"Error processing {symbol}: {e}")

# =============================
# ENTRY
# =============================

if __name__ == "__main__":
    asyncio.run(main())
