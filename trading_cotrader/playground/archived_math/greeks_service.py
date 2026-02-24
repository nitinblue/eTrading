"""
Real-Time Greeks Service

Continuously updates Greeks for all positions:
1. Fetch market data (spot price, bid/ask)
2. Calculate Greeks using our engine
3. Compare with broker Greeks
4. Alert on arbitrage opportunities
5. Update database
"""

from typing import Dict, List
from datetime import datetime, timedelta
import asyncio
import logging
from decimal import Decimal


from analytics.greeks.engine import GreeksEngine, GreeksCalculation
import core.models.domain as dm
from core.database.session import session_scope
from repositories.position import PositionRepository

logger = logging.getLogger(__name__)


class RealTimeGreeksService:
    """
    Real-time Greeks calculation and monitoring
    
    Runs continuously, updates every 30 seconds (or configurable interval)
    """
    
    def __init__(self, broker_adapter, update_interval_seconds: int = 30):
        self.broker = broker_adapter
        self.greeks_engine = GreeksEngine()
        self.update_interval = update_interval_seconds
        self.is_running = False
        self.arbitrage_opportunities = []
        
        # Performance tracking
        self.updates_count = 0
        self.last_update_time = None
        self.calculation_errors = 0
    
    async def start(self, portfolio_id: str):
        """Start real-time Greeks monitoring"""
        
        self.is_running = True
        logger.info("🚀 Starting real-time Greeks service...")
        
        while self.is_running:
            try:
                await self._update_cycle(portfolio_id)
                self.updates_count += 1
                self.last_update_time = datetime.utcnow()
                
                # Log status every 10 updates
                if self.updates_count % 10 == 0:
                    logger.info(
                        f"✓ Greeks updated: {self.updates_count} cycles, "
                        f"{len(self.arbitrage_opportunities)} opportunities detected"
                    )
                
                # Wait for next cycle
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in Greeks update cycle: {e}")
                self.calculation_errors += 1
                await asyncio.sleep(5)  # Brief pause on error
    
    def stop(self):
        """Stop the service"""
        self.is_running = False
        logger.info("Stopping real-time Greeks service...")
    
    async def _update_cycle(self, portfolio_id: str):
        """Single update cycle - calculate Greeks for all positions"""
        
        with session_scope() as session:
            position_repo = PositionRepository(session)
            positions = position_repo.get_by_portfolio(portfolio_id)
            
            if not positions:
                logger.debug("No positions to update")
                return
            
            logger.debug(f"Updating Greeks for {len(positions)} positions...")
            
            # Get current market data
            market_data = await self._fetch_market_data(positions)
            
            # Calculate Greeks for each position
            for position in positions:
                try:
                    if position.symbol.asset_type != dm.AssetType.OPTION:
                        continue  # Skip non-options
                    
                    # Get market data for this option
                    symbol_key = position.symbol.get_option_symbol()
                    data = market_data.get(symbol_key)
                    
                    if not data:
                        logger.warning(f"No market data for {symbol_key}")
                        continue
                    
                    # Calculate Greeks
                    greeks = await self._calculate_greeks_for_position(
                        position, data
                    )
                    
                    if greeks:
                        # Update position
                        position.greeks = dm.Greeks(
                            delta=greeks.delta,
                            gamma=greeks.gamma,
                            theta=greeks.theta,
                            vega=greeks.vega,
                            rho=greeks.rho,
                            timestamp=greeks.timestamp
                        )
                        
                        # Save to database
                        position_repo.update_from_domain(position)
                        
                        # Check for arbitrage
                        if data.get('broker_greeks'):
                            opportunities = self.greeks_engine.detect_arbitrage_opportunities(
                                greeks,
                                data['broker_greeks'],
                                position.quantity
                            )
                            
                            if opportunities:
                                self._handle_arbitrage_opportunities(
                                    position, opportunities
                                )
                
                except Exception as e:
                    logger.error(f"Error updating Greeks for {position.symbol.ticker}: {e}")
                    continue
            
            session.commit()
    
    async def _fetch_market_data(self, positions: List[dm.Position]) -> Dict:
        """
        Fetch current market data for all option positions
        
        Returns dict mapping symbol -> market data
        """
        
        market_data = {}
        
        for position in positions:
            if position.symbol.asset_type != dm.AssetType.OPTION:
                continue
            
            try:
                symbol_key = position.symbol.get_option_symbol()
                
                # Get quote from broker
                quote = await asyncio.to_thread(
                    self.broker.get_quote,
                    symbol_key
                )
                
                if quote:
                    # Get underlying price
                    underlying_quote = await asyncio.to_thread(
                        self.broker.get_quote,
                        position.symbol.ticker
                    )
                    
                    market_data[symbol_key] = {
                        'bid': quote.get('bid', 0),
                        'ask': quote.get('ask', 0),
                        'mid': (quote.get('bid', 0) + quote.get('ask', 0)) / 2,
                        'underlying_price': underlying_quote.get('last', 0),
                        'broker_greeks': quote.get('greeks'),
                        'broker_iv': quote.get('implied_volatility'),
                        'timestamp': datetime.utcnow()
                    }
            
            except Exception as e:
                logger.debug(f"Could not fetch market data for {position.symbol.ticker}: {e}")
                continue
        
        return market_data
    
    async def _calculate_greeks_for_position(
        self,
        position: dm.Position,
        market_data: Dict
    ) -> GreeksCalculation:
        """Calculate Greeks for a single position"""
        
        try:
            symbol = position.symbol
            
            # Calculate time to expiry
            time_to_expiry = (symbol.expiration - datetime.utcnow()).total_seconds() / (365.25 * 24 * 3600)
            
            if time_to_expiry <= 0:
                logger.info(f"{symbol.ticker} expired")
                return self.greeks_engine._create_expired_greeks()
            
            # Calculate IV from market price
            mid_price = market_data['mid']
            underlying_price = market_data['underlying_price']
            
            calculated_iv = self.greeks_engine.calculate_implied_volatility(
                option_type=symbol.option_type.value,
                market_price=mid_price,
                spot_price=underlying_price,
                strike=float(symbol.strike),
                time_to_expiry=time_to_expiry
            )
            
            # Calculate Greeks using calculated IV
            greeks = self.greeks_engine.calculate_greeks(
                option_type=symbol.option_type.value,
                spot_price=underlying_price,
                strike=float(symbol.strike),
                time_to_expiry=time_to_expiry,
                volatility=calculated_iv,
                broker_greeks=market_data.get('broker_greeks')
            )
            
            # Multiply by quantity for position-level Greeks
            greeks.delta *= abs(position.quantity)
            greeks.gamma *= abs(position.quantity)
            greeks.theta *= abs(position.quantity)
            greeks.vega *= abs(position.quantity)
            greeks.rho *= abs(position.quantity)
            
            return greeks
        
        except Exception as e:
            logger.error(f"Greeks calculation failed: {e}")
            return None
    
    def _handle_arbitrage_opportunities(
        self,
        position: dm.Position,
        opportunities: List[Dict]
    ):
        """Handle detected arbitrage opportunities"""
        
        for opp in opportunities:
            # Store for later analysis
            self.arbitrage_opportunities.append({
                'position_id': position.id,
                'symbol': position.symbol.ticker,
                'timestamp': datetime.utcnow(),
                **opp
            })
            
            # Log high-severity opportunities
            if opp['severity'] == 'HIGH':
                logger.warning(
                    f"🚨 HIGH SEVERITY: {opp['type']} on {position.symbol.ticker}\n"
                    f"   {opp['description']}\n"
                    f"   Action: {opp['action']}"
                )
    
    def get_arbitrage_report(self) -> Dict:
        """Get summary of detected arbitrage opportunities"""
        
        if not self.arbitrage_opportunities:
            return {
                'total_opportunities': 0,
                'opportunities': []
            }
        
        # Group by type
        by_type = {}
        for opp in self.arbitrage_opportunities:
            opp_type = opp['type']
            if opp_type not in by_type:
                by_type[opp_type] = []
            by_type[opp_type].append(opp)
        
        return {
            'total_opportunities': len(self.arbitrage_opportunities),
            'by_type': {k: len(v) for k, v in by_type.items()},
            'high_severity': len([o for o in self.arbitrage_opportunities if o['severity'] == 'HIGH']),
            'opportunities': self.arbitrage_opportunities[-10:]  # Last 10
        }


# ============================================================================
# Integration with Position Sync
# ============================================================================

class GreeksIntegratedPositionSync:
    """
    Position sync with integrated Greeks calculation
    
    Flow:
    1. Fetch positions from broker (may have no Greeks)
    2. Accept ALL valid positions (even without Greeks)
    3. Immediately calculate Greeks using our engine
    4. Store positions with calculated Greeks
    5. Start real-time monitoring
    """
    
    def __init__(self, broker_adapter):
        self.broker = broker_adapter
        self.greeks_engine = GreeksEngine()
        self.realtime_service = RealTimeGreeksService(broker_adapter)
    
    async def sync_with_greeks(self, portfolio_id: str) -> Dict:
        """
        Sync positions and calculate Greeks
        
        This replaces the old sync that required broker Greeks
        """
        
        logger.info("📊 Syncing positions with Greeks calculation...")
        
        # Step 1: Fetch positions from broker
        broker_positions = await asyncio.to_thread(
            self.broker.get_positions
        )
        
        logger.info(f"Fetched {len(broker_positions)} positions from broker")
        
        # Step 2: Calculate Greeks for each position
        positions_with_greeks = []
        
        for pos in broker_positions:
            try:
                # If position already has Greeks, use them
                if pos.greeks and pos.greeks.delta != 0:
                    positions_with_greeks.append(pos)
                    logger.debug(f"✓ {pos.symbol.ticker}: Using broker Greeks")
                    continue
                
                # Calculate Greeks ourselves
                if pos.symbol.asset_type == dm.AssetType.OPTION:
                    logger.info(f"📐 Calculating Greeks for {pos.symbol.ticker}...")
                    
                    # Fetch market data
                    quote = await asyncio.to_thread(
                        self.broker.get_quote,
                        pos.symbol.get_option_symbol()
                    )
                    
                    underlying_quote = await asyncio.to_thread(
                        self.broker.get_quote,
                        pos.symbol.ticker
                    )
                    
                    if quote and underlying_quote:
                        # Calculate Greeks
                        time_to_expiry = (pos.symbol.expiration - datetime.utcnow()).total_seconds() / (365.25 * 24 * 3600)
                        
                        mid_price = (quote.get('bid', 0) + quote.get('ask', 0)) / 2
                        underlying_price = underlying_quote.get('last', 0)
                        
                        # Calculate IV
                        iv = self.greeks_engine.calculate_implied_volatility(
                            option_type=pos.symbol.option_type.value,
                            market_price=mid_price,
                            spot_price=underlying_price,
                            strike=float(pos.symbol.strike),
                            time_to_expiry=time_to_expiry
                        )
                        
                        # Calculate Greeks
                        greeks = self.greeks_engine.calculate_greeks(
                            option_type=pos.symbol.option_type.value,
                            spot_price=underlying_price,
                            strike=float(pos.symbol.strike),
                            time_to_expiry=time_to_expiry,
                            volatility=iv
                        )
                        
                        # Apply to position
                        pos.greeks = dm.Greeks(
                            delta=greeks.delta * abs(pos.quantity),
                            gamma=greeks.gamma * abs(pos.quantity),
                            theta=greeks.theta * abs(pos.quantity),
                            vega=greeks.vega * abs(pos.quantity),
                            rho=greeks.rho * abs(pos.quantity),
                            timestamp=greeks.timestamp
                        )
                        
                        logger.info(f"✓ {pos.symbol.ticker}: Δ={pos.greeks.delta:.2f}, Θ={pos.greeks.theta:.2f}")
                        positions_with_greeks.append(pos)
                    else:
                        logger.warning(f"❌ {pos.symbol.ticker}: No market data available")
                
                elif pos.symbol.asset_type == dm.AssetType.EQUITY:
                    # Stock delta = quantity
                    pos.greeks = dm.Greeks(
                        delta=Decimal(str(pos.quantity)),
                        timestamp=datetime.utcnow()
                    )
                    positions_with_greeks.append(pos)
            
            except Exception as e:
                logger.error(f"Error calculating Greeks for {pos.symbol.ticker}: {e}")
                continue
        
        # Step 3: Save to database
        with session_scope() as session:
            from services.position_sync import PositionSyncService
            sync_service = PositionSyncService(session)
            result = sync_service.sync_positions(portfolio_id, positions_with_greeks)
        
        logger.info(
            f"✅ Sync complete: {result['created']} positions with Greeks, "
            f"{result['invalid']} skipped"
        )
        
        # Step 4: Start real-time monitoring
        logger.info("🚀 Starting real-time Greeks monitoring...")
        asyncio.create_task(
            self.realtime_service.start(portfolio_id)
        )
        
        return result


# Example usage
async def main():
    from adapters.tastytrade_adapter import TastytradeAdapter
    
    # Connect to broker
    broker = TastytradeAdapter()
    broker.authenticate()
    
    # Create integrated sync service
    sync_service = GreeksIntegratedPositionSync(broker)
    
    # Sync with Greeks calculation
    result = await sync_service.sync_with_greeks("your-portfolio-id")
    
    print(f"Synced {result['created']} positions with calculated Greeks")
    
    # Let real-time service run
    await asyncio.sleep(300)  # Run for 5 minutes
    
    # Get arbitrage report
    report = sync_service.realtime_service.get_arbitrage_report()
    print(f"\nArbitrage Opportunities Detected: {report['total_opportunities']}")
    for opp in report['opportunities']:
        print(f"  - {opp['type']}: {opp['description']}")


if __name__ == "__main__":
    asyncio.run(main())
