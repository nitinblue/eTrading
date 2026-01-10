# main.py
import logging
from trading_bot.config import Config
from trading_bot.config_folder.loader import load_all_configs
from trading_bot.services.portfolio_builder import build_portfolio
from trading_bot.services.risk_service import run_risk_check
from trading_bot.services.what_if_service import run_what_if, build_what_if_trade
from trading_bot.domain.models import Trade


# remove later and connect to brokers.broker_factory.create_broker
from trading_bot.brokers.tastytrade_broker import TastytradeBroker

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # 1️⃣ Load configs
    configs = load_all_configs()


    #broker = create_broker(config, broker_name=broker_name, mode=mode)
    #broker.connect()
    #logger.info(f"Execution broker: {mode.upper()} account")
    #return broker   
    
    # loading the old way, switch to load_all_configs later as i have split configs
    config = Config.load('config.yaml')
    mode = config.general.get('execution_mode', 'mock').lower()

    creds_key = 'paper' if mode == 'paper' else 'live'
    creds = config.broker[creds_key]
    
    broker = TastytradeBroker(
        client_secret=creds['client_secret'],
        refresh_token=creds['refresh_token'],
        is_paper=(mode == 'paper')
    )
    broker.connect()
    logger.info(f"Execution broker: {mode.upper()} account")


    # 2️⃣ Get positions from tastytrade broker
    tasty_positions = broker.get_positions()

    # 3️⃣ Build portfolio
    portfolio = build_portfolio(
        tasty_positions,
        realized_pnl=broker.get_realized_pnl(),
        unrealized_pnl=broker.get_unrealized_pnl('day')
    )
    
    mockPortfolio = build_portfolio(
        [
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
                sector="TECH",
            ),
        ],
        realized_pnl=0,
        unrealized_pnl=0
    )
    
    # remove later temp hack to use mock portfolio for testing
    portfolio = mockPortfolio
    # remove.

    logger.info(f"Built portfolio with {len(portfolio)} trades")
    
    # 4️⃣ Run live risk check
    risk_snapshot = run_risk_check(portfolio, configs)

    # 5️⃣ Run what-if
    what_if_trade = build_what_if_trade()
    what_if_result = run_what_if(portfolio, what_if_trade, configs)

    if what_if_result["violations"]:
        print("❌ Trade REJECTED")
    else:
        print("✅ Trade APPROVED")

if __name__ == "__main__":
    main()
