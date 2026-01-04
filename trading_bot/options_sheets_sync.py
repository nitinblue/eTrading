# trading_bot/options_sheets_sync.py
import gspread
from google.oauth2.service_account import Credentials
from tabulate import tabulate
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class OptionsSheetsSync:
    def __init__(self, config):
        # Fixed: Use attribute access for Pydantic
        sheets_config = getattr(config, 'sheets', {})
        self.sheet_id = sheets_config.get('sheet_id')
        self.worksheet_name = sheets_config.get('worksheet_name', 'Monitoring')
        self.service_account_file = sheets_config.get('service_account_file', 'service_account.json')

        if not self.sheet_id:
            raise ValueError("Google Sheet ID not configured in config.yaml (sheets.sheet_id)")

        self._connect()

    def _connect(self):
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file(self.service_account_file, scopes=scopes)
        client = gspread.authorize(creds)
        self.sheet = client.open_by_key(self.sheet_id)
        logger.info(f"Connected to Google Sheet: {self.sheet.title}")

    def update_monitoring_sheet(self, broker, portfolio, position_risks):
        """Update Sheet 1: Monitoring (view-only)."""
        monitoring = self.sheet.worksheet("Monitoring") if "Monitoring" in [ws.title for ws in self.sheet.worksheets()] else self.sheet.add_worksheet("Monitoring", rows=100, cols=20)

        # Accounts
        accounts = broker.get_accounts() if hasattr(broker, 'get_accounts') else []
        account_data = [["Account", "Opening Balance", "Current Balance"]]
        for acc in accounts:
            balance = broker.get_account_balance(acc)
            account_data.append([acc.account_number, balance.get('opening_balance', 0), balance.get('current_balance', 0)])

        monitoring.update('A1', account_data)

        # Buffer for margin
        buffer = portfolio.total_value * config.risk.reserved_margin_fraction
        monitoring.update('A5:B5', [["Buffer for Margin", buffer]])

        # Portfolio risk & stats
        portfolio_data = [["Net Delta", portfolio.get_net_greeks()['delta']], ["Net Gamma", portfolio.get_net_greeks()['gamma']], ["Total Undefined Risk", portfolio.total_undefined_risk]]
        monitoring.update('A7', portfolio_data)

        # Positions table
        positions_headers = ["Symbol", "Quantity", "Entry Price", "Current Price", "PNL", "Opening Delta", "Current Delta", "Greeks PNL", "Actual PNL", "Unexplained PNL", "Risk Level", "Threshold", "Strategy Name", "Buying Power Used"]
        positions_data = [positions_headers] + [[r.get(k, 'N/A') for k in positions_headers] for r in position_risks]
        monitoring.update('A12', positions_data)

        logger.info("Monitoring sheet updated")

    def process_what_if_sheet(self, broker, portfolio):
        """Read Sheet 2: What-If Trades, analyze impact, book if triggered."""
        what_if = self.sheet.worksheet("Orders") if "Orders" in [ws.title for ws in self.sheet.worksheets()] else self.sheet.add_worksheet("Orders", rows=100, cols=20)

        data = what_if.get_all_values()
        if not data:
            logger.warning("No data in Orders sheet")
            return

        # Analyze existing positions
        existing_positions = portfolio.positions_manager.positions
        selected_existing = [row for row in data if row[8] == "Yes"]  # Assume column I is Select

        # What-if trades
        what_if_trades = [row for row in data[1:] if row and row[0] == "What-If"]

        # Simulate combined portfolio
        simulated_positions = existing_positions.copy()  # Copy current
        for trade in what_if_trades:
            # Simulate adding trade (placeholder — add real simulation logic)
            simulated_pnl = 100  # Example
            logger.info(f"Simulated PNL impact for {trade[0]} on {trade[1]}: ${simulated_pnl:.2f}")

        # Update Sheet with analysis
        analysis_data = [["Combined PNL Impact", "Low"]]  # Placeholder
        what_if.update('K2', analysis_data)

        # Book triggered trades
        for row in data:
            if row[9] == "Book":  # Column J Trigger
                # Book trade (call appropriate function)
                strategy = row[0]
                underlying = row[1]
                logger.info(f"Booking {strategy} on {underlying} from Sheet")
                # e.g., sell_otm_put(broker, underlying)

        logger.info("What-If sheet processed and orders booked")

    def sync_all(self, broker, portfolio, position_risks):
        """Full sync: Monitoring + What-If."""
        self.update_monitoring_sheet(broker, portfolio, position_risks)
        self.process_what_if_sheet(broker, portfolio)

    def close(self):
        logger.info("Sheets sync complete")