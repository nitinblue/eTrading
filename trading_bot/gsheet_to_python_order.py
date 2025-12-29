# gsheet_to_python_order.py
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import logging
from trading_bot.broker import NeutralOrder, OrderLeg, OrderAction, PriceEffect, OrderType
from trading_bot.trade_execution import TradeExecutor
from trading_bot.broker import TastytradeBroker  # Switch to MockBroker for testing
# from trading_bot.broker_mock import MockBroker  # Uncomment for dry-run testing

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ===========================
# Configuration
# ===========================
SERVICE_ACCOUNT_FILE = "service_account.json"  # Your Google service account key
SHEET_ID = "YOUR_GOOGLE_SHEET_ID_HERE"         # Replace with your sheet ID
WORKSHEET_NAME = "Orders"                      # Name of the tab with orders

# Column mapping (adjust if your columns are different)
COLUMN_MAP = {
    "timestamp": "A",
    "underlying": "B",
    "occ_symbol": "C",
    "action": "D",
    "quantity": "E",
    "limit_price": "F",
    "account_id": "G",
    "status": "H",
    "result": "I"
}

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ===========================
# Google Sheet Helper
# ===========================
def get_sheet():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet(WORKSHEET_NAME)
    return sheet

def get_column_index(col_letter: str) -> int:
    sheet = get_sheet()
    return sheet.find(col_letter + "1").col  # Find header row

# ===========================
# Read & Process Orders
# ===========================
def process_pending_orders(dry_run_broker: bool = True):
    sheet = get_sheet()
    records = sheet.get_all_records()  # Assumes row 1 is header

    pending_orders = [r for r in records if str(r.get("Status", "")).strip().lower() == "pending"]
    
    if not pending_orders:
        logger.info("No pending orders found.")
        return

    # Initialize broker
    if dry_run_broker:
        from trading_bot.broker_mock import MockBroker
        broker = MockBroker()
    else:
        broker = TastytradeBroker(
            username="your_email@example.com",
            password="your_password",
            is_paper=True  # Set False for live
        )
    
    broker.connect()
    executor = TradeExecutor(broker)

    status_col = sheet.find("Status").col
    result_col = sheet.find("Result").col if "Result" in [h["value"] for h in sheet.row_values(1)] else None

    for idx, order in enumerate(pending_orders, start=2):  # Row 2 = first data row
        row_num = idx + 1  # +1 for header
        logger.info(f"Processing row {row_num}: {order}")

        try:
            # Build NeutralOrder
            action_str = order["Action"].upper().replace(" ", "_")
            action = OrderAction[action_str]

            leg = OrderLeg(
                symbol=order["OCC Symbol"],
                quantity=int(order["Quantity"]),
                action=action
            )

            price_effect = PriceEffect.CREDIT if "SELL" in order["Action"] else PriceEffect.DEBIT
            limit_price = float(order["Limit Price"]) if order["Limit Price"] else None

            neutral_order = NeutralOrder(
                legs=[leg],
                price_effect=price_effect,
                order_type=OrderType.LIMIT if limit_price else OrderType.MARKET,
                limit_price=limit_price,
                time_in_force="DAY",
                dry_run=dry_run_broker  # True = no real order
            )

            account_id = order.get("Account ID", None)

            # Execute
            result = executor.execute("GoogleSheetOrder", neutral_order, account_id=account_id)
            result_str = str(result)

            # Update sheet
            sheet.update_cell(row_num, status_col, "Executed")
            if result_col:
                sheet.update_cell(row_num, result_col, result_str[:500])  # Truncate if long

            logger.info(f"Success: Row {row_num} → {result_str}")

        except Exception as e:
            error_msg = f"Error: {str(e)[:100]}"
            logger.error(f"Failed row {row_num}: {e}")
            sheet.update_cell(row_num, status_col, "Failed")
            if result_col:
                sheet.update_cell(row_num, result_col, error_msg)

# ===========================
# Run
# ===========================
if __name__ == "__main__":
    # Set dry_run_broker=False only when ready for real trades!
    process_pending_orders(dry_run_broker=True)
    print("Order processing complete.")