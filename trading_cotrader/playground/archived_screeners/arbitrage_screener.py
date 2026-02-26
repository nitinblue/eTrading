"""
Arbitrage Screener — Volatility arbitrage via calendar/double calendar spreads.

Triggers when IV rank is elevated and Bollinger bandwidth indicates vol expansion.
Exploits IV term structure anomaly: sell near-term high IV, buy far-term lower IV.
"""

from typing import Any, Dict, List, Optional
import logging

from trading_cotrader.config.scenario_template_loader import (
    ScenarioTemplate, load_scenario_templates
)
from trading_cotrader.services.screeners.scenario_screener import ScenarioScreener

logger = logging.getLogger(__name__)


class ArbitrageScreener(ScenarioScreener):
    """Screen for volatility arbitrage calendar spread opportunities."""

    name = "Vol Arbitrage Screener"
    source = "scenario_arbitrage"

    def __init__(self, broker=None, technical_service=None,
                 template: Optional[ScenarioTemplate] = None):
        if template is None:
            templates = load_scenario_templates()
            template = templates.get('vol_arbitrage_calendar')
        super().__init__(broker, technical_service, template=template)

    def _build_extra_context(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """No extra context needed — Bollinger/IV from TechnicalSnapshot."""
        return {}

    def screen(self, symbols: List[str]) -> List[Recommendation]:
        """Use template underlyings if none provided."""
        if not symbols and self.template:
            symbols = self.template.underlyings
        return super().screen(symbols)


# Re-export for import convenience
from trading_cotrader.core.models.recommendation import Recommendation  # noqa: E402, F811
