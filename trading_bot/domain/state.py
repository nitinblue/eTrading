from dataclasses import dataclass, field
from typing import Dict, Any, List
from trading_bot.domain.positions import Position


@dataclass
class TradingState:
    broker_name: str
    account_id: str
    broker: Any

    # 👇 owned & populated by portfolio_dude
    portfolio_config: Dict[str, Any] = field(default_factory=dict)
    portfolio_metrics: Dict[str, float] = field(default_factory=dict)

    positions: List[Position] = field(default_factory=list)

    # 👇 produced by risk_dude
    risk_report: Dict[str, Any] = field(default_factory=dict)

    messages: List[str] = field(default_factory=list)
