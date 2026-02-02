"""
Step 5: Risk Factor Aggregation

Aggregates Greeks by RISK FACTOR (underlying), not by instrument.
This is the institutional view: "What's my MSFT delta?" not "What's my MSFT call delta?"

Uses:
- services/risk_factors/ for aggregation
- services/hedging/ for hedge recommendations
- Existing positions from previous harness steps
"""

import logging
from decimal import Decimal
from typing import List, Dict, Any, Optional
from tabulate import tabulate

# Import our new modules
from services.risk_factors import RiskFactorResolver, RiskFactorContainer
from services.hedging import HedgeCalculator

logger = logging.getLogger(__name__)


class RiskFactorAggregationStep:
    """
    Harness step for risk factor aggregation.
    
    Integrates with existing harness framework.
    """
    
    def __init__(self):
        self.name = "Risk Factor Aggregation"
        self.resolver = RiskFactorResolver()
        self.container: Optional[RiskFactorContainer] = None
        self.hedge_calculator = HedgeCalculator()
    
    def run(self, context: Dict[str, Any]) -> bool:
        """
        Run risk factor aggregation.
        
        Args:
            context: Dict containing:
                - 'positions': List[dm.Position]
                - 'portfolio': dm.Portfolio
                - 'market_data': Dict[str, Decimal] (underlying -> spot)
                
        Returns:
            True if successful
        """
        print(f"\n{'='*60}")
        print(f"STEP: {self.name}")
        print('='*60)
        
        positions = context.get('positions', [])
        market_data = context.get('market_data', {})
        
        if not positions:
            print("  ⚠️  No positions to analyze")
            return True
        
        # Step 1: Resolve positions to risk factors
        print(f"\n1. Resolving {len(positions)} positions to risk factors...")
        self.container = RiskFactorContainer()
        
        for position in positions:
            try:
                sensitivities = self.resolver.resolve_position(position)
                for sens in sensitivities:
                    self.container.add_sensitivity(sens)
            except Exception as e:
                logger.warning(f"Could not resolve {position.symbol.ticker}: {e}")
        
        print(f"   ✓ Resolved to {len(self.container.risk_factors)} risk factors")
        
        # Step 2: Display aggregated risk by underlying
        print("\n2. Aggregated Risk by Underlying:")
        risk_table = self.container.to_summary_table()
        if risk_table:
            print(tabulate(risk_table, headers='keys', tablefmt='psql', floatfmt='.2f'))
        else:
            print("   No risk factors found")
        
        # Step 3: Portfolio totals
        print("\n3. Portfolio Totals:")
        totals = self.container.get_portfolio_totals()
        print(f"   Total Delta: {totals['delta']:.2f}")
        print(f"   Total Gamma: {totals['gamma']:.4f}")
        print(f"   Total Theta: ${totals['theta']:.2f}/day")
        print(f"   Total Vega:  {totals['vega']:.2f}")
        print(f"   Total Rho:   {totals['rho']:.2f}")
        
        # Step 4: Identify factors needing hedges
        print("\n4. Risk Factors Needing Hedges:")
        needs_hedge = self.container.get_factors_needing_hedge(
            delta_threshold=Decimal('50'),
            gamma_threshold=Decimal('5'),
            vega_threshold=Decimal('200'),
        )
        
        if needs_hedge:
            for agg in needs_hedge:
                print(f"   ⚠️  {agg.risk_factor.underlying}: Δ={agg.total_delta:.0f}")
        else:
            print("   ✓ All factors within thresholds")
        
        # Step 5: Calculate hedge recommendations
        if needs_hedge and market_data:
            print("\n5. Hedge Recommendations:")
            recommendations = self.hedge_calculator.calculate_all_hedges(
                self.container, market_data
            )
            
            for reco in recommendations:
                rec = reco.recommended
                if rec:
                    print(f"   {reco.greek_type.upper()} for {reco.risk_factor.underlying}:")
                    print(f"     Current: {reco.exposure:.2f} → Target: {reco.target:.2f}")
                    print(f"     Hedge: {rec.instrument} @ {rec.position:.2f}")
        
        # Store in context for next steps
        context['risk_factor_container'] = self.container
        context['hedge_recommendations'] = needs_hedge
        
        print(f"\n✓ {self.name} complete")
        return True
    
    def get_container(self) -> Optional[RiskFactorContainer]:
        """Get the container for external use"""
        return self.container


def run_risk_factor_step(positions: List, market_data: Dict[str, Decimal] = None) -> RiskFactorContainer:
    """
    Standalone function to run risk factor aggregation.
    
    Usage in harness:
        from harness.steps.step05_risk_factors import run_risk_factor_step
        container = run_risk_factor_step(positions, market_data)
    """
    step = RiskFactorAggregationStep()
    context = {
        'positions': positions,
        'market_data': market_data or {},
    }
    step.run(context)
    return step.get_container()


# For direct testing
if __name__ == "__main__":
    print("Run via harness: python -m harness.runner")
