from typing import TypedDict, List, Dict, Optional
from decimal import Decimal

class TradingState(TypedDict, total=False):
    # Infra
    broker: object
    config: Dict

    # Market context
    market_regime: Optional[str]

    # Portfolio
    trades: List[object]
    defined_risk_used: Decimal
    undefined_risk_used: Decimal
    defined_risk_available: Decimal
    undefined_risk_available: Decimal
    active_risk_bucket: Optional[str]  # defined | undefined
    risk_remaining: Decimal

    # Trading
    proposed_trade: Optional[Dict]

    # Risk
    risk_snapshot: Dict
    risk_hard_stop: bool
    needs_adjustment: bool

    # Output
    output: Optional[str]
