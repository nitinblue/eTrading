"""
ML Data Pipeline - Bridge between your data and ML training

This connects:
- SnapshotService (daily portfolio snapshots) → Training features
- EventLogger (trade decisions) → Training labels
- EventAnalytics (patterns) → Pattern recognition

Usage:
    # In auto_trader or a scheduled job:
    from ai_cotrader.data_pipeline import MLDataPipeline
    
    pipeline = MLDataPipeline(session)
    
    # After each sync/snapshot
    pipeline.accumulate_training_data(portfolio, positions)
    
    # When ready to train (100+ samples)
    if pipeline.get_sample_count() >= 100:
        X, y = pipeline.get_training_dataset()
        model.fit(X, y)
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
import numpy as np

from sqlalchemy.orm import Session
from trading_cotrader.repositories.portfolio import PortfolioRepository
from trading_cotrader.config.settings import setup_logging
from trading_cotrader.core.database.session import session_scope
from trading_cotrader.core.database.schema import DailyPerformanceORM, TradeEventORM

from trading_cotrader.ai_cotrader.feature_engineering import FeatureExtractor, DatasetBuilder
from trading_cotrader.repositories.event import EventRepository
import trading_cotrader.core.models.events as events
from trading_cotrader.core.database.schema import GreeksHistoryORM
from trading_cotrader.ai_cotrader.learning.supervised import ActionLabels
from trading_cotrader.services.snapshot_service import SnapshotService
logger = logging.getLogger(__name__)


class MLDataPipeline:
    """
    Bridges your existing services to ML training.
    
    Data Sources:
    1. DailyPerformanceORM (from SnapshotService) → Portfolio features
    2. GreeksHistoryORM (from SnapshotService) → Position features
    3. TradeEventORM (from EventLogger) → Market context + labels
    4. EventAnalytics patterns → Additional features
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    def accumulate_training_data(
        self,
        portfolio,
        positions: List,
        market_data: Dict = None
    ) -> bool:
        """
        Called after each sync/snapshot to accumulate ML training data.
        
        This is automatic - just call it and data builds up over time.
        
        Args:
            portfolio: Current portfolio state
            positions: Current positions
            market_data: Optional additional market data (VIX, etc.)
            
        Returns:
            True if data accumulated successfully
        """
        try:
            # Step 1: Ensure daily snapshot exists
            # Workflow engine calls capture_all_portfolio_snapshots() before this.
            # If snapshot is missing, capture via ORM-direct method.

            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

            existing = self.session.query(DailyPerformanceORM).filter_by(
                portfolio_id=portfolio.id,
                date=today
            ).first()

            if not existing:
                snapshot_svc = SnapshotService(self.session)
                snapshot_svc.capture_all_portfolio_snapshots()
                logger.info("ML Pipeline: Captured daily snapshots via ORM")
            
            # Step 2: Extract and store ML features
            # (We could create a separate MLFeatureORM, but for now
            # the snapshot data is sufficient)
            
            logger.info(f"ML Pipeline: Data accumulated for {today.date()}")
            return True
            
        except Exception as e:
            logger.error(f"ML Pipeline accumulation error: {e}")
            return False
    
    def get_sample_count(self) -> int:
        """Get number of training samples available"""
        try:
            
            
            snapshots = self.session.query(DailyPerformanceORM).count()
            events = self.session.query(TradeEventORM).count()
            
            # For supervised learning, we need events with outcomes
            events_with_outcomes = self.session.query(TradeEventORM).filter(
                TradeEventORM.outcome.isnot(None)
            ).count()
            
            logger.info(f"ML Pipeline: {snapshots} snapshots, {events} events, {events_with_outcomes} with outcomes")
            
            return events_with_outcomes
            
        except Exception as e:
            logger.error(f"Error getting sample count: {e}")
            return 0
    
    def get_training_dataset(
        self,
        min_samples: int = 10,
        days: int = 365
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Build training dataset from accumulated data.
        
        Returns:
            X: Feature matrix (n_samples, n_features)
            y: Labels (n_samples,) - action taken or outcome
        """
        try:

            
            # Get events with outcomes
            event_repo = EventRepository(self.session)
            training_events = event_repo.get_events_for_learning(min_events=min_samples)
            
            if len(training_events) < min_samples:
                logger.warning(f"Only {len(training_events)} samples, need {min_samples}")
                return np.array([]), np.array([])
            
            # Build dataset
            extractor = FeatureExtractor()
            builder = DatasetBuilder()
            
            for event in training_events:
                # Extract state from event
                state = extractor.extract_from_event(event)
                
                # Determine action/outcome
                action = self._event_to_action_label(event)
                outcome = self._event_to_outcome(event)
                
                builder.add_event(
                    event=event,
                    action_taken=action,
                    outcome=outcome
                )
            
            X, y = builder.get_supervised_dataset()
            
            logger.info(f"ML Pipeline: Built dataset with {len(X)} samples, {X.shape[1]} features")
            return X, y
            
        except Exception as e:
            logger.error(f"Error building training dataset: {e}")
            return np.array([]), np.array([])
    
    def get_portfolio_features_history(
        self,
        portfolio_id: str,
        days: int = 30
    ) -> List[Dict]:
        """
        Get portfolio feature history for time-series analysis.
        
        Returns list of daily feature snapshots.
        """
        try:
            
            
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            snapshots = self.session.query(DailyPerformanceORM).filter(
                DailyPerformanceORM.portfolio_id == portfolio_id,
                DailyPerformanceORM.date >= cutoff
            ).order_by(DailyPerformanceORM.date).all()
            
            features = []
            for snap in snapshots:
                features.append({
                    'date': snap.date,
                    'total_equity': float(snap.total_equity or 0),
                    'cash_balance': float(snap.cash_balance or 0),
                    'daily_pnl': float(snap.daily_pnl or 0),
                    'unrealized_pnl': float(snap.unrealized_pnl or 0),
                    'portfolio_delta': float(snap.portfolio_delta or 0),
                    'portfolio_theta': float(snap.portfolio_theta or 0),
                    'portfolio_vega': float(snap.portfolio_vega or 0),
                    'num_positions': snap.num_positions or 0,
                })
            
            return features
            
        except Exception as e:
            logger.error(f"Error getting portfolio features: {e}")
            return []
    
    def get_position_features_history(
        self,
        position_id: str,
        days: int = 30
    ) -> List[Dict]:
        """
        Get position Greek history for analysis.
        """
        try:
            
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            history = self.session.query(GreeksHistoryORM).filter(
                GreeksHistoryORM.position_id == position_id,
                GreeksHistoryORM.timestamp >= cutoff
            ).order_by(GreeksHistoryORM.timestamp).all()
            
            features = []
            for h in history:
                features.append({
                    'timestamp': h.timestamp,
                    'delta': float(h.delta or 0),
                    'gamma': float(h.gamma or 0),
                    'theta': float(h.theta or 0),
                    'vega': float(h.vega or 0),
                    'underlying_price': float(h.underlying_price or 0),
                })
            
            return features
            
        except Exception as e:
            logger.error(f"Error getting position features: {e}")
            return []
    
    def _event_to_action_label(self, event) -> int:
        """Convert event type to action label for supervised learning"""

        
        event_type = event.event_type
        
        if event_type == events.EventType.TRADE_OPENED:
            return ActionLabels.HOLD  # Opening is implicit
        elif event_type == events.EventType.TRADE_CLOSED:
            return ActionLabels.CLOSE
        elif event_type == events.EventType.TRADE_ADJUSTED:
            return ActionLabels.ADJUST
        elif event_type == events.EventType.TRADE_ROLLED:
            return ActionLabels.ROLL
        else:
            return ActionLabels.HOLD
    
    def _event_to_outcome(self, event) -> float:
        """Extract outcome/reward from event"""
        if event.outcome:
            # Use P&L as outcome
            return float(event.outcome.final_pnl or 0)
        return 0.0
    
    def get_ml_status(self) -> Dict:
        """Get current ML data status"""
        try:

            
            snapshots = self.session.query(DailyPerformanceORM).count()
            total_events = self.session.query(TradeEventORM).count()
            events_with_outcomes = self.session.query(TradeEventORM).filter(
                TradeEventORM.outcome.isnot(None)
            ).count()
            
            return {
                'snapshots': snapshots,
                'total_events': total_events,
                'events_with_outcomes': events_with_outcomes,
                'ready_for_supervised': events_with_outcomes >= 100,
                'ready_for_rl': events_with_outcomes >= 500,
                'recommendation': self._get_recommendation(events_with_outcomes)
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _get_recommendation(self, samples: int) -> str:
        if samples < 10:
            return "Keep trading and logging events. Need 100+ for supervised learning."
        elif samples < 100:
            return f"Good progress! {100 - samples} more completed trades for supervised learning."
        elif samples < 500:
            return f"Can train supervised model! {500 - samples} more for RL."
        else:
            return "Ready for both supervised and RL training!"


# =============================================================================
# Integration Helper
# =============================================================================

def add_ml_step_to_autotrader():
    """
    Code snippet to add to auto_trader.py after snapshot step:
    
    # Add after _take_portfolio_snapshot():
    
    def _accumulate_ml_data(self):
        '''Step 2B: Accumulate ML training data'''
        print("STEP 2B: ML Data Accumulation")
        print("-" * 80)
        
        try:
            from ai_cotrader.data_pipeline import MLDataPipeline
            from repositories.position import PositionRepository
            
            with session_scope() as session:
                pipeline = MLDataPipeline(session)
                position_repo = PositionRepository(session)
                positions = position_repo.get_by_portfolio(self.portfolio.id)
                
                success = pipeline.accumulate_training_data(self.portfolio, positions)
                
                if success:
                    status = pipeline.get_ml_status()
                    print(f"✓ ML data accumulated")
                    print(f"  Snapshots: {status['snapshots']}")
                    print(f"  Events with outcomes: {status['events_with_outcomes']}")
                    print(f"  Recommendation: {status['recommendation']}")
                    return True
                else:
                    print("❌ ML data accumulation failed")
                    return False
                    
        except Exception as e:
            print(f"❌ ML error: {e}")
            return False
    """
    pass


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":

    
    setup_logging()
    
    print("=" * 80)
    print("ML DATA PIPELINE TEST")
    print("=" * 80)
    
    with session_scope() as session:
        pipeline = MLDataPipeline(session)
        
        # Get status
        status = pipeline.get_ml_status()
        
        print("\n📊 ML Data Status:")
        for key, value in status.items():
            print(f"  {key}: {value}")
        
        # Get portfolio features

        repo = PortfolioRepository(session)
        portfolios = repo.get_all_portfolios()
        
        if portfolios:
            portfolio = portfolios[0]
            
            features = pipeline.get_portfolio_features_history(portfolio.id, days=30)
            print(f"\n📈 Portfolio Feature History: {len(features)} days")
            
            if features:
                latest = features[-1]
                print(f"  Latest: {latest['date'].date()}")
                print(f"    Equity: ${latest['total_equity']:,.2f}")
                print(f"    Delta: {latest['portfolio_delta']:.2f}")
