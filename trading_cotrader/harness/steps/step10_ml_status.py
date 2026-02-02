"""
Step 10: AI/ML Status

Wires existing ai_cotrader module:
- ai_cotrader/data_pipeline.py → MLDataPipeline
- ai_cotrader/feature_engineering → FeatureExtractor
- ai_cotrader/learning/supervised.py → PatternRecognizer
- ai_cotrader/learning/reinforcement.py → TradingAdvisor

Shows:
- ML data readiness (how many samples)
- Feature extraction status
- Model training status
- Recommendations (if models trained)
"""

import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from harness.base import (
    TestStep, StepResult, rich_table, format_currency, format_percent
)
logger = logging.getLogger(__name__)


class MLStatusStep(TestStep):
    """
    Harness step for AI/ML status and recommendations.
    
    Usage:
        python -m harness.runner
        # Step 10 will display ML status
    """
    name = "Step 10: AI/ML Status"
    description = "Harness calls AI/ML module"
    order = 10
    
    def __init__(self):
        self.pipeline = None
        self.advisor = None
    
    def run(self, context: Dict[str, Any]) -> bool:
        """
        Run ML status step.
        
        Args:
            context: Dict containing:
                - 'session': SQLAlchemy session
                - 'portfolio': dm.Portfolio
                - 'positions': List[dm.Position]
        """
        print(f"\n{'='*60}")
        print(f"STEP {self.order}: {self.name}")
        print('='*60)
        
        session = context.get('session')
        portfolio = context.get('portfolio')
        positions = context.get('positions', [])
        
        if not session:
            print("  ⚠️  No session available")
            return True
        
        # 1. Check ML data pipeline status
        print("\n1. ML Data Pipeline Status:")
        self._check_data_pipeline(session)
        
        # 2. Check feature extraction
        print("\n2. Feature Extraction:")
        self._check_feature_extraction(positions, portfolio)
        
        # 3. Check model status
        print("\n3. Model Status:")
        self._check_models()
        
        # 4. Show recommendation (if available)
        print("\n4. AI Recommendation:")
        self._get_recommendation(positions, portfolio)
        
        print(f"\n✓ {self.name} complete")
        return True
    
    def _check_data_pipeline(self, session):
        """Check ML data pipeline status"""
        try:
            from ai_cotrader.data_pipeline import MLDataPipeline
            
            self.pipeline = MLDataPipeline(session)
            status = self.pipeline.get_ml_status()
            
            print(f"    Snapshots: {status.get('snapshots', 0)}")
            print(f"    Total events: {status.get('total_events', 0)}")
            print(f"    Events with outcomes: {status.get('events_with_outcomes', 0)}")
            print(f"    Ready for supervised: {'✓' if status.get('ready_for_supervised') else '✗'} (need 100+)")
            print(f"    Ready for RL: {'✓' if status.get('ready_for_rl') else '✗'} (need 500+)")
            print(f"    → {status.get('recommendation', 'Keep trading!')}")
            
        except ImportError as e:
            print(f"    ⚠️  Could not import MLDataPipeline: {e}")
        except Exception as e:
            print(f"    ⚠️  Pipeline error: {e}")
    
    def _check_feature_extraction(self, positions, portfolio):
        """Test feature extraction on current state"""
        try:
            from ai_cotrader import FeatureExtractor, RLState
            
            extractor = FeatureExtractor()
            
            # Extract portfolio features
            if portfolio:
                portfolio_features = extractor._extract_portfolio_features(portfolio)
                print(f"    Portfolio delta: {portfolio_features.portfolio_delta:.2f}")
                print(f"    Portfolio theta: {portfolio_features.portfolio_theta:.2f}")
                print(f"    Buying power used: {portfolio_features.buying_power_used:.1%}")
            
            # Extract position features for first position
            if positions:
                pos = positions[0]
                pos_features = extractor._extract_position_features(pos)
                print(f"    Sample position ({pos.symbol.ticker}):")
                print(f"      Delta: {pos_features.position_delta:.2f}")
                print(f"      DTE: {pos_features.days_to_expiry}")
            
            # Build full RL state
            state = extractor.extract_from_event(None, positions[0] if positions else None, portfolio)
            print(f"    Feature vector size: {len(state.to_vector())}")
            
        except ImportError as e:
            print(f"    ⚠️  Could not import FeatureExtractor: {e}")
        except Exception as e:
            print(f"    ⚠️  Feature extraction error: {e}")
    
    def _check_models(self):
        """Check if models are trained and loaded"""
        try:
            from ai_cotrader import PatternRecognizer, TradingAdvisor
            from pathlib import Path
            
            # Check for saved models
            model_path = Path('models')
            
            # Pattern recognizer
            recognizer = PatternRecognizer()
            if recognizer.is_fitted:
                print("    ✓ Pattern recognizer: TRAINED")
            else:
                print("    ✗ Pattern recognizer: NOT TRAINED")
            
            # Trading advisor
            self.advisor = TradingAdvisor(supervised_model=recognizer)
            print("    ✓ Trading advisor: INITIALIZED")
            
            # Check for model files
            if model_path.exists():
                model_files = list(model_path.glob('*.pkl'))
                if model_files:
                    print(f"    Model files found: {[f.name for f in model_files]}")
                else:
                    print("    No saved model files yet")
            else:
                print("    Models directory not created yet")
                
        except ImportError as e:
            print(f"    ⚠️  Could not import models: {e}")
        except Exception as e:
            print(f"    ⚠️  Model check error: {e}")
    
    def _get_recommendation(self, positions, portfolio):
        """Get AI recommendation for current state"""
        try:
            if not self.advisor:
                print("    Advisor not available")
                return
            
            from ai_cotrader import FeatureExtractor
            
            # Build state
            extractor = FeatureExtractor()
            state = extractor.extract_from_event(
                None, 
                positions[0] if positions else None, 
                portfolio
            )
            state_vector = state.to_vector()
            
            # Get recommendation
            rec = self.advisor.recommend(
                state_vector,
                positions[0] if positions else None,
                portfolio
            )
            
            print(f"    Action: {rec.get('action', 'HOLD')}")
            print(f"    Confidence: {rec.get('confidence', 0):.2f}")
            print(f"    Source: {rec.get('source', 'rules')}")
            
            if 'reasoning' in rec:
                print(f"    Reasoning: {rec['reasoning']}")
            
        except Exception as e:
            print(f"    ⚠️  Could not get recommendation: {e}")
            print("    (This is expected until models are trained)")


# For use in harness runner
def create_step():
    return MLStatusStep()
