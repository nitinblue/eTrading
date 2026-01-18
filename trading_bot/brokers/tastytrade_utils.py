import logging
from datetime import datetime
from trading_bot.domain.instruments import Instrument, InstrumentType, OptionType
from trading_bot.domain.positions import Position

logger = logging.getLogger(__name__)


def fetch_positions_from_tastytrade(broker, account_id: str) -> list[Position]:
    """
    Converts raw Tastytrade positions into domain Position objects.
    Does NOT modify tastytrade_broker.
    """

    raw_positions = broker.get_positions(account_id)
    domain_positions: list[Position] = []

    for p in raw_positions:
        symbol = p["symbol"]

        if p["instrument-type"] == "Equity Option":
            instrument = Instrument(
                symbol=symbol,
                instrument_type=InstrumentType.EQUITY_OPTION,
                exchange=p.get("exchange", "SMART"),
                underlying=p["underlying-symbol"],
                expiry=datetime.strptime(p["expiration-date"], "%Y-%m-%d").date(),
                strike=float(p["strike-price"]),
                option_type=OptionType.CALL if p["option-type"] == "C" else OptionType.PUT,
                multiplier=int(p.get("multiplier", 100))
            )
        else:
            instrument = Instrument(
                symbol=symbol,
                instrument_type=InstrumentType.EQUITY,
                exchange=p.get("exchange", "SMART"),
                multiplier=1
            )

        domain_positions.append(
            Position(
                account_id=account_id,
                instrument=instrument,
                quantity=int(p["quantity"]),
                avg_price=float(p["average-price"]),
                mark_price=float(p["mark-price"]),
                unrealized_pnl=float(p["unrealized-day-gain"]),
                realized_pnl=float(p.get("realized-day-gain", 0)),
                delta=float(p.get("delta", 0)) if "delta" in p else None,
                theta=float(p.get("theta", 0)) if "theta" in p else None,
                vega=float(p.get("vega", 0)) if "vega" in p else None,
                gamma=float(p.get("gamma", 0)) if "gamma" in p else None,
            )
        )

    return domain_positions
