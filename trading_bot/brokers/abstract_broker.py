from abc import ABC, abstractmethod
from typing import List
from trading_bot.domain.models import Order, Position


class AbstractBroker(ABC):

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def get_accounts(self) -> list:
        pass

    @abstractmethod
    def get_positions(self, account_id) -> List[Position]:
        pass

    @abstractmethod
    def get_net_liquidation(self, account_id) -> float:
        pass

    @abstractmethod
    def get_buying_power(self, account_id) -> float:
        pass

    @abstractmethod
    def place_order(self, account_id, order: Order):
        pass
