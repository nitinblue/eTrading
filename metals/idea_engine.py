# metals/idea_engine.py

from typing import List

from metals.option_models import TradeIdea
from metals.option_chain import fetch_option_chain
from metals.idea_generators import (
    generate_leaps,
    generate_diagonal,
    generate_calendar,
)


async def generate_all_ideas(symbol: str, price: float, session) -> List[TradeIdea]:
    """
    Master idea generator.
    Always returns TradeIdea objects (even if verdict is WAIT / AVOID).
    """

    ideas: List[TradeIdea] = []

    chain = await fetch_option_chain(symbol, session)

    if not chain:
        return [
            TradeIdea(
                underlying=symbol,
                strategy="NO_OPTIONS",
                legs=[],
                verdict="AVOID",
                why=["No option chain available"],
                notes=["Underlying has no usable options"]
            )
        ]

    ideas.append(await generate_leaps(symbol, price, chain, session))
    ideas.append(await generate_diagonal(symbol, price, chain, session))
    ideas.append(await generate_calendar(symbol, price, chain, session))

    # Filter out None just in case
    return [idea for idea in ideas if idea is not None]
