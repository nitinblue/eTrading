import logging
from langgraph.graph import StateGraph, END

from trading_bot.agents.market_news_dude import market_news_dude
from trading_bot.agents.portfolio_dude import portfolio_dude
from trading_bot.agents.risk_dude import trade_defined_risk, trade_undefined_risk
from trading_bot.agents.trade_ranking_dude import rank_trades
from trading_bot.agents.adjustment_dude import adjustment_dude

logger = logging.getLogger(__name__)


def build_trading_graph():
    """
    TECH ORCHESTRATOR AGENT

    Responsibilities:
    - Defines how agents collaborate
    - Owns LangGraph structure
    - Defines state transitions
    - Enforces agent ordering

    Does NOT:
    - Load config
    - Connect brokers
    - Execute main()
    """

    graph = StateGraph(dict)

    # ---- Agent Nodes ----
    graph.add_node("market_news", market_news_dude)
    graph.add_node("portfolio", portfolio_dude)
    graph.add_node("risk", trade_defined_risk)
    graph.add_node("ranking", rank_trades)
    graph.add_node("adjustments", adjustment_dude)

    # ---- Entry Point ----
    graph.set_entry_point("market_news")

    # ---- Flow Definition ----
    graph.add_edge("market_news", "portfolio")
    graph.add_edge("portfolio", "risk")
    graph.add_edge("risk", "ranking")
    graph.add_edge("ranking", "adjustments")
    graph.add_edge("adjustments", END)

    logger.info("TechOrchestrator graph built successfully")

    return graph.compile()
