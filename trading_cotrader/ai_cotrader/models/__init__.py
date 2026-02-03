"""
Trained Models Storage

This folder stores trained ML models:
- supervised.pkl: Pattern recognizer trained on your history
- rl_agent.pkl: Q-learning agent
- dqn_agent.pkl: Deep Q-Network (if using)

Models are saved/loaded by TradingAdvisor:

    from ai_cotrader import TradingAdvisor
    
    advisor = TradingAdvisor()
    
    # Save after training
    advisor.save('ai_cotrader/models/')
    
    # Load for inference
    advisor.load('ai_cotrader/models/')
"""

import os
from pathlib import Path

# Ensure models directory exists
MODELS_DIR = Path(__file__).parent
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Subdirectory for trained models
TRAINED_DIR = MODELS_DIR / 'trained'
TRAINED_DIR.mkdir(parents=True, exist_ok=True)


def get_model_path(model_name: str) -> Path:
    """Get path for a model file"""
    return TRAINED_DIR / f"{model_name}.pkl"


def list_models() -> list:
    """List all saved models"""
    return [f.stem for f in TRAINED_DIR.glob('*.pkl')]
