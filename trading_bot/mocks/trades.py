# mocks/trades.py
from domain.models import Trade

MOCK_TRADES = [
    Trade(
        trade_id="IC1",
        symbol="SPY",
        strategy="IRON_CONDOR",
        risk_type="DEFINED",
        credit=350,
        max_loss=1650,
        delta=5,
        dte=45,
        sector="INDEX"
    ),
    Trade(
        trade_id="CSP1",
        symbol="AAPL",
        strategy="CSP",
        risk_type="UNDEFINED",
        credit=420,
        max_loss=4800,      # modeled
        delta=-25,
        dte=38,
        sector="TECH"
    ),
    Trade(
        trade_id="VERT1",
        symbol="MSFT",
        strategy="VERTICAL",
        risk_type="DEFINED",
        credit=180,
        max_loss=820,
        delta=18,
        dte=30,
        sector="TECH"
    ),
]
