# trading_bot/strategy_screener.py
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class StrategyScreener:
    def __init__(self, config, broker_session):
        # config is Pydantic Config object — use attribute access
        self.strategies_config = getattr(config, 'strategies', {})
        self.broker_session = broker_session
        self.defined = self.strategies_config.get('defined', {})
        self.undefined = self.strategies_config.get('undefined', {})

    def run_all_screeners(self, underlyings: List[str]):
        logger.info("\n=== STRATEGY SCREENER RESULTS ===")
        logger.info(f"Defined Risk Allocation: {self.strategies_config.get('allocation_defined', 0.8):.0%}")
        logger.info(f"Undefined Risk Allocation: {self.strategies_config.get('allocation_undefined', 0.2):.0%}")

        logger.info("\nDefined Risk Strategies:")
        for name, strat in self.defined.items():
            logger.info(f"  {strat.get('name', name)}: {strat.get('description', '')}")
            logger.info(f"    Criteria: IV Rank > {strat.get('min_iv_rank', 'N/A')}, DTE < {strat.get('max_dte', 'N/A')}")
            suggestions = self.screen_for_strategy(name, underlyings)
            for sug in suggestions:
                logger.info(f"    → {sug['symbol']} (IV Rank: {sug['iv_rank']}%)")

        logger.info("\nUndefined Risk Strategies:")
        for name, strat in self.undefined.items():
            logger.info(f"  {strat.get('name', name)}: {strat.get('description', '')}")
            logger.info(f"    Criteria: IV Rank > {strat.get('min_iv_rank', 'N/A')}, DTE < {strat.get('max_dte', 'N/A')}")
            suggestions = self.screen_for_strategy(name, underlyings)
            for sug in suggestions:
                logger.info(f"    → {sug['symbol']} (IV Rank: {sug['iv_rank']}%)")

    def screen_for_strategy(self, strategy_name: str, underlyings: List[str]) -> List[Dict]:
        # Simulated — replace with real data later
        suggestions = []
        for symbol in underlyings:
            if "iron_condor" in strategy_name and symbol in ["SPY", "QQQ"]:
                suggestions.append({"symbol": symbol, "iv_rank": 62})
            elif "short_strangle" in strategy_name and symbol in ["TSLA"]:
                suggestions.append({"symbol": symbol, "iv_rank": 75})
        return suggestions