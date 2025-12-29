# trading_bot/auth.py
import os
from typing import Dict
from abc import ABC, abstractmethod
from tastytrade import ProductionSession  # Example for Tastytrade

class Authenticator(ABC):
    """Abstract base for authentication. Extend for different auth methods."""
    @abstractmethod
    def authenticate(self) -> Dict[str, str]:
        pass

class TastytradeAuthenticator(Authenticator):
    """Authenticator for Tastytrade."""
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    def authenticate(self) -> ProductionSession:
        return ProductionSession(self.username, self.password)

class MultiUserAuthManager:
    """Manages auth for multiple users (service-oriented)."""
    def __init__(self):
        self.sessions: Dict[str, ProductionSession] = {}  # user_id -> session

    def get_session(self, user_id: str, auth: Authenticator) -> ProductionSession:
        if user_id not in self.sessions:
            self.sessions[user_id] = auth.authenticate()
        return self.sessions[user_id]