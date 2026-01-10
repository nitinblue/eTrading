from typing import Dict
from langgraph.graph import StateGraph, END

from trading_bot.agents.state import TradingState
from trading_bot.agents.market_news_dude import market_news_dude
from trading_bot.agents.portfolio_dude import portfolio_dude
from trading_bot.agents.trader_dude import trader_dude
from trading_bot.agents.risk_dude import risk_dude
from trading_bot.agents.adjustment_dude import adjustment_dude


def build_graph():
    graph = StateGraph(TradingState)

    graph.add_node("market_news", market_news_dude)
    graph.add_node("portfolio", portfolio_dude)
    graph.add_node("trader", trader_dude)
    graph.add_node("risk", risk_dude)
    graph.add_node("adjustment", adjustment_dude)

    graph.set_entry_point("market_news")

    graph.add_edge("market_news", "portfolio")
    graph.add_edge("portfolio", "trader")
    graph.add_edge("trader", "risk")

    graph.add_conditional_edges(
        "risk",
        route_after_risk,
        {
            "loop": "portfolio",
            "adjust": "adjustment",
            "done": END,
        },
    )

    graph.add_edge("adjustment", END)

    return graph.compile()


def route_after_risk(state: Dict) -> str:
    if state.get("risk_hard_stop"):
        return "done"

    if state.get("needs_adjustment"):
        return "adjust"

    if not state.get("proposed_trade"):
        return "done"

    if state.get("risk_remaining", 0) > 0:
        return "loop"

    return "done"
