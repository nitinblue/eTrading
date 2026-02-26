"""
Earnings Screener — Sells premium before earnings for IV crush.

Triggers when a symbol has earnings in 2-7 days and IV rank is elevated.
Uses EarningsCalendarService for days_to_earnings context.
"""

from typing import Any, Dict, List, Optional
import logging

from trading_cotrader.config.scenario_template_loader import (
    ScenarioTemplate, load_scenario_templates
)
from trading_cotrader.services.screeners.scenario_screener import ScenarioScreener

logger = logging.getLogger(__name__)


class EarningsScreener(ScenarioScreener):
    """Screen for earnings IV crush opportunities."""

    name = "Earnings IV Crush Screener"
    source = "scenario_earnings"

    def __init__(self, broker=None, technical_service=None,
                 template: Optional[ScenarioTemplate] = None):
        if template is None:
            templates = load_scenario_templates()
            template = templates.get('earnings_iv_crush')
        super().__init__(broker, technical_service, template=template)
        self._earnings_service = None

    def _get_earnings_service(self):
        if self._earnings_service is None:
            from trading_cotrader.services.earnings_calendar_service import EarningsCalendarService
            self._earnings_service = EarningsCalendarService(
                use_mock=(self.broker is None)
            )
        return self._earnings_service

    def _build_extra_context(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """Fetch days-to-earnings for each symbol."""
        svc = self._get_earnings_service()
        ctx: Dict[str, Dict[str, Any]] = {}
        for symbol in symbols:
            days = svc.get_days_to_earnings(symbol)
            ctx[symbol] = {'days_to_earnings': days}
        return ctx

    def screen(self, symbols: List[str]) -> List[Recommendation]:
        """
        Override: if template has no underlyings (dynamic), use all provided symbols.
        Otherwise use template underlyings.
        """
        if not symbols and self.template and self.template.underlyings:
            symbols = self.template.underlyings
        return super().screen(symbols)


# Re-export for import convenience
from trading_cotrader.core.models.recommendation import Recommendation  # noqa: E402, F811
