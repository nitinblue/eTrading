"""
Macro Agent — Wraps MacroContextService to evaluate macro conditions.

Enriches context with:
    - macro_assessment: dict (regime, should_screen, confidence_modifier, rationale)
"""

import logging

from trading_cotrader.agents.protocol import AgentResult, AgentStatus
from trading_cotrader.services.macro_context_service import (
    MacroContextService, MacroOverride,
)

logger = logging.getLogger(__name__)


class MacroAgent:
    """Evaluates macro conditions to gate screener execution."""

    name = "macro"

    def __init__(self, broker=None):
        self.service = MacroContextService(broker=broker)

    def safety_check(self, context: dict) -> tuple[bool, str]:
        return True, ""

    def run(self, context: dict) -> AgentResult:
        """
        Evaluate macro conditions. Reads optional 'macro_override' from context.

        Writes 'macro_assessment' to context.
        """
        try:
            override = None
            override_data = context.get('macro_override')
            if override_data and isinstance(override_data, dict):
                override = MacroOverride(**override_data)

            assessment = self.service.evaluate(override=override)

            context['macro_assessment'] = {
                'regime': assessment.regime,
                'should_screen': assessment.should_screen,
                'confidence_modifier': assessment.confidence_modifier,
                'rationale': assessment.rationale,
                'vix_level': float(assessment.vix_level) if assessment.vix_level else None,
                'override_applied': assessment.override_applied,
            }

            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                data={
                    'regime': assessment.regime,
                    'should_screen': assessment.should_screen,
                },
                messages=[
                    f"Macro: {assessment.regime} — {assessment.rationale}"
                ],
            )

        except Exception as e:
            logger.error(f"MacroAgent failed: {e}")
            context['macro_assessment'] = {
                'regime': 'neutral',
                'should_screen': True,
                'confidence_modifier': 1.0,
                'rationale': f'Macro evaluation failed ({e}), defaulting to neutral',
            }
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                messages=[f"Macro error (defaulting to neutral): {e}"],
            )
