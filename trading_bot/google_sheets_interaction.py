# google_sheets_interaction.py
import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd

# ===========================
# Configuration
# ===========================

# Path to your service account JSON key file (download from Google Cloud Console)
SERVICE_ACCOUNT_FILE = "service_account.json"  # Put this file in your project root

# ID of your Google Sheet (from the URL: https://docs.google.com/spreadsheets/d/SHEET_ID/edit)
SHEET_ID = "your_google_sheet_id_here"  # Replace with your actual ID

# Name of the worksheet/tab you want to use
WORKSHEET_NAME = "Trades"  # Change if your tab has a different name

# Scopes required for read/write access
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# ===========================
# Authentication & Client Setup
# ===========================

def get_gsheet_client():
    """Authenticate and return a gspread client."""
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client

# ===========================
# Basic Operations
# ===========================

def read_trades():
    """Read all data from the Trades sheet as a pandas DataFrame."""
    client = get_gsheet_client()
    sheet = client.open_by_key(SHEET_ID).worksheet(WORKSHEET_NAME)
    
    # Get all records (assumes first row is header)
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    print("Current trades in sheet:")
    print(df)
    return df

def append_trade(signal: dict):
    """Append a new trade signal row to the sheet."""
    client = get_gsheet_client()
    sheet = client.open_by_key(SHEET_ID).worksheet(WORKSHEET_NAME)
    
    # Prepare row (match your sheet columns)
    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        signal.get("underlying", ""),
        signal.get("strategy", ""),
        signal.get("expiry", ""),
        signal.get("strike", ""),
        signal.get("option_type", ""),
        signal.get("quantity", 1),
        signal.get("status", "Pending")
    ]
    
    sheet.append_row(row)
    print(f"Appended new trade: {signal}")

def update_pnl(row_index: int, pnl: float, greeks: dict):
    """Update PnL and Greeks for a specific row (1-based index from sheet)."""
    client = get_gsheet_client()
    sheet = client.open_by_key(SHEET_ID).worksheet(WORKSHEET_NAME)
    
    updates = [
        pnl,
        greeks.get("delta", 0),
        greeks.get("gamma", 0),
        greeks.get("theta", 0),
        greeks.get("vega", 0),
        "Updated"
    ]
    
    # Column range to update (e.g., I2:N2 for row 2)
    cell_range = f"I{row_index}:N{row_index}"
    sheet.update(cell_range, [updates])
    print(f"Updated row {row_index} with PnL: {pnl} and Greeks")

# ===========================
# Example Usage
# ===========================

if __name__ == "__main__":
    # 1. Read current trades
    trades_df = read_trades()
    
    # 2. Example: Append a new short put signal
    new_signal = {
        "underlying": "AAPL",
        "strategy": "Short Put",
        "expiry": "2026-01-16",
        "strike": 190.0,
        "option_type": "put",
        "quantity": 5
    }
    append_trade(new_signal)
    
    # 3. Example: Update row 2 with calculated PnL and Greeks
    update_pnl(row_index=2, pnl=125.40, greeks={
        "delta": -0.18,
        "gamma": 0.04,
        "theta": 0.85,
        "vega": 14.2
    })