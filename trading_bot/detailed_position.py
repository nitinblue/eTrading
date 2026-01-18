from datetime import datetime
from decimal import Decimal
import pandas as pd
import asyncio

class DetailedPosition:
    """Store position with full Greeks attribution for PnL breakdown."""
    
    def __init__(self, symbol: str, underlying: str, option_type: str, 
                 strike: float, expiry_date, quantity: float, 
                 entry_premium: float, entry_greeks: dict, trade_id: str, leg_id: str):
        self.symbol = symbol
        self.underlying = underlying
        self.option_type = option_type  # "Call" or "Put"
        self.strike = strike
        self.expiry_date = expiry_date  # datetime.date
        self.quantity = quantity
        self.entry_premium = entry_premium
        
        # Opening Greeks (snapshot at entry)
        self.opening_greeks = entry_greeks  # {delta, gamma, theta, vega, rho, iv}
        
        # Current state
        self.current_premium = entry_premium
        self.current_greeks = entry_greeks.copy()
        
        # Trade metadata
        self.trade_id = trade_id
        self.leg_id = leg_id
        self.trade_date = datetime.now().date()
        self.last_updated = datetime.now()
        
    def update_current_price(self, current_premium: float, current_greeks: dict):
        """Update with latest market data."""
        self.current_premium = current_premium
        self.current_greeks = current_greeks
        self.last_updated = datetime.now()
    
    def calculate_dte(self) -> int:
        """Days to expiry."""
        return (self.expiry_date - datetime.now().date()).days
    
    def calculate_pnl_components(self, dS=0, dVol=0, dR=0.0):
        """
        Calculate Greeks-based PnL attribution.
        dS: change in underlying price
        dVol: change in IV
        dR: change in interest rate
        """
        q = self.quantity * 100  # contracts to shares
        
        # Opening Greeks
        delta_0 = self.opening_greeks.get('delta', 0)
        gamma_0 = self.opening_greeks.get('gamma', 0)
        theta_0 = self.opening_greeks.get('theta', 0)
        vega_0 = self.opening_greeks.get('vega', 0)
        rho_0 = self.opening_greeks.get('rho', 0)
        iv_0 = self.opening_greeks.get('iv', 0.25)
        
        # Changes from current
        delta_change = (self.current_greeks.get('delta', 0) - delta_0)
        iv_change = (self.current_greeks.get('iv', 0.25) - iv_0)
        
        # Greeks PnL
        delta_pnl = delta_0 * q * dS
        gamma_pnl = 0.5 * gamma_0 * q * (dS ** 2)
        theta_pnl = theta_0 * q * (1.0 / 365)  # per day
        vega_pnl = vega_0 * q * dVol
        rho_pnl = rho_0 * q * dR
        
        approximated_pnl = delta_pnl + gamma_pnl + theta_pnl + vega_pnl + rho_pnl
        
        # Actual PnL
        actual_pnl = (self.current_premium - self.entry_premium) * q
        
        # Unexplained
        unexplained_pnl = actual_pnl - approximated_pnl
        
        return {
            "delta_pnl": round(delta_pnl, 2),
            "gamma_pnl": round(gamma_pnl, 2),
            "theta_pnl": round(theta_pnl, 2),
            "vega_pnl": round(vega_pnl, 2),
            "rho_pnl": round(rho_pnl, 2),
            "approximated_pnl": round(approximated_pnl, 2),
            "actual_pnl": round(actual_pnl, 2),
            "unexplained_pnl": round(unexplained_pnl, 2),
        }
    
    def to_row(self, dS=0, dVol=0, dR=0.0):
        """Convert to spreadsheet row."""
        pnl = self.calculate_pnl_components(dS, dVol, dR)
        dte = self.calculate_dte()
        
        return [
            self.trade_date.strftime("%Y-%m-%d"),
            self.trade_id,
            self.leg_id,
            self.underlying,
            self.option_type,
            f"${self.strike:.2f}",
            self.expiry_date.strftime("%Y-%m-%d"),
            self.quantity,
            f"${self.entry_premium:.2f}",
            f"${self.opening_greeks.get('iv', 0.25):.2%}",  # Opening IV
            f"${self.current_greeks.get('iv', 0.25):.2%}",  # Current IV
            round(self.opening_greeks.get('delta', 0), 2),
            round(self.opening_greeks.get('gamma', 0), 4),
            round(self.opening_greeks.get('theta', 0), 2),
            round(self.opening_greeks.get('vega', 0), 2),
            round(self.opening_greeks.get('rho', 0), 2),
            dS,
            dVol,
            dR,
            "1 day",  # dt
            pnl["delta_pnl"],
            pnl["gamma_pnl"],
            pnl["theta_pnl"],
            pnl["vega_pnl"],
            pnl["rho_pnl"],
            pnl["actual_pnl"],
            pnl["approximated_pnl"],
            pnl["unexplained_pnl"],
            0,  # Realized PnL (closed trades)
            pnl["actual_pnl"],  # Unrealized
            dte,
            round(self.opening_greeks.get('theta', 0) / max(self.opening_greeks.get('vega', 0.001), 0.001), 2),
            0.30,  # Target delta (example)
            round(self.opening_greeks.get('delta', 0) - 0.30, 2),  # Delta deviation
            "No",  # Adjustment flag
            "Hold",  # Roll suggestion
            "",  # Notes
        ]
