"""
Event Analytics - Find patterns in your trading decisions

This is where the AI learns from your history.
"""

import logging
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict

from sqlalchemy.orm import Session
from repositories.event import EventRepository
import core.models.events as events

logger = logging.getLogger(__name__)


class EventAnalytics:
    """
    Analyze trading events to find patterns
    
    This answers questions like:
    - Do I close winners too early?
    - What's my win rate by strategy?
    - When do I typically adjust positions?
    """
    
    def __init__(self, session: Session):
        self.session = session
        self.event_repo = EventRepository(session)
    
    def get_trade_summary(self, days: int = 30) -> Dict:
        """
        Get summary of trading activity
        
        Returns:
            Dict with win rate, avg P&L, trade count, etc.
        """
        try:
            # Get completed trades
            all_events = self.event_repo.get_events_for_learning(min_events=0)
            
            # Filter to last N days
            cutoff = datetime.utcnow() - timedelta(days=days)
            recent_events = [e for e in all_events if e.timestamp >= cutoff]
            
            # Get opens and closes
            opens = [e for e in recent_events if e.event_type == events.EventType.TRADE_OPENED]
            closes = [e for e in recent_events if e.event_type == events.EventType.TRADE_CLOSED]
            completed = [e for e in opens if e.outcome]
            
            if not completed:
                return {
                    'message': f'No completed trades in last {days} days',
                    'trades_opened': len(opens),
                    'trades_closed': len(closes)
                }
            
            # Calculate stats
            wins = [e for e in completed if e.outcome.outcome == events.TradeOutcome.WIN]
            losses = [e for e in completed if e.outcome.outcome == events.TradeOutcome.LOSS]
            
            total_pnl = sum(float(e.outcome.final_pnl) for e in completed)
            avg_pnl = total_pnl / len(completed)
            
            avg_winner = sum(float(e.outcome.final_pnl) for e in wins) / len(wins) if wins else 0
            avg_loser = sum(float(e.outcome.final_pnl) for e in losses) / len(losses) if losses else 0
            
            avg_days_held = sum(e.outcome.days_held for e in completed) / len(completed)
            
            return {
                'period_days': days,
                'total_trades': len(completed),
                'wins': len(wins),
                'losses': len(losses),
                'win_rate': (len(wins) / len(completed) * 100) if completed else 0,
                'total_pnl': total_pnl,
                'avg_pnl': avg_pnl,
                'avg_winner': avg_winner,
                'avg_loser': avg_loser,
                'profit_factor': abs(avg_winner / avg_loser) if avg_loser != 0 else 0,
                'avg_days_held': avg_days_held
            }
            
        except Exception as e:
            logger.error(f"Error calculating trade summary: {e}")
            return {}
    
    def analyze_by_strategy(self) -> Dict[str, Dict]:
        """
        Analyze performance by strategy type
        
        Returns:
            Dict mapping strategy -> stats
        """
        try:
            events_list = self.event_repo.get_events_for_learning(min_events=0)
            completed = [e for e in events_list if e.outcome]
            
            # Group by strategy
            by_strategy = defaultdict(list)
            for event in completed:
                by_strategy[event.strategy_type].append(event)
            
            results = {}
            for strategy, strategy_events in by_strategy.items():
                wins = [e for e in strategy_events if e.outcome.outcome == events.TradeOutcome.WIN]
                
                results[strategy] = {
                    'count': len(strategy_events),
                    'wins': len(wins),
                    'win_rate': (len(wins) / len(strategy_events) * 100) if strategy_events else 0,
                    'avg_pnl': sum(float(e.outcome.final_pnl) for e in strategy_events) / len(strategy_events),
                    'total_pnl': sum(float(e.outcome.final_pnl) for e in strategy_events)
                }
            
            return results
            
        except Exception as e:
            logger.error(f"Error analyzing by strategy: {e}")
            return {}
    
    def analyze_by_confidence(self) -> Dict[str, Dict]:
        """
        Analyze if your confidence level predicts success
        
        Returns:
            Dict showing win rate by confidence bracket
        """
        try:
            events_list = self.event_repo.get_events_for_learning(min_events=0)
            completed = [e for e in events_list if e.outcome and e.decision_context]
            
            # Group by confidence level
            confidence_brackets = {
                'low (1-4)': [],
                'medium (5-7)': [],
                'high (8-10)': []
            }
            
            for event in completed:
                conf = event.decision_context.confidence_level
                if conf <= 4:
                    confidence_brackets['low (1-4)'].append(event)
                elif conf <= 7:
                    confidence_brackets['medium (5-7)'].append(event)
                else:
                    confidence_brackets['high (8-10)'].append(event)
            
            results = {}
            for bracket, bracket_events in confidence_brackets.items():
                if not bracket_events:
                    continue
                
                wins = [e for e in bracket_events if e.outcome.outcome == events.TradeOutcome.WIN]
                
                results[bracket] = {
                    'count': len(bracket_events),
                    'win_rate': (len(wins) / len(bracket_events) * 100),
                    'avg_pnl': sum(float(e.outcome.final_pnl) for e in bracket_events) / len(bracket_events)
                }
            
            return results
            
        except Exception as e:
            logger.error(f"Error analyzing by confidence: {e}")
            return {}
    
    def find_early_exits(self, dte_threshold: int = 21) -> List[events.TradeEvent]:
        """
        Find trades closed before DTE threshold
        
        Helps answer: "Do I close winners too early?"
        """
        try:
            events_list = self.event_repo.get_events_for_learning(min_events=0)
            
            early_exits = []
            for event in events_list:
                if event.outcome and event.outcome.days_held:
                    # Estimate DTE at close (rough)
                    # If trade was opened at 45 DTE and held 10 days, closed at ~35 DTE
                    if event.outcome.days_held < (45 - dte_threshold):
                        early_exits.append(event)
            
            return early_exits
            
        except Exception as e:
            logger.error(f"Error finding early exits: {e}")
            return []
    
    def analyze_adjustment_patterns(self) -> Dict:
        """
        Analyze when and why you adjust trades
        
        Returns insights about adjustment behavior
        """
        try:
            # Get all adjustment events
            adjustments = self.event_repo.get_by_type(events.EventType.TRADE_ADJUSTED)
            
            if not adjustments:
                return {'message': 'No adjustments logged yet'}
            
            # Group by reason keywords
            reason_keywords = defaultdict(int)
            for adj in adjustments:
                reason = adj.decision_context.rationale.lower()
                if 'delta' in reason:
                    reason_keywords['delta_breach'] += 1
                if 'roll' in reason:
                    reason_keywords['rolling'] += 1
                if 'profit' in reason:
                    reason_keywords['profit_taking'] += 1
                if 'loss' in reason or 'stop' in reason:
                    reason_keywords['stop_loss'] += 1
            
            return {
                'total_adjustments': len(adjustments),
                'reasons': dict(reason_keywords),
                'avg_per_month': len(adjustments) / max(1, (datetime.utcnow() - adjustments[0].timestamp).days / 30)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing adjustments: {e}")
            return {}
    
    def get_learning_insights(self) -> Dict:
        """
        Get insights for machine learning
        
        Returns patterns that could be trained on
        """
        try:
            events_list = self.event_repo.get_events_for_learning(min_events=5)
            
            if len(events_list) < 5:
                return {
                    'message': f'Need at least 5 completed trades. Current: {len(events_list)}',
                    'suggestion': 'Keep logging trades to build up training data'
                }
            
            insights = {
                'data_available': True,
                'training_samples': len(events_list),
                'patterns_detected': []
            }
            
            # Pattern 1: Confidence calibration
            conf_analysis = self.analyze_by_confidence()
            if conf_analysis:
                high_conf = conf_analysis.get('high (8-10)', {})
                if high_conf.get('win_rate', 0) < 60:
                    insights['patterns_detected'].append({
                        'pattern': 'overconfidence',
                        'description': 'High confidence trades underperforming',
                        'recommendation': 'Review what makes you confident - may need recalibration'
                    })
            
            # Pattern 2: Strategy effectiveness
            strategy_analysis = self.analyze_by_strategy()
            if strategy_analysis:
                best_strategy = max(strategy_analysis.items(), key=lambda x: x[1]['win_rate'])
                worst_strategy = min(strategy_analysis.items(), key=lambda x: x[1]['win_rate'])
                
                insights['patterns_detected'].append({
                    'pattern': 'strategy_variance',
                    'description': f"Best: {best_strategy[0]} ({best_strategy[1]['win_rate']:.1f}%), Worst: {worst_strategy[0]} ({worst_strategy[1]['win_rate']:.1f}%)",
                    'recommendation': f"Focus on {best_strategy[0]}"
                })
            
            # Pattern 3: Hold time
            completed = [e for e in events_list if e.outcome]
            if completed:
                avg_hold = sum(e.outcome.days_held for e in completed) / len(completed)
                winners = [e for e in completed if e.outcome.outcome == events.TradeOutcome.WIN]
                losers = [e for e in completed if e.outcome.outcome == events.TradeOutcome.LOSS]
                
                avg_hold_winners = sum(e.outcome.days_held for e in winners) / len(winners) if winners else 0
                avg_hold_losers = sum(e.outcome.days_held for e in losers) / len(losers) if losers else 0
                
                if avg_hold_winners < avg_hold_losers:
                    insights['patterns_detected'].append({
                        'pattern': 'early_profit_taking',
                        'description': f"Winners held {avg_hold_winners:.0f} days, losers {avg_hold_losers:.0f} days",
                        'recommendation': 'Consider letting winners run longer'
                    })
            
            return insights
            
        except Exception as e:
            logger.error(f"Error getting learning insights: {e}")
            return {}


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    from config.settings import setup_logging
    from core.database.session import session_scope
    
    setup_logging()
    
    with session_scope() as session:
        analytics = EventAnalytics(session)
        
        print("\n" + "="*80)
        print("EVENT ANALYTICS")
        print("="*80)
        
        # Trade summary
        summary = analytics.get_trade_summary(days=30)
        if summary:
            print("\n📊 Last 30 Days:")
            print(f"  Trades: {summary.get('total_trades', 0)}")
            print(f"  Win Rate: {summary.get('win_rate', 0):.1f}%")
            print(f"  Total P&L: ${summary.get('total_pnl', 0):,.2f}")
            print(f"  Avg P&L: ${summary.get('avg_pnl', 0):,.2f}")
        
        # By strategy
        by_strategy = analytics.analyze_by_strategy()
        if by_strategy:
            print("\n📈 By Strategy:")
            for strategy, stats in by_strategy.items():
                print(f"  {strategy}:")
                print(f"    Trades: {stats['count']}, Win Rate: {stats['win_rate']:.1f}%, P&L: ${stats['total_pnl']:,.2f}")
        
        # Learning insights
        insights = analytics.get_learning_insights()
        if insights.get('patterns_detected'):
            print("\n🧠 Patterns Detected:")
            for pattern in insights['patterns_detected']:
                print(f"  • {pattern['pattern']}: {pattern['description']}")
                print(f"    → {pattern['recommendation']}")