# metals/idea_generators.py

from metals.option_models import TradeIdea, OptionSnapshot


async def generate_leaps(symbol, price, chain, session) -> TradeIdea:
    """
    Long-term bullish exposure using deep-dated calls.
    """

    return TradeIdea(
        underlying=symbol,
        strategy="LEAPS",
        legs=[],
        verdict="WAIT",
        why=[
            "Placeholder LEAPS strategy",
            "Waiting for pullback / better IV"
        ],
        notes=[
            "LEAPS are best entered on pullbacks",
            "High RSI makes timing unfavorable"
        ]
    )


async def generate_diagonal(symbol, price, chain, session) -> TradeIdea:
    """
    Long call + short near-term call.
    """

    return TradeIdea(
        underlying=symbol,
        strategy="DIAGONAL",
        legs=[],
        verdict="WAIT",
        why=[
            "Placeholder diagonal strategy",
            "Short leg unattractive with current skew"
        ],
        notes=[
            "Diagonals work best in slow uptrends",
            "Needs better short-dated premium"
        ]
    )


async def generate_calendar(symbol, price, chain, session) -> TradeIdea:
    """
    Same strike, different expiries.
    """

    return TradeIdea(
        underlying=symbol,
        strategy="CALENDAR",
        legs=[],
        verdict="WAIT",
        why=[
            "Placeholder calendar strategy",
            "IV term structure not favorable"
        ],
        notes=[
            "Calendars benefit from IV expansion",
            "Not ideal in strong directional moves"
        ]
    )
