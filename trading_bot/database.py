# trading_bot/database.py
import sqlite3
from typing import List

class Database:
    """Optional persistence for positions, trades."""
    def __init__(self, db_file: str = 'trading.db'):
        self.conn = sqlite3.connect(db_file)
        self.create_tables()

    def create_tables(self):
        self.conn.execute('''CREATE TABLE IF NOT EXISTS positions (id INTEGER PRIMARY KEY, symbol TEXT, quantity INT)''')
        # Add more tables: trades, logs

    def save_positions(self, positions: List[Dict]):
        for pos in positions:
            self.conn.execute('INSERT INTO positions (symbol, quantity) VALUES (?, ?)', (pos['symbol'], pos['quantity']))
        self.conn.commit()