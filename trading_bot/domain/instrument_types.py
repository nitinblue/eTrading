from enum import Enum


class InstrumentType(str, Enum):
    EQUITY = "EQUITY"
    EQUITY_OPTION = "EQUITY_OPTION"
    FUTURE = "FUTURE"
    FUTURE_OPTION = "FUTURE_OPTION"
