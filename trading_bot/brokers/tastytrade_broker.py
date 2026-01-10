import logging
from tastytrade import Session
from tastytrade.account import Account

logger = logging.getLogger(__name__)


class TastytradeBroker:
    def __init__(self, broker_config: dict):
        general = broker_config["general"]
        broker = broker_config["broker"]

        mode = general.get("execution_mode", "live")
        is_paper = general.get("is_paper", False)

        creds = broker["paper"] if is_paper else broker["live"]

        self.client_secret = creds["client_secret"]
        self.refresh_token = creds["refresh_token"]
        self.is_paper = is_paper

        self.session = None
        self.accounts = {}

    def connect(self):
        try:
            logger.info(
                f"Connecting to Tastytrade | "
                f"{'PAPER' if self.is_paper else 'LIVE'}"
            )

            # ✅ EXACT SAME AS YOUR WORKING main.py
            self.session = Session(
                self.client_secret,
                self.refresh_token,
                is_test=self.is_paper
            )

            accounts = Account.get(self.session)
            self.accounts = {
                acc.account_number: acc for acc in accounts
            }

            logger.info(f"Loaded {len(self.accounts)} account(s)")

        except Exception:
            logger.exception("Tastytrade connection failed")
            raise

    # ------------------------------------------------------------------
    # SAFE ACCESSORS (never throw)
    # ------------------------------------------------------------------

    def get_positions(self):
        if not self.account:
            logger.warning("MOCK positions returned")
            return []

        try:
            return list(self.account.get_positions())
        except Exception as e:
            logger.error("Failed to fetch positions, MOCK used: %s", e)
            return []

    def get_net_liquidation(self) -> Decimal:
        if not self.account:
            return Decimal(self.config["mock"]["net_liquidation"])

        try:
            return Decimal(str(self.account.net_liquidation_value))
        except Exception as e:
            logger.error("Failed net liq, MOCK used: %s", e)
            return Decimal(self.config["mock"]["net_liquidation"])

    def get_buying_power(self) -> Decimal:
        if not self.account:
            return Decimal(self.config["mock"]["buying_power"])

        try:
            return Decimal(str(self.account.buying_power))
        except Exception as e:
            logger.error("Failed BP, MOCK used: %s", e)
            return Decimal(self.config["mock"]["buying_power"])
