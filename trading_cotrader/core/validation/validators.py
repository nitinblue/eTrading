"""
Data Validation - Ensure data integrity

Validates positions, trades, and compares against broker data
"""

import logging
from typing import List, Dict, Tuple
from decimal import Decimal

import trading_cotrader.core.models.domain as dm

logger = logging.getLogger(__name__)


class PositionValidator:
    """Validate position data integrity"""
    
    @staticmethod
    def validate_position(position: dm.Position) -> Tuple[bool, List[str]]:
        """
        Validate a single position
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        
        # Check quantity
        if position.quantity == 0:
            errors.append("Zero quantity")
        
        # Check symbol
        if not position.symbol:
            errors.append("Missing symbol")
        elif position.symbol.asset_type == dm.AssetType.OPTION:
            if not position.symbol.strike:
                errors.append("Option missing strike")
            if not position.symbol.expiration:
                errors.append("Option missing expiration")
            if not position.symbol.option_type:
                errors.append("Option missing type")
        
        # Check Greeks for options
        if position.symbol.asset_type == dm.AssetType.OPTION:
            if not position.greeks or (position.greeks.delta == 0 and position.greeks.gamma == 0):
                errors.append("Option has zero Greeks")
            
            # Delta sanity check (per position, not per contract)
            if position.greeks:
                expected_max_delta = abs(position.quantity) * 1.1  # Allow 10% margin
                if abs(position.greeks.delta) > expected_max_delta:
                    errors.append(f"Delta {position.greeks.delta:.2f} seems too high for qty {position.quantity}")
        
        # Check prices
        if position.current_price and position.current_price < 0:
            errors.append("Negative current price")
        
        return (len(errors) == 0, errors)
    
    @staticmethod
    def compare_with_broker(
        db_positions: List[dm.Position],
        broker_positions: List[dm.Position]
    ) -> Dict:
        """
        Compare database positions with broker positions
        
        Returns summary of differences
        """
        
        # Create lookups by symbol
        db_by_symbol = {}
        for pos in db_positions:
            key = pos.symbol.get_option_symbol() if pos.symbol.asset_type == dm.AssetType.OPTION else pos.symbol.ticker
            db_by_symbol[key] = pos
        
        broker_by_symbol = {}
        for pos in broker_positions:
            key = pos.symbol.get_option_symbol() if pos.symbol.asset_type == dm.AssetType.OPTION else pos.symbol.ticker
            broker_by_symbol[key] = pos
        
        # Find discrepancies
        missing_in_db = []
        extra_in_db = []
        quantity_mismatch = []
        greeks_mismatch = []
        price_mismatch = []
        
        # Check broker positions
        for symbol, broker_pos in broker_by_symbol.items():
            db_pos = db_by_symbol.get(symbol)
            
            if not db_pos:
                missing_in_db.append({
                    'symbol': symbol,
                    'broker_quantity': broker_pos.quantity,
                    'broker_market_value': float(broker_pos.market_value)
                })
            else:
                # Check quantity
                if broker_pos.quantity != db_pos.quantity:
                    quantity_mismatch.append({
                        'symbol': symbol,
                        'broker': broker_pos.quantity,
                        'db': db_pos.quantity
                    })
                
                # Check Greeks (allow 5% tolerance)
                if broker_pos.greeks and db_pos.greeks:
                    delta_diff = abs(broker_pos.greeks.delta - db_pos.greeks.delta)
                    if delta_diff > abs(broker_pos.greeks.delta) * 0.05:
                        greeks_mismatch.append({
                            'symbol': symbol,
                            'broker_delta': float(broker_pos.greeks.delta),
                            'db_delta': float(db_pos.greeks.delta),
                            'diff': float(delta_diff)
                        })
                
                # Check prices (allow 1% tolerance for market movement)
                if broker_pos.current_price and db_pos.current_price:
                    price_diff = abs(broker_pos.current_price - db_pos.current_price)
                    if price_diff > broker_pos.current_price * Decimal('0.01'):
                        price_mismatch.append({
                            'symbol': symbol,
                            'broker_price': float(broker_pos.current_price),
                            'db_price': float(db_pos.current_price),
                            'diff': float(price_diff)
                        })
        
        # Check for extras in DB
        for symbol, db_pos in db_by_symbol.items():
            if symbol not in broker_by_symbol:
                extra_in_db.append({
                    'symbol': symbol,
                    'db_quantity': db_pos.quantity,
                    'db_market_value': float(db_pos.market_value)
                })
        
        is_valid = (
            len(missing_in_db) == 0 and
            len(extra_in_db) == 0 and
            len(quantity_mismatch) == 0
        )
        
        return {
            'is_valid': is_valid,
            'summary': {
                'db_count': len(db_positions),
                'broker_count': len(broker_positions),
                'missing_in_db': len(missing_in_db),
                'extra_in_db': len(extra_in_db),
                'quantity_mismatches': len(quantity_mismatch),
                'greeks_mismatches': len(greeks_mismatch),
                'price_mismatches': len(price_mismatch)
            },
            'details': {
                'missing_in_db': missing_in_db,
                'extra_in_db': extra_in_db,
                'quantity_mismatch': quantity_mismatch,
                'greeks_mismatch': greeks_mismatch,
                'price_mismatch': price_mismatch
            }
        }


class TradeValidator:
    """Validate trade data"""
    
    @staticmethod
    def validate_trade(trade: dm.Trade) -> Tuple[bool, List[str]]:
        """Validate a trade"""
        errors = []
        
        # Check legs
        if not trade.legs:
            errors.append("Trade has no legs")
        
        # Check each leg
        for i, leg in enumerate(trade.legs):
            if leg.quantity == 0:
                errors.append(f"Leg {i+1} has zero quantity")
            
            if not leg.symbol:
                errors.append(f"Leg {i+1} missing symbol")
        
        # Check Greeks consistency
        if trade.legs:
            total_greeks = trade.total_greeks()
            # Validate Greeks make sense for the strategy
            
        return (len(errors) == 0, errors)


class PortfolioValidator:
    """Validate portfolio-level data"""
    
    @staticmethod
    def validate_portfolio_greeks(portfolio: dm.Portfolio, positions: List[dm.Position]) -> Tuple[bool, List[str]]:
        """Validate that portfolio Greeks match sum of position Greeks"""
        errors = []
        
        # Calculate expected Greeks from positions
        expected_delta = sum(p.greeks.delta if p.greeks else 0 for p in positions)
        expected_gamma = sum(p.greeks.gamma if p.greeks else 0 for p in positions)
        expected_theta = sum(p.greeks.theta if p.greeks else 0 for p in positions)
        expected_vega = sum(p.greeks.vega if p.greeks else 0 for p in positions)
        
        # Compare with portfolio Greeks (allow 1% tolerance)
        if portfolio.portfolio_greeks:
            if abs(portfolio.portfolio_greeks.delta - expected_delta) > abs(expected_delta) * Decimal('0.01'):
                errors.append(f"Portfolio delta mismatch: portfolio={portfolio.portfolio_greeks.delta:.2f}, expected={expected_delta:.2f}")
            
            if abs(portfolio.portfolio_greeks.theta - expected_theta) > abs(expected_theta) * Decimal('0.01'):
                errors.append(f"Portfolio theta mismatch: portfolio={portfolio.portfolio_greeks.theta:.2f}, expected={expected_theta:.2f}")
        
        return (len(errors) == 0, errors)