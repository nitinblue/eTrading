# trading_bot/options_sheets_sync.py
from datetime import datetime
import os
import gspread
from google.oauth2.service_account import Credentials
from tabulate import tabulate
from typing import Dict, List
import logging
import pandas as pd

from trading_bot.detailed_position import DetailedPosition

logger = logging.getLogger(__name__)

class OptionsSheetsSync:
    def __init__(self, config):
        risk_config = getattr(config, 'risk', {})
        # Fixed: Use attribute access for Pydantic
        sheets_config = getattr(config, 'sheets', {})
        # self.sheet_id = sheets_config.get('sheet_id')
        self.sheet_id = os.getenv('GOOGLE_SHEET_ID')
        self.worksheet_name = sheets_config.get('worksheet_name', 'Monitoring')
        self.service_account_file = sheets_config.get('service_account_file', 'service_account.json')
        self.risk_config = risk_config

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
        logger.info(f"Updating Monitoring sheet...")
        """Update Sheet 1: Monitoring (view-only)."""
        monitoring = self.sheet.worksheet("Monitoring") if "Monitoring" in [ws.title for ws in self.sheet.worksheets()] else self.sheet.add_worksheet("Monitoring", rows=100, cols=20)

        # Accounts
        from tastytrade.account import Account
        accounts = Account.get(broker.session)
        account_data = [["Account", "Opening Balance", "Current Balance"]]
        for acc in accounts:          
            balance = broker.get_account_balance()
            account_data.append([acc.account_number, balance.get('cash_balance', 0), balance.get('margin_equity', 0)])

        monitoring.update('A1', account_data)

        # Buffer for margin
        buffer = float(portfolio.total_value) * float(self.risk_config.get('reserve_margin_fraction',0.1))
        monitoring.update('A5:B5', [["Buffer for Margin", buffer]])

        # Portfolio risk & stats
        # portfolio_data = [["Net Delta", portfolio.get_net_greeks()['delta']], ["Net Gamma", portfolio.get_net_greeks()['gamma']], ["Total Undefined Risk", portfolio.total_undefined_risk]]
        portfolio_data = [["Net Delta", portfolio.get_net_greeks()['delta']], ["Net Gamma", portfolio.get_net_greeks()['gamma']]]
        logger.info(f"Portfolio Net Greeks: {portfolio_data}")
        monitoring.update('A7', portfolio_data)

        # Positions table
        monitoring.update('A10', [["Positions Details"]])
        positions_headers = ["Symbol", "Quantity", "Entry Price", "Current Price", "PNL", "Opening Delta", "Current Delta", "Greeks PNL", "Actual PNL", "Unexplained PNL", "Risk Level", "Threshold", "Strategy Name", "Buying Power Used"]
        positions_data = [positions_headers] + [[r.get(k, 'N/A') for k in positions_headers] for r in position_risks]
        monitoring.update('A11', positions_data)      

        logger.info("Monitoring sheet updated")

    def process_what_if_sheet(self, broker, portfolio):
        """Read Sheet 2: What-If Trades, analyze impact, book if triggered."""
        what_if = self.sheet.worksheet("Orders") if "Orders" in [ws.title for ws in self.sheet.worksheets()] else self.sheet.add_worksheet("Orders", rows=100, cols=20)

        data = what_if.get_all_values()
        logger.info(f"Processing What-If sheet with {len(data)-1} entries {data}")
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
        what_if.update('J2', analysis_data)

        # Book triggered trades
        for row in data:
            if row[9] == "Book":  # Column J Trigger
                # Book trade (call appropriate function)
                strategy = row[0]
                underlying = row[1]
                logger.info(f"Booking {strategy} on {underlying} from Sheet")
                # e.g., sell_otm_put(broker, underlying)

        logger.info("What-If sheet processed and orders booked")

    async def sync_all(self, broker, portfolio, position_risks):
        """Full sync: Monitoring + What-If."""
        self.update_monitoring_sheet(broker, portfolio, position_risks)
        self.process_what_if_sheet(broker, portfolio)
        self.orders_to_excel(broker)
        await self.positions_to_excel(broker)

    def close(self):
        logger.info("Sheets sync complete")
    
    def orders_to_excel(self, broker):
        # Get worksheet (gspread)
        titles = [ws.title for ws in self.sheet.worksheets()]
        if "Orders" in titles:
            worksheet = self.sheet.worksheet("Orders")
        else:
            worksheet = self.sheet.add_worksheet("Orders", rows=100, cols=20)
        logger.info(f"Orders sheet: {worksheet.title}")
        # Get positions (your custom format)
        orders_json = broker.get_all_orders()  # → list of dicts!
        logger.info(f"Positions: {len(orders_json)} items {orders_json}")
        if not orders_json:
                logger.warning("No positions to export")
                return
        
        # Your data is already list of dicts (not nested "data.items")
        items = orders_json  # ← FIXED!
        
        # DataFrame
        df = pd.DataFrame(items)
    
        # Convert numerics
        num_cols = [
            "quantity", "entry_price", "current_price"
        ]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
    
        # Rename
        rename_map = {
            "symbol": "option_symbol",
            "entry_price": "avg_open_price",
            "current_price": "mark_price",
        }
        df = df.rename(columns=rename_map)
                  
        # Write to gspread (list of lists)
        headers = df.columns.tolist()
        values = [headers] + df.fillna('').astype(str).values.tolist()
        
        worksheet.update(values=values, range_name="A8")
        logger.info(f"✅ Updated Orders sheet: {len(items)} orders")
    
    async def positions_to_excel(self, broker):
        # Get worksheet (gspread)
        titles = [ws.title for ws in self.sheet.worksheets()]
        if "Positions" in titles:
            worksheet = self.sheet.worksheet("Positions")
        else:
            worksheet = self.sheet.add_worksheet("Positions", rows=100, cols=20)
        logger
        # Get positions (your custom format)
        positions_json = await broker.get_positions()  # → list of dicts!
       
        logger.info(f"Positions: {len(positions_json)} items {positions_json}")       
        if not positions_json:
                logger.warning("No positions to export")
                return
        self.positions_to_detailed_sheet(positions_json)
        
        # Your data is already list of dicts (not nested "data.items")
        # items = positions_json  # ← FIXED!
        
        # # DataFrame
        # df = pd.DataFrame(items)
    
        # # Convert numerics
        # num_cols = [
        #     "quantity", "entry_price", "current_price"
        # ]
        # for col in num_cols:
        #     if col in df.columns:
        #         df[col] = pd.to_numeric(df[col], errors="coerce")
    
        # # Rename
        # rename_map = {
        #     "symbol": "option_symbol",
        #     "entry_price": "avg_open_price",
        #     "current_price": "mark_price",
        # }
        # df = df.rename(columns=rename_map)
        
        # # Add computed columns
        # df["notional"] = df["quantity"] * 100 * df["avg_open_price"]
        # df["mark_value"] = df["quantity"] * 100 * df["mark_price"]
        # df["unrealized_pnl"] = df["mark_value"] - df["notional"]
    
        # # Write to gspread (list of lists)
        # headers = df.columns.tolist()
        # values = [headers] + df.fillna('').astype(str).values.tolist()
        
        # worksheet.update(values=values, range_name="A1")
        # logger.info(f"✅ Updated Options sheet: {len(items)} positions")

    def positions_to_detailed_sheet(self, positions):
        """Write DetailedPosition to Google Sheet."""
        titles = [ws.title for ws in self.sheet.worksheets()]
        if "Positions" in titles:
            worksheet = self.sheet.worksheet("Positions")
        else:
            worksheet = self.sheet.add_worksheet("Positions", rows=100, cols=20)

        detailed_positions = self.dict_positions_to_detailed(positions)
       
        headers = [
        "Date", "Trade ID", "Leg ID", "Underlying", "Option Type", "Strike", "Expiry",
        "Quantity", "Entry Premium", "Opening IV", "Current IV",
        "Opening Delta", "Opening Gamma", "Opening Theta", "Opening Vega", "Opening Rho",
        "dS", "dVol", "dR", "dt",
        "Delta PnL", "Gamma PnL", "Theta PnL", "Vega PnL", "Rho PnL",
        "Actual PnL", "Approximated PnL", "Unexplained PnL",
        "Realized PnL", "Unrealized PnL", "DTE",
        "Theta/Vega Ratio", "Target Delta", "Delta Deviation",
        "Adjustment Flag", "Roll Suggestion", "Notes"
    ]
        
            # Market assumptions
        dS:any = 5.0  # $5 underlying move
        dVol = 0.02  # +2% IV change
        dR = 0.0001  # +1bp rate change
        
        rows = [
                pos.to_row(dS=dS, dVol=dVol, dR=dR) 
                for pos in detailed_positions
                    ]
        values = [headers] + rows
        worksheet.update(values=values, range_name="A1")
        logger.info(f"✅ Updated Detailed PnL sheet: {len(detailed_positions)} positions")
    def dict_positions_to_detailed(self, positions_json: List[Dict]) -> List[DetailedPosition]:
        """positions_json → DetailedPosition objects."""
        detailed = []
        
        for i, pos in enumerate(positions_json):
            symbol = pos["symbol"].strip()
            
            # Parse symbol (QQQ 260106C00620000 → underlying, type, strike, expiry)
            parts = symbol.split()
            underlying = parts[0]  # "QQQ"
            opt_part = parts[1]    # "260106C00620000"
            
            option_type = "Call" if "C" in opt_part else "Put"
            expiry_str = opt_part[:6]  # "260106"
            strike_str = opt_part[-8:] # "00620000"
            
            expiry = datetime.strptime(expiry_str, "%y%m%d").date()
            strike = float(strike_str) / 1000
            
            # Create DetailedPosition
            d_pos = DetailedPosition(
                symbol=symbol,
                underlying=underlying,
                option_type=option_type,
                strike=strike,
                expiry_date=expiry,
                quantity=pos["quantity"],
                entry_premium=pos["entry_price"],
                entry_greeks=pos.get("greeks", {}),  # From your enrichment
                trade_id="Trade001",  # Or from your order tracking
                leg_id=f"Leg{i+1}"
            )
            
            # Update with current
            current_greeks = pos.get("greeks", {})
            d_pos.update_current_price(pos["current_price"], current_greeks)
            detailed.append(d_pos)
        
        return detailed
