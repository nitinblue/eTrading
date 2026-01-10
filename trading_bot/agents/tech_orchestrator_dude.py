from langgraph.graph import StateGraph, END
from trading_bot.agents.agent_state import AgentState
from trading_bot.agents.market_news_dude import market_news_dude
from trading_bot.agents.portfolio_dude import portfolio_dude
from trading_bot.agents.risk_dude import trade_defined_risk_dude
from trading_bot.agents.risk_dude import trade_undefined_risk_dude
from trading_bot.agents.routing import route_after_portfolio


def run_trading_graph(broker, config):

    # --------------------------------------------------
    # Initial State
    # --------------------------------------------------
    state = AgentState(
        broker=broker,
        config=config
    )

    # --------------------------------------------------
    # Graph Definition
    # --------------------------------------------------
    graph = StateGraph(AgentState)

    graph.add_node("market_news", market_news_dude)
    graph.add_node("portfolio", portfolio_dude)
    graph.add_node("defined_risk_trader", trade_defined_risk_dude)
    graph.add_node("undefined_risk_trader", trade_undefined_risk_dude)

    # --------------------------------------------------
    # Edges
    # --------------------------------------------------
    graph.set_entry_point("market_news")

    graph.add_edge("market_news", "portfolio")

    graph.add_conditional_edges(
        "portfolio",
        route_after_portfolio,
        {
            "defined": "defined_risk_trader",
            "undefined": "undefined_risk_trader",
            "end": END
        }
    )

    graph.add_edge("defined_risk_trader", END)
    graph.add_edge("undefined_risk_trader", END)

    app = graph.compile()

    final_state = app.invoke(state)

    return final_state
