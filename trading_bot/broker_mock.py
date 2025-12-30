# trading_bot/broker_mock.py
from typing import List, Optional, Dict
from order_model import UniversalOrder  # Import from new file
from brokers.abstract_broker import Broker  # Absolute
import logging



logger = logging.getLogger(__name__)

class MockBroker(Broker):
    def __init__(self, mock_positions: Optional[Dict[str, List[Dict]]] = None, mock_balances: Optional[Dict[str, Dict]] = None):
        self.mock_positions = mock_positions or {
            'default_account': [
                {
                    'symbol': '.AAPL260117C00200000',
                    'quantity': -10,
                    'entry_price': 5.20,
                    'current_price': 6.00,
                    'greeks': {'delta': -0.32, 'gamma': 0.04, 'theta': -0.85, 'vega': 15.2, 'rho': 0.1}
                }
            ]
        }
        self.mock_balances = mock_balances or {
            'default_account': {
                'cash_balance': 100000.0,
                'buying_power': 100000.0,
                'equity': 75000.0
            }
        }
        self.order_history: Dict[str, List[Dict]] = {}
        self.connected = False

    def connect(self) -> None:
        self.connected = True
        logger.info("[MOCK] Connected to broker.")

    def get_positions(self, account_id: Optional[str] = None) -> List[Dict]:
        if not self.connected:
            raise RuntimeError("[MOCK] Broker not connected.")
        acc_id = account_id or 'default_account'
        return self.mock_positions.get(acc_id, [])

    def get_account_balance(self, account_id: Optional[str] = None) -> Dict:
        if not self.connected:
            raise RuntimeError("[MOCK] Broker not connected.")
        acc_id = account_id or 'default_account'
        return self.mock_balances.get(acc_id, {})

    def execute_order(self, order: UniversalOrder, account_id: Optional[str] = None) -> Dict:
        if not self.connected:
            raise RuntimeError("[MOCK] Broker not connected.")
        acc_id = account_id or 'default_account'
        if acc_id not in self.order_history:
            self.order_history[acc_id] = []
        if order.dry_run:
            logger.info(f"[MOCK DRY RUN] Would execute on {acc_id}: {order.to_dict()}")
            return {"status": "mock_dry_run_success", "order": order.to_dict()}
        self.order_history[acc_id].append(order.to_dict())
        for leg in order.legs:
            mock_pos = {
                'symbol': leg.symbol,
                'quantity': leg.quantity if "BUY" in leg.action.value else -leg.quantity,
                'entry_price': 0.0,
                'current_price': 0.0,
                'greeks': {}
            }
            if acc_id not in self.mock_positions:
                self.mock_positions[acc_id] = []
            self.mock_positions[acc_id].append(mock_pos)
        logger.info(f"[MOCK] Executed on {acc_id}: {order.to_dict()}")
        return {"status": "mock_success", "order_id": len(self.order_history[acc_id]), "details": order.to_dict()}