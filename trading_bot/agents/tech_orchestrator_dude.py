# trading_bot/agents/tech_orchestrator_dude.py
"""
TechOrchestratorDude: Coordinates the full agent workflow using LangGraph.
- Fixed recursion by sequential flow: market_news → portfolio → trader_defined → trader_undefined → done.
- No loops — explicit bucket handling.
"""

from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Dict
import logging
from trading_bot.agents.market_news_dude import market_news_dude
from trading_bot.agents.portfolio_dude import portfolio_dude
from trading_bot.agents.trader_dude import trader_dude

logger = logging.getLogger(__name__)

class TradingState(TypedDict):
    input: str
    output: str
    current_bucket: str  # 'defined', 'undefined', 'done'
    config: Dict  # Config injected
    broker: any  # Broker injected

class TechOrchestratorDude:
    def __init__(self):
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(TradingState)

        # Nodes
        graph.add_node("market_news", market_news_dude)
        graph.add_node("portfolio", portfolio_dude)
        graph.add_node("trader_defined", trader_dude)
        graph.add_node("trader_undefined", trader_dude)
        graph.add_node("done", self._done_node)

        # Flow
        graph.add_edge(START, "market_news")
        graph.add_edge("market_news", "portfolio")

        # Conditional from portfolio
        def route_from_portfolio(state: TradingState):
            bucket = state.get('current_bucket', 'done')
            if bucket == 'defined':
                return "trader_defined"
            elif bucket == 'undefined':
                return "trader_undefined"
            return "done"

        graph.add_conditional_edges(
            "portfolio",
            route_from_portfolio,
            {
                "trader_defined": "trader_defined",
                "trader_undefined": "trader_undefined",
                "done": "done"
            }
        )

        # Trader nodes go to done (no loop)
        graph.add_edge("trader_defined", "trader_undefined")  # Sequential: defined then undefined
        graph.add_edge("trader_undefined", "done")
        graph.add_edge("done", END)

        return graph.compile()

    def _done_node(self, state: TradingState) -> TradingState:
        logger.info("All buckets processed — cycle complete")
        state['output'] = state.get('output', "") + "\nCycle complete: All risk buckets processed."
        return state

    def run_cycle(self, initial_state: Dict):
        result = self.graph.invoke(initial_state)
        logger.info("Cycle complete")
        return result