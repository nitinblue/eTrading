"""
Data Validation Runner - Verify database matches Tastytrade

Run this after sync to ensure data accuracy.
"""

import sys
import asyncio
import logging
from pathlib import Path
from tabulate import tabulate

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import get_settings, setup_logging
from core.database.session import session_scope
from trading_cotrader.adapters.tastytrade_adapter import TastytradeAdapter
from repositories.portfolio import PortfolioRepository
from repositories.position import PositionRepository
from core.validation.validators import PositionValidator

logger = logging.getLogger(__name__)


class ValidationRunner:
    """Validate database against broker data"""
    
    def __init__(self):
        self.settings = get_settings()
        self.broker = None
        self.portfolio = None
    
    async def run(self):
        """Main validation workflow"""
        
        print("\n" + "=" * 80)
        print("DATA VALIDATION - Database vs Tastytrade")
        print("=" * 80)
        print()
        
        # Step 1: Connect to broker
        if not await self._connect_broker():
            return False
        
        # Step 2: Load portfolio
        if not await self._load_portfolio():
            return False
        
        # Step 3: Validate positions
        if not await self._validate_positions():
            return False
        
        # Step 4: Validate balance
        if not await self._validate_balance():
            return False
        
        # Step 5: Validate Greeks
        if not await self._validate_greeks():
            return False
        
        print("\n" + "=" * 80)
        print("VALIDATION COMPLETE")
        print("=" * 80)
        print()
        
        return True
    
    async def _connect_broker(self) -> bool:
        """Connect to Tastytrade"""
        print("📡 Connecting to Tastytrade...")
        
        try:
            self.broker = TastytradeAdapter(
                account_number=self.settings.tastytrade_account_number,
                is_paper=self.settings.is_paper_trading
            )
            
            if not self.broker.authenticate():
                print("❌ Failed to authenticate")
                return False
            
            print(f"✓ Connected to account: {self.broker.account_id}")
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    async def _load_portfolio(self) -> bool:
        """Load portfolio from database"""
        print("\n📂 Loading portfolio from database...")
        
        try:
            with session_scope() as session:
                portfolio_repo = PortfolioRepository(session)
                self.portfolio = portfolio_repo.get_by_account(
                    broker="tastytrade",
                    account_id=self.broker.account_id
                )
            
            if not self.portfolio:
                print("❌ Portfolio not found in database")
                print("   Run sync_portfolio.py first")
                return False
            
            print(f"✓ Found portfolio: {self.portfolio.name}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to load portfolio: {e}")
            return False
    
    async def _validate_positions(self) -> bool:
        """Validate positions match between DB and broker"""
        print("\n📊 Validating positions...")
        
        try:
            # Fetch from both sources
            broker_positions = await asyncio.to_thread(self.broker.get_positions)
            
            with session_scope() as session:
                position_repo = PositionRepository(session)
                db_positions = position_repo.get_by_portfolio(self.portfolio.id)
            
            print(f"  Broker positions: {len(broker_positions)}")
            print(f"  Database positions: {len(db_positions)}")
            
            # Compare
            validator = PositionValidator()
            comparison = validator.compare_with_broker(db_positions, broker_positions)
            
            # Display results
            if comparison['is_valid']:
                print("✅ All positions match!")
            else:
                print("⚠️  Discrepancies found:")
                
                summary = comparison['summary']
                if summary['missing_in_db'] > 0:
                    print(f"  ❌ {summary['missing_in_db']} positions missing in DB")
                    self._display_missing_positions(comparison['details']['missing_in_db'])
                
                if summary['extra_in_db'] > 0:
                    print(f"  ❌ {summary['extra_in_db']} extra positions in DB")
                    self._display_extra_positions(comparison['details']['extra_in_db'])
                
                if summary['quantity_mismatches'] > 0:
                    print(f"  ❌ {summary['quantity_mismatches']} quantity mismatches")
                    self._display_quantity_mismatches(comparison['details']['quantity_mismatch'])
                
                if summary['greeks_mismatches'] > 0:
                    print(f"  ⚠️  {summary['greeks_mismatches']} Greeks mismatches (may be due to market movement)")
                
                if summary['price_mismatches'] > 0:
                    print(f"  ⚠️  {summary['price_mismatches']} price mismatches (market movement)")
            
            return comparison['is_valid']
            
        except Exception as e:
            print(f"❌ Position validation failed: {e}")
            logger.exception("Full error:")
            return False
    
    async def _validate_balance(self) -> bool:
        """Validate account balance"""
        print("\n💰 Validating account balance...")
        
        try:
            balance = await asyncio.to_thread(self.broker.get_account_balance)
            
            broker_cash = balance['cash_balance']
            db_cash = self.portfolio.cash_balance
            
            diff = abs(broker_cash - db_cash)
            
            if diff < 1:  # Within $1
                print(f"✅ Cash balance matches: ${broker_cash:,.2f}")
                return True
            else:
                print(f"⚠️  Cash balance mismatch:")
                print(f"  Broker:   ${broker_cash:,.2f}")
                print(f"  Database: ${db_cash:,.2f}")
                print(f"  Diff:     ${diff:,.2f}")
                return False
            
        except Exception as e:
            print(f"❌ Balance validation failed: {e}")
            return False
    
    async def _validate_greeks(self) -> bool:
        """Validate Greeks calculations"""
        print("\n🧮 Validating Greeks...")
        
        try:
            with session_scope() as session:
                position_repo = PositionRepository(session)
                positions = position_repo.get_by_portfolio(self.portfolio.id)
            
            # Calculate expected Greeks
            expected_delta = sum(p.greeks.delta if p.greeks else 0 for p in positions)
            expected_theta = sum(p.greeks.theta if p.greeks else 0 for p in positions)
            
            # Compare with portfolio Greeks
            if self.portfolio.portfolio_greeks:
                delta_diff = abs(self.portfolio.portfolio_greeks.delta - expected_delta)
                theta_diff = abs(self.portfolio.portfolio_greeks.theta - expected_theta)
                
                if delta_diff < 1 and theta_diff < 1:
                    print(f"✅ Greeks match:")
                    print(f"  Delta: {self.portfolio.portfolio_greeks.delta:.2f}")
                    print(f"  Theta: {self.portfolio.portfolio_greeks.theta:.2f}")
                    return True
                else:
                    print(f"⚠️  Greeks mismatch:")
                    print(f"  Portfolio Delta: {self.portfolio.portfolio_greeks.delta:.2f}")
                    print(f"  Expected Delta:  {expected_delta:.2f}")
                    print(f"  Portfolio Theta: {self.portfolio.portfolio_greeks.theta:.2f}")
                    print(f"  Expected Theta:  {expected_theta:.2f}")
                    return False
            else:
                print("⚠️  No portfolio Greeks found")
                return False
            
        except Exception as e:
            print(f"❌ Greeks validation failed: {e}")
            return False
    
    def _display_missing_positions(self, missing):
        """Display positions missing in DB"""
        if not missing:
            return
        
        print("\n  Missing in Database:")
        headers = ["Symbol", "Quantity", "Market Value"]
        rows = [[m['symbol'], m['broker_quantity'], f"${m['broker_market_value']:,.2f}"] 
                for m in missing[:10]]  # Show first 10
        print("  " + tabulate(rows, headers=headers, tablefmt="simple").replace("\n", "\n  "))
    
    def _display_extra_positions(self, extra):
        """Display extra positions in DB"""
        if not extra:
            return
        
        print("\n  Extra in Database:")
        headers = ["Symbol", "Quantity", "Market Value"]
        rows = [[e['symbol'], e['db_quantity'], f"${e['db_market_value']:,.2f}"] 
                for e in extra[:10]]
        print("  " + tabulate(rows, headers=headers, tablefmt="simple").replace("\n", "\n  "))
    
    def _display_quantity_mismatches(self, mismatches):
        """Display quantity mismatches"""
        if not mismatches:
            return
        
        print("\n  Quantity Mismatches:")
        headers = ["Symbol", "Broker", "Database", "Diff"]
        rows = [[m['symbol'], m['broker'], m['db'], m['broker'] - m['db']] 
                for m in mismatches[:10]]
        print("  " + tabulate(rows, headers=headers, tablefmt="simple").replace("\n", "\n  "))


async def main():
    """Main entry point"""
    
    # Setup
    setup_logging()
    
    try:
        runner = ValidationRunner()
        success = await runner.run()
        
        if success:
            print("✅ All validations passed!")
            return 0
        else:
            print("⚠️  Some validations failed - review above")
            return 1
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        logger.exception("Full error:")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))