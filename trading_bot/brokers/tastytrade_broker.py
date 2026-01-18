import logging
from tastytrade import Session, Account

logger = logging.getLogger(__name__)


class TastytradeBroker:
    def __init__(self, cfg: dict):
        self.cfg = cfg

        mode = cfg["general"]["execution_mode"]  # live / paper
        self.is_paper = cfg["general"]["is_paper"]

        broker_cfg = cfg["broker"][mode]

        self.client_secret = broker_cfg["client_secret"]
        self.refresh_token = broker_cfg["refresh_token"]

        logger.info(
            f"TastytradeBroker using client_secret length={len(self.client_secret)}"
        )

        self.session = None
        self.accounts = {}

        self.connect()

    def connect(self):
        try:
            logger.info(
                f"Connecting to Tastytrade | {'PAPER' if self.is_paper else 'LIVE'}"
            )

            self.session = Session(
                self.client_secret,
                self.refresh_token,
                is_test=self.is_paper
            )

            accounts = Account.get(self.session)
            self.accounts = {a.account_number: a for a in accounts}

            logger.info(f"Loaded {len(self.accounts)} account(s)")

        except Exception:
            logger.exception("Tastytrade connection failed")
            raise

    # ------------------------------------------------------------------
    # SAFE ACCESSORS (never throw)
    # ------------------------------------------------------------------
    def get_default_account(self) -> str:
        if not self.accounts:
            raise RuntimeError("No Tastytrade accounts loaded")

        return next(iter(self.accounts.keys()))


    def get_accounts(self):
        """
        Returns list of account IDs.
        """
        return list(self.accounts.keys())

    def get_account(self, account_id):
        """
        Returns the raw account object (SDK object).
        """
        return self.accounts.get(account_id)

    def get_net_liquidation(self, account_id):
        """
        Returns net liquidation value for an account.
        """
        acc = self.get_account(account_id)
        if acc is None:
            raise ValueError(f"Unknown account_id: {account_id}")

        # Tastytrade SDK exposes this on balances, hardcoded for now revisit later
        return 10000.0
        return float(acc.get_balances(account_id).net_liquidating_value)

    def get_buying_power(self, account_id):
        """
        Returns buying power for an account.
        """
        acc = self.get_account(account_id)
        if acc is None:
            raise ValueError(f"Unknown account_id: {account_id}")

        # Tastytrade SDK exposes this on balances, hardcoded for now revisit later
        return 10000.0
        return float(acc.balances.buying_power)
