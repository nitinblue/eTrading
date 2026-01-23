"""
Real Risk Check - Validate against actual portfolio from database

This connects the risk manager to your real portfolio data.
"""

import sys
from pathlib import Path
from decimal import Decimal

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import setup_logging, get_settings
from core.database.session import session_scope
from repositories.portfolio import PortfolioRepository
from repositories.position import PositionRepository
from repositories.trade import TradeRepository
from services.risk_manager import RiskManager, RiskCheckResult
import core.models.domain as dm
import logging

logger = logging.getLogger(__name__)


class RealRiskChecker:
    """
    Risk checker that uses ACTUAL portfolio data from your database
    
    This is the real integration - validates against your live positions
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.risk_manager = RiskManager("risk_limits.yaml")
        self.portfolio = None
        self.positions = []
        self.trades = []
    
    def load_portfolio_state(self) -> bool:
        """Load current portfolio state from database"""
        try:
            with session_scope() as session:
                portfolio_repo = PortfolioRepository(session)
                position_repo = PositionRepository(session)
                trade_repo = TradeRepository(session)
                
                # Get portfolio
                portfolios = portfolio_repo.get_all_portfolios()
                if not portfolios:
                    logger.error("No portfolio found. Run sync first.")
                    return False
                
                self.portfolio = portfolios[0]
                
                # Get positions
                self.positions = position_repo.get_by_portfolio(self.portfolio.id)
                
                # Get trades
                self.trades = trade_repo.get_by_portfolio(self.portfolio.id, open_only=True)
                
                logger.info(f"✓ Loaded portfolio: {self.portfolio.name}")
                logger.info(f"  Positions: {len(self.positions)}")
                logger.info(f"  Open trades: {len(self.trades)}")
                logger.info(f"  Total equity: ${self.portfolio.total_equity:,.2f}")
                logger.info(f"  Portfolio delta: {self.portfolio.portfolio_greeks.delta:.2f}")
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to load portfolio: {e}")
            return False
    
    def check_proposed_trade(self, proposed_trade: dm.Trade) -> RiskCheckResult:
        """
        Check a proposed trade against your REAL portfolio
        
        Args:
            proposed_trade: The trade you're considering
            
        Returns:
            RiskCheckResult with all violations
        """
        if not self.portfolio:
            raise ValueError("Portfolio not loaded. Call load_portfolio_state() first.")
        
        logger.info(f"\n{'='*80}")
        logger.info(f"RISK CHECK: {proposed_trade.underlying_symbol}")
        logger.info(f"{'='*80}")
        
        # Run full risk validation
        result = self.risk_manager.validate_trade(
            proposed_trade=proposed_trade,
            current_portfolio=self.portfolio,
            current_positions=self.positions,
            current_trades=self.trades
        )
        
        return result
    
    def display_current_risk_status(self):
        """Display current portfolio risk metrics"""
        if not self.portfolio:
            print("Portfolio not loaded")
            return
        
        limits = self.risk_manager.limits
        
        print("\n" + "="*80)
        print("CURRENT PORTFOLIO RISK STATUS")
        print("="*80)
        
        # Greeks status
        print("\n📊 Greeks:")
        if self.portfolio.portfolio_greeks:
            greeks = self.portfolio.portfolio_greeks
            greek_limits = limits['greeks']
            
            delta_usage = Decimal((abs(greeks.delta)) / Decimal(greek_limits['max_portfolio_delta'])) * Decimal("100")
            print(f"  Delta:  {greeks.delta:>8.2f} / ±{greek_limits['max_portfolio_delta']:.0f}  ({delta_usage:.1f}% used)")
            
            gamma_usage = Decimal((abs(greeks.gamma)) / Decimal(greek_limits['max_portfolio_gamma'])) * Decimal("100")
            print(f"  Gamma:  {greeks.gamma:>8.4f} / {greek_limits['max_portfolio_gamma']:.1f}  ({gamma_usage:.1f}% used)")
            
            theta_min = greek_limits['min_portfolio_theta']
            theta_pct = (Decimal(greeks.theta) / Decimal(theta_min)) * Decimal("100") if theta_min != 0 else 0
            print(f"  Theta:  {greeks.theta:>8.2f} / {theta_min:.0f}  ({theta_pct:.1f}% of max)")
            
            print(f"  Vega:   {greeks.vega:>8.2f}")
        
        # Portfolio value
        print(f"\n💰 Capital:")
        print(f"  Total Equity:  ${self.portfolio.total_equity:>12,.2f}")
        print(f"  Cash Balance:  ${self.portfolio.cash_balance:>12,.2f}")
        print(f"  Buying Power:  ${self.portfolio.buying_power:>12,.2f}")
        
        # Position count
        print(f"\n📈 Positions:")
        print(f"  Total positions: {len(self.positions)}")
        print(f"  Open trades:     {len(self.trades)}")
        
        # Concentration
        print(f"\n🎯 Concentration:")
        by_underlying = {}
        for pos in self.positions:
            ticker = pos.symbol.ticker
            if ticker not in by_underlying:
                by_underlying[ticker] = Decimal('0')
            by_underlying[ticker] += abs(pos.market_value)
        
        # Sort by exposure
        sorted_underlyings = sorted(
            by_underlying.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        portfolio_value = self.portfolio.total_equity
        max_per_underlying = limits['concentration']['max_percent_per_underlying']
        
        for ticker, exposure in sorted_underlyings[:5]:  # Top 5
            pct = (exposure / portfolio_value) * 100 if portfolio_value > 0 else 0
            status = "⚠️" if pct > max_per_underlying else "✓"
            print(f"  {status} {ticker:>6}: ${exposure:>10,.2f}  ({pct:>5.1f}%)")
        
        # Risk capacity
        print(f"\n🛡️  Available Risk Capacity:")
        max_single_trade = limits['portfolio']['max_single_trade_risk_percent']
        max_trade_value = (portfolio_value * Decimal(max_single_trade) / 100)
        print(f"  Max risk per trade: ${max_trade_value:,.2f} ({max_single_trade}%)")
        
        # Delta capacity
        if self.portfolio.portfolio_greeks:
            delta_capacity = Decimal(greek_limits['max_portfolio_delta']) - Decimal(abs(greeks.delta))
            print(f"  Delta capacity:     {delta_capacity:.2f}")
        
        print()


def create_example_trade() -> dm.Trade:
    """Create an example trade for testing"""
    print("\n" + "="*80)
    print("EXAMPLE: Creating a bullish SPY trade")
    print("="*80)
    
    # Example: Buy 10 SPY shares (simple directional bet)
    spy_symbol = dm.Symbol(
        ticker="SPY",
        asset_type=dm.AssetType.EQUITY
    )
    
    leg = dm.Leg(
        symbol=spy_symbol,
        quantity=10,  # Buy 10 shares
        entry_price=Decimal('580.00'),
        side=dm.OrderSide.BUY
    )
    
    # Stock has delta = quantity
    leg.greeks = dm.Greeks(delta=Decimal('10'))
    
    trade = dm.Trade(
        underlying_symbol="SPY",
        legs=[leg]
    )
    
    print(f"  Symbol: SPY")
    print(f"  Quantity: 10 shares")
    print(f"  Cost: ${10 * 580:,.2f}")
    print(f"  Delta: +10")
    
    return trade


def main():
    """Main entry point"""
    setup_logging()
    
    print("\n" + "="*80)
    print("REAL PORTFOLIO RISK CHECK")
    print("="*80)
    
    # Initialize
    checker = RealRiskChecker()
    
    # Load actual portfolio
    print("\n1. Loading your actual portfolio from database...")
    if not checker.load_portfolio_state():
        print("❌ Failed to load portfolio")
        return 1
    
    # Display current status
    print("\n2. Current risk status:")
    checker.display_current_risk_status()
    
    # Create example trade
    print("\n3. Testing proposed trade:")
    proposed_trade = create_example_trade()
    
    # Check against real portfolio
    print("\n4. Running risk validation...")
    result = checker.check_proposed_trade(proposed_trade)
    
    # Display results
    print("\n" + "="*80)
    print("RISK CHECK RESULTS")
    print("="*80)
    print(result.summary())
    print()
    
    if result.passed:
        print("✅ Trade would be ALLOWED")
        print("\n💡 To execute this trade, integrate with broker adapter")
    else:
        print("🚫 Trade would be BLOCKED")
        print("\n💡 Adjust trade size or wait for portfolio Greeks to change")
    
    print("\n" + "="*80)
    
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())