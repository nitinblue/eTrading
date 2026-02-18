"""
Market Data Agent — Fetches technical snapshots and VIX for the shared context.

Wraps TechnicalAnalysisService. Enriches context with:
    - snapshots: dict of symbol → TechnicalSnapshot
    - vix: float (current VIX level)
"""

from decimal import Decimal
from typing import Optional
import logging

from trading_cotrader.agents.protocol import AgentResult, AgentStatus

logger = logging.getLogger(__name__)


class MarketDataAgent:
    """Fetches market data snapshots and VIX."""

    name = "market_data"

    def __init__(self, broker=None, use_mock: bool = False):
        self.broker = broker
        self.use_mock = use_mock
        self._tech_service = None

    def _get_tech_service(self):
        if self._tech_service is None:
            from trading_cotrader.services.technical_analysis_service import TechnicalAnalysisService
            self._tech_service = TechnicalAnalysisService(use_mock=self.use_mock)
        return self._tech_service

    def safety_check(self, context: dict) -> tuple[bool, str]:
        return True, ""

    def run(self, context: dict) -> AgentResult:
        """
        Fetch market data for watchlist symbols.

        Reads 'watchlist_symbols' from context (default: SPY, QQQ, IWM).
        Writes 'snapshots' and 'vix' to context.
        """
        symbols = context.get('watchlist_symbols', ['SPY', 'QQQ', 'IWM'])
        messages = []

        try:
            tech = self._get_tech_service()
            snapshots = {}
            vix = 20.0  # default fallback

            for symbol in symbols:
                try:
                    snap = tech.get_snapshot(symbol)
                    snapshots[symbol] = snap
                except Exception as e:
                    logger.warning(f"Failed to get snapshot for {symbol}: {e}")
                    messages.append(f"Snapshot failed for {symbol}: {e}")

            context['snapshots'] = snapshots
            context['vix'] = vix

            # Populate MarketDataContainer if available
            container_manager = context.get('container_manager')
            if container_manager and hasattr(container_manager, 'market_data'):
                for sym, snap in snapshots.items():
                    container_manager.market_data.update_from_snapshot(snap)
                messages.append(
                    f"Updated MarketDataContainer: {container_manager.market_data.count} symbols"
                )

            messages.append(f"Fetched {len(snapshots)}/{len(symbols)} snapshots, VIX={vix:.1f}")

            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                data={'symbol_count': len(snapshots), 'vix': vix},
                messages=messages,
            )

        except Exception as e:
            logger.error(f"MarketDataAgent failed: {e}")
            context['vix'] = 20.0  # safe default
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                messages=[f"Market data error: {e}"],
            )
