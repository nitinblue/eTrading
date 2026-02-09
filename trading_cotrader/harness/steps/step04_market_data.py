"""
Step 4: Market Data Container
=============================

Build the market data container from positions.
Shows instruments and risk factors.
"""

from collections import Counter
from datetime import date
from trading_cotrader.harness.base import (
    TestStep, StepResult, rich_table, format_currency, format_greek,
    format_quantity
)


class MarketDataContainerStep(TestStep):
    """Build and display the market data container."""
    
    name = "Step 4: Market Data Container"
    description = "Build instrument registry and market data container from positions"
    
    def execute(self) -> StepResult:
        tables = []
        messages = []
        
        from services.market_data import (
            MarketDataService, InstrumentRegistry
        )
        
        # Get positions from context - could be raw dicts OR domain objects
        positions = self.context.get('broker_positions', [])
        
        # Check if we have domain Position objects instead of dicts
        if positions and hasattr(positions[0], 'symbol'):
            # Convert Position domain objects to the dict format expected by MarketDataService
            positions = self._convert_domain_positions_to_dicts(positions)
            messages.append(f"Converted {len(positions)} domain positions to dicts")
        
        if not positions:
            positions = self._get_mock_positions()
            messages.append("Using mock positions")
        
        # Build the container
        registry = InstrumentRegistry()
        service = MarketDataService(registry)
        
        new_count = service.sync_from_positions(positions)
        container = service.get_container()
        
        # Store in context
        self.context['instrument_registry'] = registry
        self.context['market_data_service'] = service
        self.context['market_data_container'] = container
        
        messages.append(f"Registered {new_count} instruments")
        
        # Summary table
        type_counts = Counter(inst.asset_type.value for inst in container.instruments)
        summary_data = [
            ["Total Instruments", len(container.instruments), ""],
            ["DXLink Symbols", len(container.dxlink_symbols), "For streamer"],
            ["Unique Underlyings", len(container.get_underlyings()), 
             ", ".join(container.get_underlyings()[:5])],
        ]
        
        for asset_type, count in sorted(type_counts.items()):
            summary_data.append([f"  {asset_type}", count, ""])
        
        tables.append(rich_table(
            summary_data,
            headers=["Metric", "Count", "Details"],
            title="📦 Market Data Container Summary"
        ))
        
        # Instruments table
        inst_data = []
        for inst in sorted(container.instruments, 
                          key=lambda x: (x.ticker, str(x.expiry or ''), float(x.strike or 0))):
            
            # Risk factors
            rf_types = [rf.factor_type.value for rf in inst.risk_factors]
            
            # DTE
            dte = "-"
            if inst.expiry:
                dte = (inst.expiry - date.today()).days
                if dte < 0:
                    dte = f"{dte} ⚠"
            
            inst_data.append([
                inst.ticker,
                inst.asset_type.value[:8],
                inst.option_type.value[0] if inst.option_type else "-",
                f"{float(inst.strike):.0f}" if inst.strike else "-",
                dte,
                inst.multiplier,
                ", ".join(rf_types),
                format_currency(inst.current_price) if inst.current_price else "-",
            ])
        
        tables.append(rich_table(
            inst_data,
            headers=["Ticker", "Type", "P/C", "Strike", "DTE", "Mult", 
                    "Risk Factors", "Price"],
            title="🎯 Registered Instruments"
        ))
        
        # DXLink symbols table (what to subscribe to)
        symbols_data = []
        for sym in sorted(container.dxlink_symbols)[:15]:
            # Determine type from symbol format
            sym_type = "Option" if len(sym) > 10 else "Equity"
            symbols_data.append([sym, sym_type])
        
        if len(container.dxlink_symbols) > 15:
            symbols_data.append(["...", f"+{len(container.dxlink_symbols) - 15} more"])
        
        tables.append(rich_table(
            symbols_data,
            headers=["Symbol", "Type"],
            title="📡 DXLink Symbols (for DXLinkStreamer)"
        ))
        
        # Underlying breakdown
        underlying_data = []
        for underlying in sorted(container.get_underlyings()):
            insts = [i for i in container.instruments 
                    if (i.underlying_symbol or i.ticker) == underlying]
            options = [i for i in insts if i.is_option()]
            stocks = [i for i in insts if not i.is_option()]
            
            underlying_data.append([
                underlying,
                len(stocks),
                len(options),
                len(insts),
            ])
        
        tables.append(rich_table(
            underlying_data,
            headers=["Underlying", "Stock", "Options", "Total"],
            title="📈 Instruments by Underlying"
        ))
        
        return self._success_result(tables=tables, messages=messages)
    
    def _get_mock_positions(self) -> list:
        """Mock positions for testing."""
        return [
            {"symbol": "MSFT", "instrument_type": "EQUITY", "quantity": 100},
            {"symbol": "MSFT  260331P00400000", "instrument_type": "EQUITY_OPTION",
             "underlying_symbol": "MSFT", "strike_price": "400.00",
             "expiration_date": "2026-03-31", "option_type": "PUT", 
             "multiplier": 100, "quantity": -2},
            {"symbol": "SPY   260331C00600000", "instrument_type": "EQUITY_OPTION",
             "underlying_symbol": "SPY", "strike_price": "600.00",
             "expiration_date": "2026-03-31", "option_type": "CALL",
             "multiplier": 100, "quantity": 5},
        ]
    
    def _convert_domain_positions_to_dicts(self, positions) -> list:
        """Convert Position domain objects to dict format for MarketDataService."""
        result = []
        for p in positions:
            try:
                symbol = p.symbol
                
                # Determine instrument type
                if symbol.asset_type.value == "OPTION":
                    inst_type = "EQUITY_OPTION"
                elif symbol.asset_type.value == "FUTURE":
                    inst_type = "FUTURE"
                elif symbol.asset_type.value == "FUTURE_OPTION":
                    inst_type = "FUTURE_OPTION"
                else:
                    inst_type = "EQUITY"
                
                pos_dict = {
                    "symbol": symbol.ticker if inst_type == "EQUITY" else str(symbol),
                    "instrument_type": inst_type,
                    "quantity": p.quantity,
                    "underlying_symbol": symbol.ticker,
                }
                
                # Add option-specific fields
                if symbol.asset_type.value == "OPTION":
                    pos_dict["strike_price"] = str(symbol.strike) if symbol.strike else None
                    pos_dict["expiration_date"] = symbol.expiration.isoformat() if symbol.expiration else None
                    pos_dict["option_type"] = symbol.option_type.value if symbol.option_type else None
                    pos_dict["multiplier"] = 100
                
                result.append(pos_dict)
            except Exception as e:
                # Skip positions that can't be converted
                continue
        
        return result
