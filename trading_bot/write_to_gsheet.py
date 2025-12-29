# write_to_gsheet.py
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===========================
# Config
# ===========================
SERVICE_ACCOUNT_FILE = "service_account.json"
SHEET_ID = "YOUR_SHEET_ID_HERE"
WORKSHEET_NAME = "Positions"  # Tab name

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def get_sheet():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).worksheet(WORKSHEET_NAME)

def find_row_by_symbol(sheet, occ_symbol: str) -> int:
    """Find row number (1-based) by OCC symbol in column C."""
    cell = sheet.find(occ_symbol, in_column=3)  # Column C = 3
    return cell.row if cell else None

def update_position_row(occ_symbol: str, data: dict):
    """
    Update a row with calculated data (Greeks, prices, etc.).
    
    data example:
    {
        "current_option_price": 5.40,
        "delta": -0.18,
        "gamma": 0.04,
        "theta": -0.85,
        "vega": 14.2,
        "rho": 0.07,
        "underlying_price": 195.50,
        "pnl": 125.00
    }
    """
    sheet = get_sheet()
    
    row = find_row_by_symbol(sheet, occ_symbol)
    if not row:
        logger.warning(f"Symbol {occ_symbol} not found in sheet.")
        return
    
    # Map data to columns (use header names for reliability)
    updates = []
    col_map = {
        "Current Price": data.get("current_option_price"),
        "Delta": data.get("delta"),
        "Gamma": data.get("gamma"),
        "Theta": data.get("theta"),
        "Vega": data.get("vega"),
        "Rho": data.get("rho"),
        "Underlying Price": data.get("underlying_price"),
        "PnL": data.get("pnl"),  # If you have a PnL column
        "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    header_row = sheet.row_values(1)  # Get headers
    for header, value in col_map.items():
        if header in header_row:
            col_index = header_row.index(header) + 1  # 1-based
            updates.append({
                "range": f"{gspread.utils.rowcol_to_a1(row, col_index)}",
                "values": [[value if value is not None else ""]]
            })
    
    if updates:
        sheet.batch_update(updates)
        logger.info(f"Updated row {row} for {occ_symbol}")
    else:
        logger.warning("No columns matched for update.")

# ===========================
# Example Usage
# ===========================
if __name__ == "__main__":
    sample_data = {
        "current_option_price": 5.40,
        "delta": -0.18,
        "gamma": 0.04,
        "theta": -0.85,
        "vega": 14.2,
        "rho": 0.07,
        "underlying_price": 195.50,
        "pnl": 125.00
    }
    
    update_position_row(".AAPL260116C00200000", sample_data)