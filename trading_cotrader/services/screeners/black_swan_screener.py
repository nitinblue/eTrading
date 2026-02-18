"""
Black Swan Screener — Tail risk hedge / protection buying.

Triggers when VIX > 30 and market has dropped > 12% from highs.
Insurance, not income — buys protective puts.
"""

from typing import Any, Dict, List, Optional
import logging

from trading_cotrader.config.scenario_template_loader import (
    ScenarioTemplate, load_scenario_templates
)
from trading_cotrader.services.screeners.scenario_screener import ScenarioScreener

logger = logging.getLogger(__name__)


class BlackSwanScreener(ScenarioScreener):
    """Screen for tail risk hedging opportunities."""

    name = "Black Swan Hedge Screener"
    source = "scenario_black_swan"

    def __init__(self, broker=None, technical_service=None,
                 template: Optional[ScenarioTemplate] = None):
        if template is None:
            templates = load_scenario_templates()
            template = templates.get('black_swan_hedge')
        super().__init__(broker, technical_service, template=template)

    def _build_extra_context(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """Add VIX to global context."""
        vix = self._get_vix()
        return {'_global': {'vix': vix}}

    def _get_vix(self) -> Optional[float]:
        """Get current VIX level."""
        if not self.broker:
            return 18.0  # mock default — below trigger threshold
        try:
            quote = self.broker.get_quote('VIX')
            if quote:
                bid = float(quote.get('bid', 0))
                ask = float(quote.get('ask', 0))
                mid = (bid + ask) / 2
                return mid if mid > 0 else None
        except Exception as e:
            logger.warning(f"Failed to get VIX: {e}")
        return None

    def screen(self, symbols: List[str]) -> List[Recommendation]:
        """Use template underlyings (SPY) if none provided."""
        if not symbols and self.template:
            symbols = self.template.underlyings
        return super().screen(symbols)


# Re-export for import convenience
from trading_cotrader.core.models.recommendation import Recommendation  # noqa: E402, F811
