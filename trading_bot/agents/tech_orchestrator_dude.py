import logging
from langgraph.graph import StateGraph, END
from trading_bot.domain.state import TradingState
from trading_bot.agents.market_news_dude import market_news_dude
from trading_bot.agents.portfolio_dude import portfolio_dude
from trading_bot.agents.risk_dude import risk_dude
from trading_bot.agents.trader_dude import trader_dude

logger = logging.getLogger(__name__)


def build_graph():
    graph = StateGraph(TradingState)

    graph.add_node("market_news", market_news_dude)
    graph.add_node("portfolio", portfolio_dude)
    graph.add_node("risk", risk_dude)
    graph.add_node("trader", trader_dude)

    graph.set_entry_point("market_news")

    graph.add_edge("market_news", "portfolio")
    graph.add_edge("portfolio", "risk")
    graph.add_edge("risk", "trader")
    graph.add_edge("trader", END)

    return graph.compile()


def run_trading_graph(state: TradingState):
    logger.info("🧠 Invoking LangGraph")
    graph = build_graph()
    graph.invoke(state)
