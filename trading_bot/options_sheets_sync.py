# trading_bot/options_sheets_sync.py
"""
Google Sheets sync for the 'OptionsPortfolio' worksheet.
Now includes opening/current Greeks and PNL attribution per Greek.
"""

import gspread
from google.oauth2.service_account import Credentials
from typing import Dict, List
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class OptionsSheetsSync:
    def __init__(self, config: Config):
        sheets_config = getattr(config, 'sheets', {})
        self.sheet_id = sheets_config.get('sheet_id')
        self.worksheet_name = sheets_config.get('worksheet_name', 'OptionsPortfolio')
        self.service_account_file = sheets_config.get('service_account_file', 'service_account.json')

        if not self.sheet_id:
            raise ValueError("Google Sheet ID not configured in config.yaml")

        self._connect()

    def _connect(self):
        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = Credentials.from_service_account_file(self.service_account_file, scopes=scopes)
            client = gspread.authorize(creds)
            self.sheet = client.open_by_key(self.sheet_id)

            try:
                self.worksheet = self.sheet.worksheet(self.worksheet_name)
                logger.info(f"Using existing worksheet: {self.worksheet_name}")
            except gspread.WorksheetNotFound:
                self.worksheet = self.sheet.add_worksheet(
                    title=self.worksheet_name,
                    rows=2000,
                    cols=30
                )
                logger.info(f"Created new worksheet: {self.worksheet_name}")

        except Exception as e:
            logger.error(f"Google Sheets connection failed: {e}")
            raise

    def clear_sheet(self):
        self.worksheet.clear()
        logger.info("Cleared OptionsPortfolio sheet")

    def update_account_summary(self, balance: Dict):
        data = [
            ["Options Portfolio Dashboard", ""],
            ["Last Updated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ["", ""],
            ["Account Summary", ""],
            ["Cash Balance", f"${balance.get('cash_balance', 0):.2f}"],
            ["Equity Buying Power", f"${balance.get('equity_buying_power', 0):.2f}"],
            ["Derivative Buying Power", f"${balance.get('derivative_buying_power', 0):.2f}"],
            ["Margin Equity", f"${balance.get('margin_equity', 0):.2f}"],
        ]
        self.worksheet.update('A1:B8', data)
        logger.info("Account summary updated")

    def update_positions_table(self, position_risks: List[Dict]):
        """Write full positions table with opening/current Greeks and PNL attribution."""
        if not position_risks:
            logger.info("No positions to write")
            return

        headers = [
            "Trade ID", "Leg ID", "Strategy", "Symbol", "Quantity",
            "Entry Price", "Current Price", "Actual PnL", "PnL Driver",
            "Allocation %", "Buying Power Used", "Stop Loss", "Take Profit",
            "Undefined Risk", "Violations",
            # Opening Greeks
            "Open Delta", "Open Gamma", "Open Theta", "Open Vega", "Open Rho",
            # Current Greeks
            "Curr Delta", "Curr Gamma", "Curr Theta", "Curr Vega", "Curr Rho",
            # PNL Attribution
            "Delta PnL", "Gamma PnL", "Theta PnL", "Vega PnL", "Rho PnL", "Unexplained PnL"
        ]

        rows = [headers]
        for risk in position_risks:
            open_g = risk.get('opening_greeks', {})
            curr_g = risk.get('current_greeks', {})
            rows.append([
                risk.get('trade_id', 'N/A'),
                risk.get('leg_id', 'N/A'),
                risk.get('strategy', 'Unknown'),
                risk.get('symbol', 'N/A'),
                risk.get('quantity', 0),
                f"${risk.get('entry_price', 0):.2f}",
                f"${risk.get('current_price', 0):.2f}",
                f"${risk.get('actual_pnl', 0):.2f}",
                risk.get('pnl_driver', ''),
                f"{risk.get('allocation', 0):.2%}",
                f"${risk.get('buying_power_used', 0):.2f}",
                f"${risk.get('stop_loss', 0):.2f}",
                f"${risk.get('take_profit', 0):.2f}",
                "Yes" if risk.get('is_undefined_risk') else "No",
                "; ".join(risk.get('violations', [])),
                # Opening Greeks
                f"{open_g.get('delta', 0):.4f}",
                f"{open_g.get('gamma', 0):.4f}",
                f"{open_g.get('theta', 0):.4f}",
                f"{open_g.get('vega', 0):.2f}",
                f"{open_g.get('rho', 0):.4f}",
                # Current Greeks
                f"{curr_g.get('delta', 0):.4f}",
                f"{curr_g.get('gamma', 0):.4f}",
                f"{curr_g.get('theta', 0):.4f}",
                f"{curr_g.get('vega', 0):.2f}",
                f"{curr_g.get('rho', 0):.4f}",
                # PNL Attribution
                f"${risk.get('delta_pnl', 0):.2f}",
                f"${risk.get('gamma_pnl', 0):.2f}",
                f"${risk.get('theta_pnl', 0):.2f}",
                f"${risk.get('vega_pnl', 0):.2f}",
                f"${risk.get('rho_pnl', 0):.2f}",
                f"${risk.get('unexplained_pnl', 0):.2f}",
            ])

        start_cell = "A10"
        self.worksheet.update(start_cell, rows)
        logger.info(f"Updated {len(position_risks)} positions with full Greek PNL attribution")

    def sync_all(self, balance: Dict, position_risks: List[Dict]):
        self.clear_sheet()
        self.update_account_summary(balance)
        self.update_positions_table(position_risks)
        logger.info("OptionsPortfolio sheet fully synced with Greek attribution")