from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AgentState:
    # --- External ---
    broker: object
    config: dict

    # --- Portfolio / Risk ---
    net_liquidation: float = 0.0
    buying_power: float = 0.0

    defined_risk_limit: float = 0.0
    undefined_risk_limit: float = 0.0

    defined_risk_used: float = 0.0
    undefined_risk_used: float = 0.0

    # --- Market Context ---
    market_regime: Optional[str] = None
    news_summary: Optional[str] = None

    # --- Trade Ideas ---
    defined_risk_trades: List[Dict] = field(default_factory=list)
    undefined_risk_trades: List[Dict] = field(default_factory=list)
