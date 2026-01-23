"""
Event Logger CLI - Capture trading decisions and outcomes

This is how you teach the AI about your trading patterns.
Every time you make a decision, log it here.
"""

import sys
from pathlib import Path
from datetime import datetime
from decimal import Decimal
import argparse

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import setup_logging, get_settings
from core.database.session import session_scope
from repositories.event import EventRepository
from repositories.trade import TradeRepository
from repositories.portfolio import PortfolioRepository
from repositories.position import PositionRepository
import core.models.events as events
import core.models.domain as dm
import logging

logger = logging.getLogger(__name__)


class EventLogger:
    """CLI tool for logging trading events"""
    
    def __init__(self):
        self.settings = get_settings()
    
    def log_trade_open(
        self,
        underlying: str,
        strategy: str,
        rationale: str,
        market_outlook: str,
        confidence: int,
        risk_amount: float,
        profit_target_pct: float = None,
        max_loss_pct: float = None
    ):
        """
        Log when you OPEN a new trade
        
        This captures WHY you entered and WHAT you expect
        """
        print(f"\n{'='*80}")
        print(f"LOGGING: Trade Open - {underlying}")
        print(f"{'='*80}")
        
        try:
            with session_scope() as session:
                event_repo = EventRepository(session)
                portfolio_repo = PortfolioRepository(session)
                position_repo = PositionRepository(session)
                
                # Get current portfolio state
                portfolio = portfolio_repo.get_all_portfolios()[0]
                positions = position_repo.get_by_portfolio(portfolio.id)
                
                # Get current positions for this underlying
                underlying_positions = [p for p in positions if p.symbol.ticker == underlying]
                
                # Calculate entry Greeks
                entry_delta = sum(p.greeks.delta if p.greeks else 0 for p in underlying_positions)
                entry_theta = sum(p.greeks.theta if p.greeks else 0 for p in underlying_positions)
                entry_vega = sum(p.greeks.vega if p.greeks else 0 for p in underlying_positions)
                
                # Get current price (from first position)
                underlying_price = underlying_positions[0].current_price if underlying_positions else Decimal('0')
                
                # Build market context
                market_context = events.MarketContext(
                    underlying_symbol=underlying,
                    underlying_price=underlying_price,
                    timestamp=datetime.utcnow()
                )
                
                # Build decision context
                decision_context = events.DecisionContext(
                    rationale=rationale,
                    market_outlook=events.MarketOutlook(market_outlook.lower()),
                    confidence_level=confidence,
                    profit_target_percent=Decimal(str(profit_target_pct)) if profit_target_pct else None,
                    max_loss_percent=Decimal(str(max_loss_pct)) if max_loss_pct else None
                )
                
                # Create event
                event = events.TradeEvent(
                    event_type=events.EventType.TRADE_OPENED,
                    trade_id=f"manual_{underlying}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                    market_context=market_context,
                    decision_context=decision_context,
                    strategy_type=strategy,
                    underlying_symbol=underlying,
                    net_credit_debit=Decimal(str(risk_amount)),
                    entry_delta=entry_delta,
                    entry_theta=entry_theta,
                    entry_vega=entry_vega,
                    tags=[strategy, underlying, market_outlook]
                )
                
                # Save event
                created = event_repo.create_from_domain(event)
                
                if created:
                    print(f"\n✅ Event logged successfully!")
                    print(f"  Event ID: {created.event_id}")
                    print(f"  Trade: {underlying} - {strategy}")
                    print(f"  Rationale: {rationale}")
                    print(f"  Confidence: {confidence}/10")
                    print(f"  Entry Delta: {entry_delta:.2f}")
                    print(f"\n💡 When you close this trade, log the outcome with:")
                    print(f"     python -m cli.log_event close-trade --event-id {created.event_id}")
                else:
                    print("❌ Failed to log event")
                    return False
                
                return True
                
        except Exception as e:
            print(f"❌ Error logging event: {e}")
            logger.exception("Full error:")
            return False
    
    def log_trade_close(
        self,
        event_id: str,
        final_pnl: float,
        close_reason: str,
        days_held: int = None,
        met_expectations: bool = True,
        what_went_right: str = "",
        what_went_wrong: str = "",
        would_do_differently: str = ""
    ):
        """
        Log when you CLOSE a trade
        
        This captures the OUTCOME and what you learned
        """
        print(f"\n{'='*80}")
        print(f"LOGGING: Trade Close")
        print(f"{'='*80}")
        
        try:
            with session_scope() as session:
                event_repo = EventRepository(session)
                
                # Find the original open event
                original_event = event_repo.get_by_id(event_id)
                if not original_event:
                    print(f"❌ Event {event_id} not found")
                    return False
                
                # Calculate outcome
                pnl_decimal = Decimal(str(final_pnl))
                outcome_type = events.TradeOutcome.WIN if pnl_decimal > 0 else \
                              events.TradeOutcome.LOSS if pnl_decimal < 0 else \
                              events.TradeOutcome.BREAKEVEN
                
                # Calculate days held if not provided
                if not days_held:
                    days_held = (datetime.utcnow() - original_event.timestamp).days
                
                # Calculate P&L percent (if we have cost basis)
                cost_basis = abs(original_event.net_credit_debit)
                pnl_percent = (pnl_decimal / cost_basis * 100) if cost_basis > 0 else Decimal('0')
                
                # Build outcome
                outcome = events.TradeOutcomeData(
                    outcome=outcome_type,
                    final_pnl=pnl_decimal,
                    pnl_percent=pnl_percent,
                    days_held=days_held,
                    close_reason=close_reason,
                    met_expectations=met_expectations,
                    what_went_right=what_went_right,
                    what_went_wrong=what_went_wrong,
                    would_do_differently=would_do_differently
                )
                
                # Update the original event with outcome
                success = event_repo.update_outcome(event_id, outcome)
                
                if success:
                    print(f"\n✅ Trade outcome logged!")
                    print(f"  Original trade: {original_event.underlying_symbol} - {original_event.strategy_type}")
                    print(f"  Opened: {original_event.timestamp.strftime('%Y-%m-%d')}")
                    print(f"  Days held: {days_held}")
                    print(f"  P&L: ${pnl_decimal:,.2f} ({pnl_percent:.1f}%)")
                    print(f"  Result: {outcome_type.value.upper()}")
                    print(f"  Reason: {close_reason}")
                    
                    if what_went_right:
                        print(f"\n  What went right: {what_went_right}")
                    if what_went_wrong:
                        print(f"  What went wrong: {what_went_wrong}")
                    if would_do_differently:
                        print(f"  Would do differently: {would_do_differently}")
                else:
                    print("❌ Failed to log outcome")
                    return False
                
                return True
                
        except Exception as e:
            print(f"❌ Error logging outcome: {e}")
            logger.exception("Full error:")
            return False
    
    def log_adjustment(
        self,
        underlying: str,
        adjustment_type: str,
        reason: str,
        delta_before: float = None,
        delta_after: float = None
    ):
        """
        Log when you ADJUST a trade
        
        This captures WHY you adjusted and what changed
        """
        print(f"\n{'='*80}")
        print(f"LOGGING: Trade Adjustment - {underlying}")
        print(f"{'='*80}")
        
        try:
            with session_scope() as session:
                event_repo = EventRepository(session)
                portfolio_repo = PortfolioRepository(session)
                
                # Get current state
                portfolio = portfolio_repo.get_all_portfolios()[0]
                
                # Build context
                market_context = events.MarketContext(
                    underlying_symbol=underlying,
                    timestamp=datetime.utcnow()
                )
                
                decision_context = events.DecisionContext(
                    rationale=reason
                )
                
                # Create adjustment event
                event = events.TradeEvent(
                    event_type=events.EventType.TRADE_ADJUSTED,
                    trade_id=f"adj_{underlying}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                    market_context=market_context,
                    decision_context=decision_context,
                    underlying_symbol=underlying,
                    tags=[adjustment_type, underlying]
                )
                
                # Save
                created = event_repo.create_from_domain(event)
                
                if created:
                    print(f"\n✅ Adjustment logged!")
                    print(f"  Type: {adjustment_type}")
                    print(f"  Reason: {reason}")
                    if delta_before and delta_after:
                        print(f"  Delta change: {delta_before:.2f} → {delta_after:.2f}")
                else:
                    print("❌ Failed to log adjustment")
                    return False
                
                return True
                
        except Exception as e:
            print(f"❌ Error logging adjustment: {e}")
            logger.exception("Full error:")
            return False
    
    def list_open_trades(self):
        """List all trades waiting for outcome"""
        print(f"\n{'='*80}")
        print(f"OPEN TRADES (Waiting for Outcome)")
        print(f"{'='*80}\n")
        
        try:
            with session_scope() as session:
                event_repo = EventRepository(session)
                
                # Get all open trade events (no outcome)
                events_list = event_repo.get_events_for_learning(min_events=0)
                
                # Filter to only opens without outcomes
                open_events = [
                    e for e in events_list 
                    if e.event_type == events.EventType.TRADE_OPENED and not e.outcome
                ]
                
                if not open_events:
                    print("No open trades found.")
                    print("\n💡 Log a new trade with:")
                    print("   python -m cli.log_event open-trade --underlying SPY --strategy 'iron_condor' ...")
                    return
                
                for event in open_events:
                    days_open = (datetime.utcnow() - event.timestamp).days
                    print(f"📊 {event.underlying_symbol} - {event.strategy_type}")
                    print(f"   Event ID: {event.event_id}")
                    print(f"   Opened: {event.timestamp.strftime('%Y-%m-%d')} ({days_open} days ago)")
                    print(f"   Rationale: {event.decision_context.rationale}")
                    print(f"   Confidence: {event.decision_context.confidence_level}/10")
                    print(f"   Entry Delta: {event.entry_delta:.2f}")
                    print(f"\n   To close: python -m cli.log_event close-trade --event-id {event.event_id}")
                    print()
                
        except Exception as e:
            print(f"❌ Error listing trades: {e}")
            logger.exception("Full error:")


def main():
    """Main CLI entry point"""
    setup_logging()
    
    parser = argparse.ArgumentParser(
        description="Log trading events for AI learning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Log opening a trade
  python -m cli.log_event open-trade --underlying SPY --strategy iron_condor \\
    --rationale "IV rank 75, expecting mean reversion" \\
    --outlook neutral --confidence 8 --risk 500

  # Log closing a trade
  python -m cli.log_event close-trade --event-id abc123 \\
    --pnl 250 --reason "Hit 50%% profit target" \\
    --went-right "Theta decay as expected"

  # Log adjustment
  python -m cli.log_event adjust --underlying IWM \\
    --type roll --reason "Delta breach, rolled to next month"

  # List open trades
  python -m cli.log_event list
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Open trade command
    open_parser = subparsers.add_parser('open-trade', help='Log opening a new trade')
    open_parser.add_argument('--underlying', required=True, help='Underlying symbol (e.g., SPY)')
    open_parser.add_argument('--strategy', required=True, help='Strategy type (e.g., iron_condor)')
    open_parser.add_argument('--rationale', required=True, help='Why are you entering this trade?')
    open_parser.add_argument('--outlook', required=True, choices=['bullish', 'bearish', 'neutral', 'uncertain'], 
                           help='Market outlook')
    open_parser.add_argument('--confidence', type=int, required=True, choices=range(1, 11),
                           help='Confidence level 1-10')
    open_parser.add_argument('--risk', type=float, required=True, help='Risk amount ($)')
    open_parser.add_argument('--profit-target', type=float, help='Profit target (percent)')
    open_parser.add_argument('--max-loss', type=float, help='Max loss (percent)')
    
    # Close trade command
    close_parser = subparsers.add_parser('close-trade', help='Log closing a trade')
    close_parser.add_argument('--event-id', required=True, help='Event ID from open-trade')
    close_parser.add_argument('--pnl', type=float, required=True, help='Final P&L ($)')
    close_parser.add_argument('--reason', required=True, help='Why did you close?')
    close_parser.add_argument('--days', type=int, help='Days held (auto-calculated if omitted)')
    close_parser.add_argument('--met-expectations', action='store_true', default=True,
                            help='Did trade meet expectations?')
    close_parser.add_argument('--went-right', default='', help='What went right?')
    close_parser.add_argument('--went-wrong', default='', help='What went wrong?')
    close_parser.add_argument('--differently', default='', help='What would you do differently?')
    
    # Adjustment command
    adj_parser = subparsers.add_parser('adjust', help='Log trade adjustment')
    adj_parser.add_argument('--underlying', required=True, help='Underlying symbol')
    adj_parser.add_argument('--type', required=True, help='Adjustment type (roll, hedge, add_leg)')
    adj_parser.add_argument('--reason', required=True, help='Why adjusting?')
    adj_parser.add_argument('--delta-before', type=float, help='Delta before adjustment')
    adj_parser.add_argument('--delta-after', type=float, help='Delta after adjustment')
    
    # List command
    subparsers.add_parser('list', help='List open trades waiting for outcome')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    logger = EventLogger()
    
    if args.command == 'open-trade':
        success = logger.log_trade_open(
            underlying=args.underlying,
            strategy=args.strategy,
            rationale=args.rationale,
            market_outlook=args.outlook,
            confidence=args.confidence,
            risk_amount=args.risk,
            profit_target_pct=args.profit_target,
            max_loss_pct=args.max_loss
        )
    elif args.command == 'close-trade':
        success = logger.log_trade_close(
            event_id=args.event_id,
            final_pnl=args.pnl,
            close_reason=args.reason,
            days_held=args.days,
            met_expectations=args.met_expectations,
            what_went_right=args.went_right,
            what_went_wrong=args.went_wrong,
            would_do_differently=args.differently
        )
    elif args.command == 'adjust':
        success = logger.log_adjustment(
            underlying=args.underlying,
            adjustment_type=args.type,
            reason=args.reason,
            delta_before=args.delta_before,
            delta_after=args.delta_after
        )
    elif args.command == 'list':
        logger.list_open_trades()
        success = True
    else:
        parser.print_help()
        return 1
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())