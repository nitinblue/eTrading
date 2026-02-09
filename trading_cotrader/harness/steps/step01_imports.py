"""
Step 1: Verify Imports
======================

Verifies all required modules can be imported.
"""

from trading_cotrader.harness.base import TestStep, StepResult, rich_table, success, error, warning


class ImportStep(TestStep):
    """Verify all required modules load correctly."""
    
    name = "Step 1: Verify Imports"
    description = "Check that all required modules can be imported"
    
    def execute(self) -> StepResult:
        results = []
        all_passed = True
        
        # Define modules to check with categories
        modules = [
            # Category, Module Path, Required
            ("Core", "services.event_logger.EventLogger", True),
            ("Core", "services.snapshot_service.SnapshotService", True),
            ("Core", "services.portfolio_sync.PortfolioSyncService", True),
            ("Risk", "services.risk_manager.RiskManager", True),
            ("Risk", "services.real_risk_check.RealRiskChecker", False),
            ("Broker", "adapters.tastytrade_adapter.TastytradeAdapter", True),
            ("Data", "repositories.portfolio.PortfolioRepository", True),
            ("Data", "repositories.position.PositionRepository", True),
            ("Data", "repositories.trade.TradeRepository", True),
            ("Data", "repositories.event.EventRepository", True),
            ("Domain", "core.models.domain", True),
            ("Domain", "core.models.events", True),
            ("Market Data", "services.market_data.MarketDataService", True),
            ("Market Data", "services.market_data.InstrumentRegistry", True),
            ("Hedging", "services.hedging.HedgeCalculator", True),
            ("Hedging", "services.hedging.RiskBucket", True),
        ]
        
        for category, module_path, required in modules:
            try:
                # Parse module and class
                parts = module_path.rsplit('.', 1)
                if len(parts) == 2:
                    module_name, class_name = parts
                    module = __import__(module_name, fromlist=[class_name])
                    getattr(module, class_name)
                else:
                    __import__(module_path)
                
                results.append([category, module_path, "✓", "Loaded"])
                
            except ImportError as e:
                status = "✗" if required else "⚠"
                msg = str(e)[:40]
                results.append([category, module_path, status, msg])
                if required:
                    all_passed = False
            except Exception as e:
                results.append([category, module_path, "✗", str(e)[:40]])
                if required:
                    all_passed = False
        
        # Create table
        table = rich_table(
            results,
            headers=["Category", "Module", "Status", "Details"],
            title="📦 Module Import Status"
        )
        
        return StepResult(
            step_name=self.name,
            passed=all_passed,
            duration_ms=0,
            tables=[table],
            messages=[f"Loaded {sum(1 for r in results if r[2] == '✓')}/{len(results)} modules"]
        )
