from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional

from trading_bot.domain.instrument_types import InstrumentType


class OptionType(str, Enum):
    CALL = "CALL"
    PUT = "PUT"


# ---------------------------
# BASE INSTRUMENT
# ---------------------------

@dataclass(kw_only=True)
class Instrument:
    """
    Immutable description of a tradable instrument.
    """

    instrument_type: InstrumentType
    symbol: str
    exchange: Optional[str] = None
    currency: str = "USD"


# ---------------------------
# EQUITY
# ---------------------------

@dataclass(kw_only=True)
class EquityInstrument(Instrument):
    pass


# ---------------------------
# EQUITY OPTION
# ---------------------------

@dataclass(kw_only=True)
class EquityOptionInstrument(Instrument):
    expiry: date
    strike: float
    option_type: OptionType
    contract_size: int = 100


# ---------------------------
# FUTURE
# ---------------------------

@dataclass(kw_only=True)
class FutureInstrument(Instrument):
    expiry: date
    contract_size: float


# ---------------------------
# FUTURE OPTION
# ---------------------------

@dataclass(kw_only=True)
class FutureOptionInstrument(Instrument):
    expiry: date
    strike: float
    option_type: OptionType
    underlying_future_expiry: date
    contract_size: float
