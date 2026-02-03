from tastytrade import DXLinkStreamer
from tastytrade.dxfeed import Quote, Greeks

async def fetch_option_snapshot(session, option_symbol: str):
    async with DXLinkStreamer(session) as streamer:
        await streamer.subscribe(Greeks, [option_symbol])
        await streamer.subscribe(Quote, [option_symbol])

        greeks = await streamer.get_event(Greeks)
        quote = await streamer.get_event(Quote)

        if not greeks:
            return None

        mid_price = None
        if quote and quote.bid_price and quote.ask_price:
            mid_price = (quote.bid_price + quote.ask_price) / 2

        return {
            "symbol": option_symbol,
            "expiry": greeks.expiration_date,
            "strike": float(greeks.strike_price),
            "option_type": greeks.option_type,
            "price": mid_price,
            "delta": greeks.delta,
            "gamma": greeks.gamma,
            "theta": greeks.theta,
            "vega": greeks.vega,
            "iv": greeks.implied_volatility
        }
