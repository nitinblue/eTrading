# trading_bot/ui.py
import gspread
from google.oauth2.service_account import Credentials
from typing import Dict

class UIIntegration:
    """Base for UI, e.g., Google Sheets."""
    @abstractmethod
    def read_data(self) -> Dict:
        pass

    @abstractmethod
    def write_data(self, data: Dict):
        pass

class GoogleSheetsUI(UIIntegration):
    def __init__(self, sheet_id: str, credentials_file: str):
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds = Credentials.from_service_account_file(credentials_file, scopes=scopes)
        client = gspread.authorize(creds)
        self.sheet = client.open_by_key(sheet_id).sheet1

    def read_data(self, row: int) -> Dict:
        values = self.sheet.row_values(row)
        # Parse into dict as before
        return {}  # Implement parsing

    def write_data(self, row: int, col: int, value):
        self.sheet.update_cell(row, col, value)