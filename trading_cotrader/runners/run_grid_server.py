"""
Grid Server Runner

Starts the WebSocket server with mock or live data.

Usage:
    python -m trading_cotrader.runners.run_grid_server [--mock|--live]

Then open trading_cotrader/ui/trading-grid.html in a browser.
"""

import sys
import argparse
import logging
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MockDataProvider:
    """Provides mock data for development/testing"""

    def __init__(self):
        self.refresh_count = 0

    def get_snapshot(self):
        """Return a mock snapshot"""
        from trading_cotrader.server.contracts import (
            MarketSnapshot, MarketContext, VolatilityQuote,
            PositionWithMarket, PositionGreeks, RiskBucket,
            RiskLimit, create_empty_snapshot
        )

        self.refresh_count += 1

        # Create mock positions
        positions = self._create_mock_positions()

        # Create risk buckets by underlying
        risk_by_underlying = self._aggregate_risk(positions)

        # Portfolio totals
        portfolio_risk = RiskBucket(
            underlying="PORTFOLIO",
            delta=sum(r.delta for r in risk_by_underlying.values()),
            gamma=sum(r.gamma for r in risk_by_underlying.values()),
            theta=sum(r.theta for r in risk_by_underlying.values()),
            vega=sum(r.vega for r in risk_by_underlying.values()),
            position_count=len(positions),
        )

        # Create snapshot
        snapshot = create_empty_snapshot()
        snapshot.positions = positions
        snapshot.risk_by_underlying = risk_by_underlying
        snapshot.portfolio_risk = portfolio_risk
        snapshot.account_value = Decimal('250000')
        snapshot.buying_power = Decimal('150000')
        snapshot.refresh_count = self.refresh_count
        snapshot.timestamp = datetime.utcnow()

        return snapshot

    def _create_mock_positions(self) -> List:
        """Create mock positions"""
        from trading_cotrader.server.contracts import PositionWithMarket, PositionGreeks
        import random

        positions = []

        # SPY Iron Condor
        spy_spot = Decimal('585.50') + Decimal(str(random.uniform(-2, 2)))

        positions.extend([
            PositionWithMarket(
                position_id='spy-ic-put-sell',
                symbol='SPY',
                option_type='PUT',
                strike=Decimal('570'),
                expiry='2026-02-21',
                dte=12,
                quantity=-2,
                entry_price=Decimal('3.50'),
                bid=Decimal('2.80'),
                ask=Decimal('3.00'),
                last=Decimal('2.90'),
                mark=Decimal('2.90'),
                greeks=PositionGreeks(
                    delta=Decimal('0.30'),
                    gamma=Decimal('0.02'),
                    theta=Decimal('-8.50'),
                    vega=Decimal('15.00'),
                ),
                iv=Decimal('0.18'),
                entry_value=Decimal('-700'),
                market_value=Decimal('-580'),
                unrealized_pnl=Decimal('120'),
            ),
            PositionWithMarket(
                position_id='spy-ic-put-buy',
                symbol='SPY',
                option_type='PUT',
                strike=Decimal('560'),
                expiry='2026-02-21',
                dte=12,
                quantity=2,
                entry_price=Decimal('2.00'),
                bid=Decimal('1.50'),
                ask=Decimal('1.70'),
                last=Decimal('1.60'),
                mark=Decimal('1.60'),
                greeks=PositionGreeks(
                    delta=Decimal('-0.15'),
                    gamma=Decimal('-0.01'),
                    theta=Decimal('5.00'),
                    vega=Decimal('-10.00'),
                ),
                iv=Decimal('0.20'),
                entry_value=Decimal('400'),
                market_value=Decimal('320'),
                unrealized_pnl=Decimal('-80'),
            ),
            PositionWithMarket(
                position_id='spy-ic-call-sell',
                symbol='SPY',
                option_type='CALL',
                strike=Decimal('600'),
                expiry='2026-02-21',
                dte=12,
                quantity=-2,
                entry_price=Decimal('3.00'),
                bid=Decimal('2.50'),
                ask=Decimal('2.70'),
                last=Decimal('2.60'),
                mark=Decimal('2.60'),
                greeks=PositionGreeks(
                    delta=Decimal('-0.35'),
                    gamma=Decimal('0.02'),
                    theta=Decimal('-7.00'),
                    vega=Decimal('14.00'),
                ),
                iv=Decimal('0.16'),
                entry_value=Decimal('-600'),
                market_value=Decimal('-520'),
                unrealized_pnl=Decimal('80'),
            ),
            PositionWithMarket(
                position_id='spy-ic-call-buy',
                symbol='SPY',
                option_type='CALL',
                strike=Decimal('610'),
                expiry='2026-02-21',
                dte=12,
                quantity=2,
                entry_price=Decimal('1.50'),
                bid=Decimal('1.20'),
                ask=Decimal('1.40'),
                last=Decimal('1.30'),
                mark=Decimal('1.30'),
                greeks=PositionGreeks(
                    delta=Decimal('0.20'),
                    gamma=Decimal('-0.01'),
                    theta=Decimal('4.00'),
                    vega=Decimal('-8.00'),
                ),
                iv=Decimal('0.15'),
                entry_value=Decimal('300'),
                market_value=Decimal('260'),
                unrealized_pnl=Decimal('-40'),
            ),
        ])

        # QQQ Vertical Spread
        positions.extend([
            PositionWithMarket(
                position_id='qqq-vert-sell',
                symbol='QQQ',
                option_type='PUT',
                strike=Decimal('500'),
                expiry='2026-02-21',
                dte=12,
                quantity=-3,
                entry_price=Decimal('4.00'),
                bid=Decimal('3.20'),
                ask=Decimal('3.50'),
                last=Decimal('3.35'),
                mark=Decimal('3.35'),
                greeks=PositionGreeks(
                    delta=Decimal('0.45'),
                    gamma=Decimal('0.03'),
                    theta=Decimal('-12.00'),
                    vega=Decimal('20.00'),
                ),
                iv=Decimal('0.22'),
                entry_value=Decimal('-1200'),
                market_value=Decimal('-1005'),
                unrealized_pnl=Decimal('195'),
            ),
            PositionWithMarket(
                position_id='qqq-vert-buy',
                symbol='QQQ',
                option_type='PUT',
                strike=Decimal('490'),
                expiry='2026-02-21',
                dte=12,
                quantity=3,
                entry_price=Decimal('2.50'),
                bid=Decimal('2.00'),
                ask=Decimal('2.30'),
                last=Decimal('2.15'),
                mark=Decimal('2.15'),
                greeks=PositionGreeks(
                    delta=Decimal('-0.25'),
                    gamma=Decimal('-0.02'),
                    theta=Decimal('8.00'),
                    vega=Decimal('-12.00'),
                ),
                iv=Decimal('0.24'),
                entry_value=Decimal('750'),
                market_value=Decimal('645'),
                unrealized_pnl=Decimal('-105'),
            ),
        ])

        # AAPL Stock Position
        positions.append(
            PositionWithMarket(
                position_id='aapl-stock',
                symbol='AAPL',
                option_type=None,
                strike=None,
                expiry=None,
                dte=None,
                quantity=100,
                entry_price=Decimal('185.50'),
                bid=Decimal('188.90'),
                ask=Decimal('189.10'),
                last=Decimal('189.00'),
                mark=Decimal('189.00'),
                greeks=PositionGreeks(
                    delta=Decimal('100.00'),
                    gamma=Decimal('0'),
                    theta=Decimal('0'),
                    vega=Decimal('0'),
                ),
                iv=Decimal('0'),
                entry_value=Decimal('18550'),
                market_value=Decimal('18900'),
                unrealized_pnl=Decimal('350'),
            )
        )

        return positions

    def _aggregate_risk(self, positions) -> Dict:
        """Aggregate positions into risk buckets by underlying"""
        from trading_cotrader.server.contracts import RiskBucket

        buckets = {}

        for pos in positions:
            underlying = pos.symbol
            if underlying not in buckets:
                buckets[underlying] = RiskBucket(
                    underlying=underlying,
                    delta=Decimal('0'),
                    gamma=Decimal('0'),
                    theta=Decimal('0'),
                    vega=Decimal('0'),
                )

            bucket = buckets[underlying]
            bucket.delta += pos.greeks.delta
            bucket.gamma += pos.greeks.gamma
            bucket.theta += pos.greeks.theta
            bucket.vega += pos.greeks.vega
            bucket.position_count += 1

            if pos.quantity > 0:
                bucket.long_count += 1
            else:
                bucket.short_count += 1

        return buckets


def main():
    parser = argparse.ArgumentParser(description='Run Trading Grid Server')
    parser.add_argument('--mock', action='store_true', help='Use mock data (default)')
    parser.add_argument('--live', action='store_true', help='Use live TastyTrade data')
    parser.add_argument('--port', type=int, default=8000, help='Server port')
    args = parser.parse_args()

    # Set up data provider
    if args.live:
        logger.info("Using live TastyTrade data provider")
        from trading_cotrader.server.data_provider import RefreshBasedProvider
        provider = RefreshBasedProvider()
    else:
        logger.info("Using mock data provider")
        provider = MockDataProvider()

    # Configure server
    from trading_cotrader.server.websocket_server import app, set_data_provider, container_manager
    set_data_provider(provider)

    # Load initial data
    try:
        snapshot = provider.get_snapshot()
        container_manager.load_from_snapshot(snapshot)
        logger.info(f"Loaded {container_manager.positions.count} positions")
    except Exception as e:
        logger.error(f"Failed to load initial data: {e}")

    # Run server
    import uvicorn
    logger.info(f"Starting server on http://localhost:{args.port}")
    logger.info(f"Open trading_cotrader/ui/trading-grid.html in a browser")
    uvicorn.run(app, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
