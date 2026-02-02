"""
Step 09: Events & Event Analytics

Wires existing event logging and analytics services:
- services/event_logger.py → EventLogger
- services/event_analytics.py → EventAnalytics
- repositories/event.py → EventRepository
- core/models/events.py → EventType, TradeEvent

Shows:
- Recent trade events
- Event patterns
- Decision history
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
from harness.base import (
    TestStep, StepResult, rich_table, format_currency, format_percent
)
logger = logging.getLogger(__name__)


class EventsStep(TestStep):
    """
    Harness step for events and event analytics.
    
    Usage:
        python -m harness.runner
        # Step 09 will display event data
    """
    name = "Step 9: Events and Analytics"
    description = "Harness calls Events"
    order = 9
    
    def __init__(self):
        self.event_logger = None
        self.event_analytics = None
    
    def execute(self, context: Dict[str, Any]) -> bool:
        """
        Run events step.
        
        Args:
            context: Dict containing:
                - 'session': SQLAlchemy session
                - 'portfolio': dm.Portfolio
        """
        print(f"\n{'='*60}")
        print(f"STEP {self.order}: {self.name}")
        print('='*60)
        
        session = context.get('session')
        portfolio = context.get('portfolio')
        
        if not session:
            print("  ⚠️  No session available")
            return True
        
        # Initialize services
        try:
            from services.event_logger import EventLogger
            from services.event_analytics import EventAnalytics
            
            self.event_logger = EventLogger(session)
            self.event_analytics = EventAnalytics(session)
            print("  ✓ Event services initialized")
        except ImportError as e:
            print(f"  ⚠️  Could not import event services: {e}")
            return True
        
        # 1. Show recent events
        print("\n1. Recent Trade Events:")
        self._show_recent_events(session, portfolio)
        
        # 2. Show event patterns
        print("\n2. Detected Patterns:")
        self._show_patterns(portfolio)
        
        # 3. Show event summary
        print("\n3. Event Summary:")
        self._show_summary(portfolio)
        
        print(f"\n✓ {self.name} complete")
        return True
    
    def _show_recent_events(self, session, portfolio, limit: int = 10):
        """Display recent trade events"""
        try:
            from repositories.event import EventRepository
            from core.database.schema import TradeEventORM
            
            # Try using repository
            try:
                event_repo = EventRepository(session)
                events = event_repo.get_recent(limit=limit)
            except:
                # Fallback to direct query
                events = session.query(TradeEventORM).order_by(
                    TradeEventORM.timestamp.desc()
                ).limit(limit).all()
            
            if not events:
                print("    No events found")
                return
            
            for event in events[:5]:  # Show first 5
                ts = event.timestamp.strftime('%Y-%m-%d %H:%M') if event.timestamp else 'N/A'
                event_type = getattr(event, 'event_type', 'UNKNOWN')
                underlying = getattr(event, 'underlying_symbol', 'N/A')
                print(f"    [{ts}] {event_type} - {underlying}")
            
            if len(events) > 5:
                print(f"    ... and {len(events) - 5} more events")
                
        except Exception as e:
            print(f"    ⚠️  Could not load events: {e}")
    
    def _show_patterns(self, portfolio):
        """Show detected patterns from event analytics"""
        try:
            if not self.event_analytics:
                print("    Event analytics not available")
                return
            
            # Try to get patterns
            try:
                patterns = self.event_analytics.analyze_patterns(portfolio.id if portfolio else None)
                if patterns:
                    for p in patterns[:3]:
                        print(f"    • {p.get('description', 'Unknown pattern')}")
                else:
                    print("    No patterns detected yet (need more events)")
            except AttributeError:
                print("    Pattern analysis not implemented yet")
                
        except Exception as e:
            print(f"    ⚠️  Could not analyze patterns: {e}")
    
    def _show_summary(self, portfolio):
        """Show event summary statistics"""
        try:
            if not self.event_analytics:
                print("    Event analytics not available")
                return
            
            # Try to get summary
            try:
                summary = self.event_analytics.get_trade_summary(
                    portfolio.id if portfolio else None
                )
                if summary:
                    print(f"    Total events: {summary.get('total_events', 0)}")
                    print(f"    Events with outcomes: {summary.get('events_with_outcomes', 0)}")
                    print(f"    Win rate: {summary.get('win_rate', 0):.1%}")
                else:
                    print("    No summary available")
            except AttributeError:
                print("    Summary not implemented yet")
                
        except Exception as e:
            print(f"    ⚠️  Could not get summary: {e}")


# For use in harness runner
def create_step():
    return EventsStep()
