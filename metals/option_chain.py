# metals/option_chain.py

from datetime import datetime
from collections import defaultdict
from typing import Dict, List

from tastytrade.instruments import get_option_chain


async def fetch_option_chain(symbol: str, session) -> Dict[datetime.date, List]:
    """
    Fetch option chain from tastytrade and group by expiry date.

    Returns:
        {
            expiry_date: [Option, Option, ...]
        }
    """

    chain = await get_option_chain(session, symbol)

    if not chain or "items" not in chain:
        return {}

    grouped = defaultdict(list)

    for opt in chain["items"]:
        try:
            expiry = datetime.strptime(
                opt["expiration-date"],
                "%Y-%m-%d"
            ).date()

            grouped[expiry].append(opt)

        except Exception:
            # Skip malformed options
            continue

    return dict(grouped)
