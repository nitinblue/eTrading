"""
Position Sync Service - Synchronize positions from broker to database

Strategy: CLEAR AND REBUILD
- Delete all existing positions for portfolio
- Insert fresh positions from broker
- Simple, reliable, no duplicate issues
"""

import logging
from typing import List, Dict
from datetime import datetime

from trading_cotrader.core.database.session import Session
from trading_cotrader.repositories.position import PositionRepository
from trading_cotrader.repositories.portfolio import PortfolioRepository
import trading_cotrader.core.models.domain as dm

logger = logging.getLogger(__name__)


class PositionSyncService:
    """Handle position synchronization from broker to database"""
    
    def __init__(self, session: Session):
        self.session = session
        self.position_repo = PositionRepository(session)
        self.portfolio_repo = PortfolioRepository(session)
    
    def sync_positions(self, portfolio_id: str, broker_positions: List[dm.Position]) -> Dict[str, int]:
        """
        Sync positions using CLEAR AND REBUILD strategy
        
        This is simpler and more reliable than update-or-insert:
        1. Delete all existing positions
        2. Insert all broker positions
        3. No chance of duplicates
        
        Args:
            portfolio_id: Portfolio ID
            broker_positions: Fresh positions from broker
            
        Returns:
            Dict with sync statistics
        """
        logger.info(f"Starting position sync for portfolio {portfolio_id}")
        logger.info(f"Received {len(broker_positions)} positions from broker")
        
        # Validate broker positions
        valid_positions = []
        invalid_count = 0
        
        for pos in broker_positions:
            is_valid, errors = self._validate_position(pos)
            if is_valid:
                valid_positions.append(pos)
            else:
                logger.warning(f"Invalid position {pos.symbol.ticker}: {errors}")
                invalid_count += 1
        
        logger.info(f"Valid positions: {len(valid_positions)}, Invalid: {invalid_count}")
        
        # STEP 1: Clear existing positions
        deleted_count = self.position_repo.delete_by_portfolio(portfolio_id)
        logger.info(f"Deleted {deleted_count} existing positions")
        
        # STEP 2: Insert fresh positions
        created_count = 0
        failed_count = 0
        
        for broker_pos in valid_positions:
            try:
                created = self.position_repo.create_from_domain(broker_pos, portfolio_id)
                if created:
                    created_count += 1
                else:
                    failed_count += 1
                    logger.error(f"Failed to create position for {broker_pos.symbol.ticker}")
            except Exception as e:
                failed_count += 1
                logger.error(f"Error creating position {broker_pos.symbol.ticker}: {e}")
        
        # STEP 3: Commit transaction
        try:
            self.session.commit()
            logger.info(f"✓ Transaction committed")
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to commit transaction: {e}")
            raise
        
        # STEP 4: Verify final count
        final_positions = self.position_repo.get_by_portfolio(portfolio_id)
        final_count = len(final_positions)
        
        logger.info(f"✓ Position sync complete:")
        logger.info(f"  Deleted: {deleted_count}")
        logger.info(f"  Created: {created_count}")
        logger.info(f"  Failed: {failed_count}")
        logger.info(f"  Final count: {final_count}")
        
        if final_count != created_count:
            logger.error(f"❌ COUNT MISMATCH: Created {created_count} but DB has {final_count}")
        
        return {
            'deleted': deleted_count,
            'created': created_count,
            'failed': failed_count,
            'invalid': invalid_count,
            'final_count': final_count,
            'success': final_count == created_count
        }
    
    def _validate_position(self, position: dm.Position) -> tuple[bool, List[str]]:
        
        """
        Validate position data - RELAXED GREEKS REQUIREMENT
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        warnings = []
        
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
        
        # Check Greeks for options - CHANGED TO WARNING INSTEAD OF ERROR
        if position.symbol.asset_type == dm.AssetType.OPTION:
            if not position.greeks or (position.greeks.delta == 0 and position.greeks.gamma == 0):
                # CHANGED: This is now just a warning, not an error
                warnings.append("Option has zero Greeks - will calculate later")
                logger.info(f"Position {position.symbol.ticker} accepted without Greeks - will calculate separately")
            else:
                # Delta sanity check (only if we have Greeks)
                expected_max_delta = abs(position.quantity) * 1.1
                if abs(position.greeks.delta) > expected_max_delta:
                    warnings.append(f"Delta {position.greeks.delta:.2f} seems high for qty {position.quantity}")
        
        # Check prices
        if position.current_price and position.current_price < 0:
            errors.append("Negative current price")
        
        # Check broker position ID
        if not position.broker_position_id:
            warnings.append("Missing broker_position_id")
        
        # Log warnings
        if warnings:
            logger.debug(f"Warnings for {position.symbol.ticker}: {warnings}")
        
        # Only fail on actual errors, not missing Greeks
        return (len(errors) == 0, errors)
    
    def get_sync_summary(self, portfolio_id: str) -> Dict:
        """Get summary of current positions"""
        positions = self.position_repo.get_by_portfolio(portfolio_id)
        
        total_market_value = sum(p.market_value for p in positions)
        total_pnl = sum(p.unrealized_pnl() for p in positions)
        
        # Group by asset type
        by_type = {}
        for pos in positions:
            asset_type = pos.symbol.asset_type.value
            if asset_type not in by_type:
                by_type[asset_type] = []
            by_type[asset_type].append(pos)
        
        # Calculate Greeks
        total_delta = sum(p.greeks.delta if p.greeks else 0 for p in positions)
        total_gamma = sum(p.greeks.gamma if p.greeks else 0 for p in positions)
        total_theta = sum(p.greeks.theta if p.greeks else 0 for p in positions)
        total_vega = sum(p.greeks.vega if p.greeks else 0 for p in positions)
        
        return {
            'total_positions': len(positions),
            'total_market_value': float(total_market_value),
            'total_unrealized_pnl': float(total_pnl),
            'by_asset_type': {k: len(v) for k, v in by_type.items()},
            'greeks': {
                'delta': float(total_delta),
                'gamma': float(total_gamma),
                'theta': float(total_theta),
                'vega': float(total_vega)
            }
        }