"""
Event Logging Service

Business logic for logging trading events.
This can be called from CLI, web UI, or anywhere else.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any
from dataclasses import dataclass

from core.database.session import Session, session_scope
from repositories.trade import TradeRepository
from repositories.portfolio import PortfolioRepository
from repositories.event import EventRepository
import core.models.domain as dm
import core.models.events as events

logger = logging.getLogger(__name__)


@dataclass
class TradeOpenedResult:
    """Result of logging a trade opened event"""
    success: bool
    trade_id: Optional[str] = None
    event_id: Optional[str] = None
    error: Optional[str] = None
    trade: Optional[dm.Trade] = None


class EventLogger:
    """
    Service for logging trading events
    
    This contains the business logic that can be called from:
    - CLI
    - Web UI
    - API
    - Scheduled jobs
    - Anywhere else
    """
    
    def __init__(self, session: Session):
        self.session = session
        self.portfolio_repo = PortfolioRepository(session)
        self.trade_repo = TradeRepository(session)
        self.event_repo = EventRepository(session)
    
    def log_trade_opened(
        self,
        underlying: str,
        strategy: str,
        rationale: str,
        outlook: str,
        confidence: int,
        max_risk: float,
        portfolio_id: Optional[str] = None
    ) -> TradeOpenedResult:
        """
        Log a trade opening event
        
        Creates:
        1. Intent trade in database
        2. Event record linked to trade
        
        Args:
            underlying: Symbol (e.g. "IWM")
            strategy: Strategy name (e.g. "iron_condor")
            rationale: Why this trade
            outlook: "bullish", "bearish", "neutral", "uncertain"
            confidence: 1-10
            max_risk: Maximum $ risk
            portfolio_id: Portfolio ID (uses first if not provided)
            
        Returns:
            TradeOpenedResult with success/failure info
        """
        
        try:
            # Get portfolio
            if portfolio_id:
                portfolio = self.portfolio_repo.get_by_id(portfolio_id)
                if not portfolio:
                    return TradeOpenedResult(
                        success=False,
                        error=f"Portfolio {portfolio_id} not found"
                    )
            else:
                portfolios = self.portfolio_repo.get_all_portfolios()
                if not portfolios:
                    return TradeOpenedResult(
                        success=False,
                        error="No portfolio found. Run sync first."
                    )
                portfolio = portfolios[0]
            
            # Generate trade ID
            trade_id = f"manual_{underlying}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            
            # Map strategy string to enum
            strategy_type = self._map_strategy_type(strategy)
            
            # Create intent trade
            intent_trade = dm.Trade(
                id=trade_id,
                underlying_symbol=underlying.upper(),
                trade_type=dm.TradeType.REAL,
                trade_status=dm.TradeStatus.INTENT,
                strategy=dm.Strategy(
                    name=strategy,
                    strategy_type=strategy_type,
                    max_loss=Decimal(str(max_risk))
                ),
                intent_at=datetime.now(timezone.utc),
                max_risk=Decimal(str(max_risk)),
                notes=rationale,
                tags=[strategy, underlying.upper(), outlook],
                legs=[]
            )
            
            # Save trade
            created_trade = self.trade_repo.create_from_domain(intent_trade, portfolio.id)
            if not created_trade:
                return TradeOpenedResult(
                    success=False,
                    error="Failed to create intent trade"
                )
            
            logger.info(f"Created intent trade: {trade_id}")
            
            # Create event
            market_ctx = events.MarketContext(
                timestamp=datetime.now(timezone.utc),
                underlying_symbol=underlying.upper()
            )
            
            outlook_enum = self._map_outlook(outlook)
            
            decision_ctx = events.DecisionContext(
                rationale=rationale,
                market_outlook=outlook_enum,
                confidence_level=confidence,
                risk_tolerance=events.RiskTolerance.MODERATE
            )
            
            event = events.TradeEvent(
                trade_id=trade_id,
                event_type=events.EventType.TRADE_OPENED,
                underlying_symbol=underlying.upper(),
                strategy_type=strategy,
                market_context=market_ctx,
                decision_context=decision_ctx,
                net_credit_debit=Decimal(str(max_risk)),
                tags=[strategy, underlying.upper(), outlook]
            )
            
            created_event = self.event_repo.create_from_domain(event)
            if not created_event:
                return TradeOpenedResult(
                    success=False,
                    error="Failed to log event"
                )
            
            logger.info(f"Event logged: {created_event.event_id}")
            
            return TradeOpenedResult(
                success=True,
                trade_id=trade_id,
                event_id=created_event.event_id,
                trade=created_trade
            )
            
        except Exception as e:
            logger.error(f"Failed to log trade opened: {e}", exc_info=True)
            return TradeOpenedResult(
                success=False,
                error=str(e)
            )
    
    def _map_strategy_type(self, strategy: str) -> dm.StrategyType:
        """Map strategy string to enum"""
        strategy_map = {
            'iron_condor': dm.StrategyType.IRON_CONDOR,
            'vertical_spread': dm.StrategyType.VERTICAL_SPREAD,
            'iron_butterfly': dm.StrategyType.IRON_BUTTERFLY,
            'covered_call': dm.StrategyType.COVERED_CALL,
            'protective_put': dm.StrategyType.PROTECTIVE_PUT,
            'straddle': dm.StrategyType.STRADDLE,
            'strangle': dm.StrategyType.STRANGLE,
            'butterfly': dm.StrategyType.BUTTERFLY,
            'condor': dm.StrategyType.CONDOR,
        }
        return strategy_map.get(strategy.lower(), dm.StrategyType.CUSTOM)
    
    def _map_outlook(self, outlook: str) -> events.MarketOutlook:
        """Map outlook string to enum"""
        outlook_map = {
            'bullish': events.MarketOutlook.BULLISH,
            'bearish': events.MarketOutlook.BEARISH,
            'neutral': events.MarketOutlook.NEUTRAL,
            'uncertain': events.MarketOutlook.UNCERTAIN,
        }
        return outlook_map.get(outlook.lower(), events.MarketOutlook.NEUTRAL)


# ============================================================================
# Testing / Example Usage
# ============================================================================

def main():
    """
    Test the EventLogger service
    
    Usage:
        python -m services.event_logger
    """
    from config.settings import setup_logging, get_settings
    
    # Setup
    setup_logging()
    settings = get_settings()
    
    print("=" * 80)
    print("EVENT LOGGER SERVICE - Test")
    print("=" * 80)
    print()
    
    # Example 1: Log a trade opening
    print("Test 1: Log trade opening event")
    print("-" * 80)
    
    with session_scope() as session:
        event_logger = EventLogger(session)
        
        result = event_logger.log_trade_opened(
            underlying="IWM",
            strategy="iron_condor",
            rationale="IV rank 80, expecting mean reversion to 50",
            outlook="neutral",
            confidence=8,
            max_risk=500.0
        )
        
        if result.success:
            print(f"✓ Success!")
            print(f"  Trade ID: {result.trade_id}")
            print(f"  Event ID: {result.event_id}")
            print(f"  Status: {result.trade.trade_status.value}")
            print(f"  Type: {result.trade.trade_type.value}")
            print()
        else:
            print(f"✗ Failed: {result.error}")
            print()
            return 1
    
    # Example 2: Verify the trade was saved
    print("Test 2: Verify trade exists in database")
    print("-" * 80)
    
    with session_scope() as session:
        trade_repo = TradeRepository(session)
        
        # Get all intent trades
        portfolios = PortfolioRepository(session).get_all_portfolios()
        if portfolios:
            trades = trade_repo.get_by_portfolio(portfolios[0].id)
            intent_trades = [t for t in trades if t.trade_status == dm.TradeStatus.INTENT]
            
            print(f"✓ Found {len(intent_trades)} intent trade(s)")
            for trade in intent_trades[-3:]:  # Show last 3
                print(f"  - {trade.id}")
                print(f"    Underlying: {trade.underlying_symbol}")
                print(f"    Strategy: {trade.strategy.name if trade.strategy else 'N/A'}")
                print(f"    Max Risk: ${trade.max_risk}")
                print(f"    Notes: {trade.notes[:50]}...")
                print()
    
    # Example 3: Verify the event was saved
    print("Test 3: Verify event exists in database")
    print("-" * 80)
    
    with session_scope() as session:
        event_repo = EventRepository(session)
        
        # Get recent events
        recent_events = event_repo.get_recent_events(days=1)
        
        print(f"✓ Found {len(recent_events)} event(s) in last 24 hours")
        for event in recent_events[-3:]:  # Show last 3
            print(f"  - {event.event_id}")
            print(f"    Type: {event.event_type.value}")
            print(f"    Underlying: {event.underlying_symbol}")
            print(f"    Rationale: {event.decision_context.rationale[:50]}...")
            print(f"    Confidence: {event.decision_context.confidence_level}/10")
            print()
    
    # Example 4: Test error handling
    print("Test 4: Test error handling (invalid confidence)")
    print("-" * 80)
    
    with session_scope() as session:
        event_logger = EventLogger(session)
        
        result = event_logger.log_trade_opened(
            underlying="SPY",
            strategy="covered_call",
            rationale="Testing error handling",
            outlook="bullish",
            confidence=15,  # Invalid - should be 1-10
            max_risk=1000.0
        )
        
        # Should still work - service doesn't validate confidence range
        # That would be done by CLI or web form validation
        if result.success:
            print(f"✓ Service accepted invalid confidence (validation should be in UI layer)")
        else:
            print(f"✗ Failed: {result.error}")
        print()
    
    print("=" * 80)
    print("✓ All tests completed")
    print("=" * 80)
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())