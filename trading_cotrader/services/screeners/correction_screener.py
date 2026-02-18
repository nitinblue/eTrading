"""
Correction Screener — Market correction premium selling.

Triggers when market drops 8-15% from highs with elevated VIX.
Pure trigger-based — no extra context needed beyond TechnicalSnapshot + VIX.
"""

from typing import Any, Dict, List, Optional
import logging

from trading_cotrader.config.scenario_template_loader import (
    ScenarioTemplate, load_scenario_templates
)
from trading_cotrader.services.screeners.scenario_screener import ScenarioScreener

logger = logging.getLogger(__name__)


class CorrectionScreener(ScenarioScreener):
    """Screen for market correction premium-selling opportunities."""

    name = "Market Correction Screener"
    source = "scenario_correction"

    def __init__(self, broker=None, technical_service=None,
                 template: Optional[ScenarioTemplate] = None):
        if template is None:
            templates = load_scenario_templates()
            template = templates.get('correction_premium_sell')
        super().__init__(broker, technical_service, template=template)

    def _build_extra_context(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """Add VIX to context."""
        vix = self._get_vix()
        return {'_global': {'vix': vix}}

    def _get_vix(self) -> Optional[float]:
        """Get current VIX level."""
        if not self.broker:
            return 18.0  # mock default
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
        """Override to use template underlyings if symbols not specified."""
        if not symbols and self.template:
            symbols = self.template.underlyings
        return super().screen(symbols)


# Re-export for import convenience
from trading_cotrader.core.models.recommendation import Recommendation  # noqa: E402, F811
