"""
Research Container — Unified per-symbol research data store.

Superset of MarketDataContainer. Aggregates:
- Technical indicators (from market_regime library)
- HMM regime detection (R1-R4)
- Fundamentals summary
- Macro context (global, shared across all symbols)
- Screening results (triggered templates)

Owned by the Quant/Research agent. Populated on-demand via API
or by the agent during workflow cycles.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ResearchEntry:
    """Comprehensive research data for a single symbol."""
    symbol: str = ""
    name: str = ""
    asset_class: str = ""
    timestamp: Optional[datetime] = None

    # --- Price & Technicals ---
    current_price: Optional[float] = None
    atr: Optional[float] = None
    atr_pct: Optional[float] = None
    vwma_20: Optional[float] = None

    # RSI
    rsi_14: Optional[float] = None
    rsi_overbought: bool = False
    rsi_oversold: bool = False

    # Moving Averages
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_9: Optional[float] = None
    ema_21: Optional[float] = None
    price_vs_sma_20_pct: Optional[float] = None
    price_vs_sma_50_pct: Optional[float] = None
    price_vs_sma_200_pct: Optional[float] = None

    # Bollinger
    bollinger_upper: Optional[float] = None
    bollinger_lower: Optional[float] = None
    bollinger_pct_b: Optional[float] = None
    bollinger_bandwidth: Optional[float] = None

    # MACD
    macd_histogram: Optional[float] = None
    macd_bullish_cross: bool = False
    macd_bearish_cross: bool = False

    # Stochastic
    stochastic_k: Optional[float] = None
    stochastic_d: Optional[float] = None
    stochastic_overbought: bool = False
    stochastic_oversold: bool = False

    # Support / Resistance
    support: Optional[float] = None
    resistance: Optional[float] = None
    price_vs_support_pct: Optional[float] = None
    price_vs_resistance_pct: Optional[float] = None

    # Signals (list of dicts: name, direction, strength, description)
    signals: List[Dict[str, str]] = field(default_factory=list)

    # --- HMM Regime ---
    hmm_regime_id: Optional[int] = None       # 1-4
    hmm_regime_label: Optional[str] = None     # R1_LOW_VOL_MR etc.
    hmm_confidence: Optional[float] = None
    hmm_trend_direction: Optional[str] = None  # bullish/bearish/neutral
    hmm_strategy_comment: Optional[str] = None

    # --- Fundamentals Summary ---
    long_name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[float] = None
    beta: Optional[float] = None
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    peg_ratio: Optional[float] = None
    earnings_growth: Optional[float] = None
    revenue_growth: Optional[float] = None
    dividend_yield: Optional[float] = None
    profit_margins: Optional[float] = None
    pct_from_52w_high: Optional[float] = None
    pct_from_52w_low: Optional[float] = None
    next_earnings_date: Optional[str] = None
    days_to_earnings: Optional[int] = None

    # --- Phase (Wyckoff) ---
    phase_name: Optional[str] = None           # accumulation/markup/distribution/markdown
    phase_confidence: Optional[float] = None
    phase_description: Optional[str] = None
    phase_higher_highs: bool = False
    phase_higher_lows: bool = False
    phase_lower_highs: bool = False
    phase_lower_lows: bool = False
    phase_range_compression: Optional[float] = None
    phase_volume_trend: Optional[str] = None
    phase_price_vs_sma_50_pct: Optional[float] = None

    # --- VCP (Volatility Contraction Pattern) ---
    vcp_stage: Optional[str] = None            # none/forming/maturing/ready/breakout
    vcp_score: Optional[float] = None
    vcp_contraction_count: Optional[int] = None
    vcp_current_range_pct: Optional[float] = None
    vcp_range_compression: Optional[float] = None
    vcp_volume_trend: Optional[str] = None
    vcp_pivot_price: Optional[float] = None
    vcp_pivot_distance_pct: Optional[float] = None
    vcp_days_in_base: Optional[int] = None
    vcp_above_sma_50: bool = False
    vcp_above_sma_200: bool = False
    vcp_description: Optional[str] = None

    # --- Screening ---
    triggered_templates: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Flat dict for API/AG Grid serialization."""
        return {
            'symbol': self.symbol,
            'name': self.name,
            'asset_class': self.asset_class,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            # Price & Technicals
            'current_price': self.current_price,
            'atr': self.atr,
            'atr_pct': self.atr_pct,
            'rsi_14': self.rsi_14,
            'rsi_overbought': self.rsi_overbought,
            'rsi_oversold': self.rsi_oversold,
            # MAs
            'sma_20': self.sma_20,
            'sma_50': self.sma_50,
            'sma_200': self.sma_200,
            'ema_9': self.ema_9,
            'ema_21': self.ema_21,
            'price_vs_sma_20_pct': self.price_vs_sma_20_pct,
            'price_vs_sma_50_pct': self.price_vs_sma_50_pct,
            'price_vs_sma_200_pct': self.price_vs_sma_200_pct,
            # Bollinger
            'bollinger_upper': self.bollinger_upper,
            'bollinger_lower': self.bollinger_lower,
            'bollinger_pct_b': self.bollinger_pct_b,
            'bollinger_bandwidth': self.bollinger_bandwidth,
            # MACD
            'macd_histogram': self.macd_histogram,
            'macd_bullish_cross': self.macd_bullish_cross,
            'macd_bearish_cross': self.macd_bearish_cross,
            # Stochastic
            'stochastic_k': self.stochastic_k,
            'stochastic_d': self.stochastic_d,
            'stochastic_overbought': self.stochastic_overbought,
            'stochastic_oversold': self.stochastic_oversold,
            # Support/Resistance
            'support': self.support,
            'resistance': self.resistance,
            'price_vs_support_pct': self.price_vs_support_pct,
            'price_vs_resistance_pct': self.price_vs_resistance_pct,
            # Signals
            'signals': self.signals,
            # Regime
            'hmm_regime_id': self.hmm_regime_id,
            'hmm_regime_label': self.hmm_regime_label,
            'hmm_confidence': self.hmm_confidence,
            'hmm_trend_direction': self.hmm_trend_direction,
            'hmm_strategy_comment': self.hmm_strategy_comment,
            # Fundamentals
            'long_name': self.long_name,
            'sector': self.sector,
            'industry': self.industry,
            'market_cap': self.market_cap,
            'beta': self.beta,
            'pe_ratio': self.pe_ratio,
            'forward_pe': self.forward_pe,
            'peg_ratio': self.peg_ratio,
            'earnings_growth': self.earnings_growth,
            'revenue_growth': self.revenue_growth,
            'dividend_yield': self.dividend_yield,
            'profit_margins': self.profit_margins,
            'pct_from_52w_high': self.pct_from_52w_high,
            'pct_from_52w_low': self.pct_from_52w_low,
            'next_earnings_date': self.next_earnings_date,
            'days_to_earnings': self.days_to_earnings,
            # Phase
            'phase_name': self.phase_name,
            'phase_confidence': self.phase_confidence,
            'phase_description': self.phase_description,
            'phase_higher_highs': self.phase_higher_highs,
            'phase_higher_lows': self.phase_higher_lows,
            'phase_lower_highs': self.phase_lower_highs,
            'phase_lower_lows': self.phase_lower_lows,
            'phase_range_compression': self.phase_range_compression,
            'phase_volume_trend': self.phase_volume_trend,
            'phase_price_vs_sma_50_pct': self.phase_price_vs_sma_50_pct,
            # VCP
            'vcp_stage': self.vcp_stage,
            'vcp_score': self.vcp_score,
            'vcp_contraction_count': self.vcp_contraction_count,
            'vcp_current_range_pct': self.vcp_current_range_pct,
            'vcp_range_compression': self.vcp_range_compression,
            'vcp_volume_trend': self.vcp_volume_trend,
            'vcp_pivot_price': self.vcp_pivot_price,
            'vcp_pivot_distance_pct': self.vcp_pivot_distance_pct,
            'vcp_days_in_base': self.vcp_days_in_base,
            'vcp_above_sma_50': self.vcp_above_sma_50,
            'vcp_above_sma_200': self.vcp_above_sma_200,
            'vcp_description': self.vcp_description,
            # Screening
            'triggered_templates': self.triggered_templates,
        }


@dataclass
class MacroContext:
    """Global macro context (shared, not per-symbol)."""
    timestamp: Optional[datetime] = None
    next_event_name: Optional[str] = None
    next_event_date: Optional[str] = None
    next_event_impact: Optional[str] = None
    next_event_options_impact: Optional[str] = None
    days_to_next_event: Optional[int] = None
    next_fomc_date: Optional[str] = None
    days_to_fomc: Optional[int] = None
    events_7d: List[Dict[str, Any]] = field(default_factory=list)
    events_30d: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'next_event_name': self.next_event_name,
            'next_event_date': self.next_event_date,
            'next_event_impact': self.next_event_impact,
            'next_event_options_impact': self.next_event_options_impact,
            'days_to_next_event': self.days_to_next_event,
            'next_fomc_date': self.next_fomc_date,
            'days_to_fomc': self.days_to_fomc,
            'events_7d': self.events_7d,
            'events_30d': self.events_30d,
        }


class ResearchContainer:
    """
    Unified per-symbol research data store.

    Replaces MarketDataContainer as a superset. Aggregates technicals,
    HMM regime, fundamentals, macro context, and screening results.

    Cross-portfolio: research data is the same regardless of portfolio.
    One instance in ContainerManager.
    """

    def __init__(self):
        self._data: Dict[str, ResearchEntry] = {}
        self._macro: MacroContext = MacroContext()
        self._watchlist_config: List[Dict[str, str]] = []
        self._loaded_from_db: bool = False

    # -----------------------------------------------------------------
    # Watchlist config (owned by this container)
    # -----------------------------------------------------------------

    def load_watchlist_config(self, items: List[Dict[str, str]]) -> None:
        """Store watchlist config items (ticker, name, asset_class)."""
        self._watchlist_config = items
        for item in items:
            symbol = item['ticker']
            if symbol not in self._data:
                self._data[symbol] = ResearchEntry(
                    symbol=symbol,
                    name=item.get('name', ''),
                    asset_class=item.get('asset_class', ''),
                )
            else:
                self._data[symbol].name = item.get('name', '')
                self._data[symbol].asset_class = item.get('asset_class', '')

    @property
    def watchlist_config(self) -> List[Dict[str, str]]:
        return self._watchlist_config

    # -----------------------------------------------------------------
    # Technicals update (from market_regime TechnicalSnapshot)
    # -----------------------------------------------------------------

    def update_technicals(self, symbol: str, tech: dict) -> None:
        """
        Update from market_regime TechnicalSnapshot (already model_dump'd to dict).
        """
        entry = self._get_or_create(symbol)

        entry.current_price = tech.get('current_price')
        entry.atr = tech.get('atr')
        entry.atr_pct = tech.get('atr_pct')
        entry.vwma_20 = tech.get('vwma_20')

        # RSI
        rsi = tech.get('rsi', {})
        entry.rsi_14 = rsi.get('value')
        entry.rsi_overbought = rsi.get('is_overbought', False)
        entry.rsi_oversold = rsi.get('is_oversold', False)

        # MAs
        ma = tech.get('moving_averages', {})
        entry.sma_20 = ma.get('sma_20')
        entry.sma_50 = ma.get('sma_50')
        entry.sma_200 = ma.get('sma_200')
        entry.ema_9 = ma.get('ema_9')
        entry.ema_21 = ma.get('ema_21')
        entry.price_vs_sma_20_pct = ma.get('price_vs_sma_20_pct')
        entry.price_vs_sma_50_pct = ma.get('price_vs_sma_50_pct')
        entry.price_vs_sma_200_pct = ma.get('price_vs_sma_200_pct')

        # Bollinger
        bb = tech.get('bollinger', {})
        entry.bollinger_upper = bb.get('upper')
        entry.bollinger_lower = bb.get('lower')
        entry.bollinger_pct_b = bb.get('percent_b')
        entry.bollinger_bandwidth = bb.get('bandwidth')

        # MACD
        macd = tech.get('macd', {})
        entry.macd_histogram = macd.get('histogram')
        entry.macd_bullish_cross = macd.get('is_bullish_crossover', False)
        entry.macd_bearish_cross = macd.get('is_bearish_crossover', False)

        # Stochastic
        stoch = tech.get('stochastic', {})
        entry.stochastic_k = stoch.get('k')
        entry.stochastic_d = stoch.get('d')
        entry.stochastic_overbought = stoch.get('is_overbought', False)
        entry.stochastic_oversold = stoch.get('is_oversold', False)

        # Support/Resistance
        sr = tech.get('support_resistance', {})
        entry.support = sr.get('support')
        entry.resistance = sr.get('resistance')
        entry.price_vs_support_pct = sr.get('price_vs_support_pct')
        entry.price_vs_resistance_pct = sr.get('price_vs_resistance_pct')

        # Phase (Wyckoff)
        phase = tech.get('phase')
        if phase and isinstance(phase, dict):
            entry.phase_name = phase.get('phase')
            entry.phase_confidence = phase.get('confidence')
            entry.phase_description = phase.get('description')
            entry.phase_higher_highs = phase.get('higher_highs', False)
            entry.phase_higher_lows = phase.get('higher_lows', False)
            entry.phase_lower_highs = phase.get('lower_highs', False)
            entry.phase_lower_lows = phase.get('lower_lows', False)
            entry.phase_range_compression = phase.get('range_compression')
            entry.phase_volume_trend = phase.get('volume_trend')
            entry.phase_price_vs_sma_50_pct = phase.get('price_vs_sma_50_pct')

        # VCP (Volatility Contraction Pattern)
        vcp = tech.get('vcp')
        if vcp and isinstance(vcp, dict):
            entry.vcp_stage = vcp.get('stage')
            entry.vcp_score = vcp.get('score')
            entry.vcp_contraction_count = vcp.get('contraction_count')
            entry.vcp_current_range_pct = vcp.get('current_range_pct')
            entry.vcp_range_compression = vcp.get('range_compression')
            entry.vcp_volume_trend = vcp.get('volume_trend')
            entry.vcp_pivot_price = vcp.get('pivot_price')
            entry.vcp_pivot_distance_pct = vcp.get('pivot_distance_pct')
            entry.vcp_days_in_base = vcp.get('days_in_base')
            entry.vcp_above_sma_50 = vcp.get('above_sma_50', False)
            entry.vcp_above_sma_200 = vcp.get('above_sma_200', False)
            entry.vcp_description = vcp.get('description')

        # Signals
        entry.signals = tech.get('signals', [])

        entry.timestamp = datetime.utcnow()

    # -----------------------------------------------------------------
    # Regime update (from market_regime detect)
    # -----------------------------------------------------------------

    def update_regime(self, symbol: str, regime_data: dict) -> None:
        """
        Update HMM regime fields from detect() result dict.

        Expected keys: regime, regime_name, confidence, trend_direction
        """
        entry = self._get_or_create(symbol)
        entry.hmm_regime_id = regime_data.get('regime')
        entry.hmm_regime_label = regime_data.get('regime_name')
        entry.hmm_confidence = regime_data.get('confidence')
        entry.hmm_trend_direction = regime_data.get('trend_direction')
        entry.hmm_strategy_comment = regime_data.get('strategy_comment')
        entry.timestamp = datetime.utcnow()

    # -----------------------------------------------------------------
    # Fundamentals update (from market_regime fetch_fundamentals)
    # -----------------------------------------------------------------

    def update_fundamentals(self, symbol: str, fund: dict) -> None:
        """
        Update fundamentals summary from fetch_fundamentals() model_dump'd dict.
        """
        entry = self._get_or_create(symbol)

        biz = fund.get('business', {})
        entry.long_name = biz.get('long_name')
        entry.sector = biz.get('sector')
        entry.industry = biz.get('industry')
        entry.beta = biz.get('beta')

        val = fund.get('valuation', {})
        entry.pe_ratio = val.get('trailing_pe')
        entry.forward_pe = val.get('forward_pe')
        entry.peg_ratio = val.get('peg_ratio')

        earn = fund.get('earnings', {})
        entry.earnings_growth = earn.get('earnings_growth')

        rev = fund.get('revenue', {})
        entry.market_cap = rev.get('market_cap')
        entry.revenue_growth = rev.get('revenue_growth')

        marg = fund.get('margins', {})
        entry.profit_margins = marg.get('profit_margins')

        div = fund.get('dividends', {})
        entry.dividend_yield = div.get('dividend_yield')

        w52 = fund.get('fifty_two_week', {})
        entry.pct_from_52w_high = w52.get('pct_from_high')
        entry.pct_from_52w_low = w52.get('pct_from_low')

        events = fund.get('upcoming_events', {})
        entry.next_earnings_date = events.get('next_earnings_date')
        entry.days_to_earnings = events.get('days_to_earnings')

        # Name from fundamentals if not already set by watchlist
        if not entry.name and entry.long_name:
            entry.name = entry.long_name

        entry.timestamp = datetime.utcnow()

    # -----------------------------------------------------------------
    # Macro context update
    # -----------------------------------------------------------------

    def update_macro(self, macro_data: dict) -> None:
        """
        Update global macro context from get_macro_calendar() model_dump'd dict.
        """
        self._macro.timestamp = datetime.utcnow()

        nxt = macro_data.get('next_event')
        if nxt:
            self._macro.next_event_name = nxt.get('name')
            self._macro.next_event_date = nxt.get('date')
            self._macro.next_event_impact = nxt.get('impact')
            self._macro.next_event_options_impact = nxt.get('options_impact')

        self._macro.days_to_next_event = macro_data.get('days_to_next')

        fomc = macro_data.get('next_fomc')
        if fomc:
            self._macro.next_fomc_date = fomc.get('date')
        self._macro.days_to_fomc = macro_data.get('days_to_next_fomc')

        self._macro.events_7d = macro_data.get('events_next_7_days', [])
        self._macro.events_30d = macro_data.get('events_next_30_days', [])

    # -----------------------------------------------------------------
    # Screening update
    # -----------------------------------------------------------------

    def set_triggered_templates(self, symbol: str, templates: List[str]) -> None:
        """Set which research templates triggered for a symbol."""
        entry = self._get_or_create(symbol)
        entry.triggered_templates = templates

    # -----------------------------------------------------------------
    # Accessors
    # -----------------------------------------------------------------

    def get(self, symbol: str) -> Optional[ResearchEntry]:
        """Get entry for a symbol."""
        return self._data.get(symbol.upper() if symbol == symbol.upper() else symbol)

    def get_all(self) -> Dict[str, ResearchEntry]:
        """Get all entries."""
        return dict(self._data)

    def get_macro(self) -> MacroContext:
        """Get global macro context."""
        return self._macro

    def to_grid_rows(self) -> List[Dict[str, Any]]:
        """Serialize all entries for AG Grid."""
        return [entry.to_dict() for entry in self._data.values()]

    @property
    def symbols(self) -> List[str]:
        """All tracked symbols."""
        return list(self._data.keys())

    @property
    def count(self) -> int:
        return len(self._data)

    @property
    def is_stale(self) -> bool:
        """True if no entry has been updated in last 5 minutes."""
        if not self._data:
            return True
        now = datetime.utcnow()
        for entry in self._data.values():
            if entry.timestamp and (now - entry.timestamp).total_seconds() < 300:
                return False
        return True

    # -----------------------------------------------------------------
    # Backward compat: MarketDataContainer interface
    # -----------------------------------------------------------------

    def update_from_snapshot(self, snap) -> Dict[str, Any]:
        """
        Backward compat: update from TechnicalSnapshot object
        (same interface as MarketDataContainer).
        """
        symbol = snap.symbol
        entry = self._get_or_create(symbol)

        # Map the old MarketDataContainer fields
        field_map = {
            'current_price': 'current_price',
            'rsi_14': 'rsi_14',
            'atr_14': 'atr',
            'atr_percent': 'atr_pct',
            'iv_rank': None,  # not in ResearchEntry (comes from broker)
            'ema_20': 'sma_20',
            'ema_50': 'sma_50',
            'sma_200': 'sma_200',
            'bollinger_upper': 'bollinger_upper',
            'bollinger_lower': 'bollinger_lower',
            'bollinger_width': 'bollinger_bandwidth',
        }

        changes: Dict[str, Any] = {}
        for snap_field, entry_field in field_map.items():
            if entry_field is None:
                continue
            new_val = getattr(snap, snap_field, None)
            if new_val is not None:
                old_val = getattr(entry, entry_field, None)
                if new_val != old_val:
                    changes[entry_field] = {'old': old_val, 'new': new_val}
                    setattr(entry, entry_field, new_val if not hasattr(new_val, '__float__') else float(new_val))

        entry.timestamp = datetime.utcnow()
        return changes

    # -----------------------------------------------------------------
    # DB persistence (load / save)
    # -----------------------------------------------------------------

    def load_from_db(self, session) -> int:
        """
        Load latest research snapshots from DB into in-memory container.

        Returns count of entries loaded.
        """
        from trading_cotrader.repositories.research_snapshot import ResearchSnapshotRepository

        repo = ResearchSnapshotRepository(session)

        # Load research entries
        snapshots = repo.load_latest_research()
        count = 0

        # Fields that map 1:1 from ORM to ResearchEntry (float-convertible Numerics)
        _FLOAT_FIELDS = [
            'current_price', 'atr', 'atr_pct', 'vwma_20',
            'rsi_14', 'sma_20', 'sma_50', 'sma_200', 'ema_9', 'ema_21',
            'price_vs_sma_20_pct', 'price_vs_sma_50_pct', 'price_vs_sma_200_pct',
            'bollinger_upper', 'bollinger_lower', 'bollinger_pct_b', 'bollinger_bandwidth',
            'macd_histogram', 'stochastic_k', 'stochastic_d',
            'support', 'resistance', 'price_vs_support_pct', 'price_vs_resistance_pct',
            'hmm_confidence', 'market_cap', 'beta', 'pe_ratio', 'forward_pe',
            'peg_ratio', 'earnings_growth', 'revenue_growth', 'dividend_yield',
            'profit_margins', 'pct_from_52w_high', 'pct_from_52w_low',
            'phase_confidence', 'phase_range_compression', 'phase_price_vs_sma_50_pct',
            'vcp_score', 'vcp_current_range_pct', 'vcp_range_compression',
            'vcp_pivot_price', 'vcp_pivot_distance_pct',
        ]
        _BOOL_FIELDS = [
            'rsi_overbought', 'rsi_oversold',
            'macd_bullish_cross', 'macd_bearish_cross',
            'stochastic_overbought', 'stochastic_oversold',
            'phase_higher_highs', 'phase_higher_lows',
            'phase_lower_highs', 'phase_lower_lows',
            'vcp_above_sma_50', 'vcp_above_sma_200',
        ]
        _STR_FIELDS = [
            'name', 'asset_class', 'hmm_regime_label', 'hmm_trend_direction',
            'hmm_strategy_comment', 'long_name', 'sector', 'industry',
            'next_earnings_date',
            'phase_name', 'phase_description', 'phase_volume_trend',
            'vcp_stage', 'vcp_volume_trend', 'vcp_description',
        ]
        _INT_FIELDS = ['hmm_regime_id', 'days_to_earnings',
                        'vcp_contraction_count', 'vcp_days_in_base']

        for snap_orm in snapshots:
            symbol = snap_orm.symbol
            entry = self._get_or_create(symbol)

            # Float fields — Numeric → float
            for f in _FLOAT_FIELDS:
                val = getattr(snap_orm, f, None)
                setattr(entry, f, float(val) if val is not None else None)

            # Bool fields
            for f in _BOOL_FIELDS:
                setattr(entry, f, bool(getattr(snap_orm, f, False)))

            # String fields
            for f in _STR_FIELDS:
                setattr(entry, f, getattr(snap_orm, f, None))

            # Int fields
            for f in _INT_FIELDS:
                val = getattr(snap_orm, f, None)
                setattr(entry, f, int(val) if val is not None else None)

            # JSON fields
            entry.signals = getattr(snap_orm, 'signals', None) or []
            entry.triggered_templates = getattr(snap_orm, 'triggered_templates', None) or []

            # Timestamp from ORM updated_at
            entry.timestamp = snap_orm.updated_at or snap_orm.created_at
            count += 1

        # Load macro
        macro_orm = repo.load_latest_macro()
        if macro_orm:
            self._macro.next_event_name = macro_orm.next_event_name
            self._macro.next_event_date = macro_orm.next_event_date
            self._macro.next_event_impact = macro_orm.next_event_impact
            self._macro.next_event_options_impact = macro_orm.next_event_options_impact
            self._macro.days_to_next_event = macro_orm.days_to_next_event
            self._macro.next_fomc_date = macro_orm.next_fomc_date
            self._macro.days_to_fomc = macro_orm.days_to_fomc
            self._macro.events_7d = macro_orm.events_7d or []
            self._macro.events_30d = macro_orm.events_30d or []
            self._macro.timestamp = macro_orm.updated_at or macro_orm.created_at

        if count > 0:
            self._loaded_from_db = True
            logger.info(f"ResearchContainer loaded {count} entries from DB (macro={'yes' if macro_orm else 'no'})")

        return count

    def save_to_db(self, session) -> int:
        """
        Persist current container state to DB.

        Only saves entries that have been populated (timestamp is not None).
        Returns count saved.
        """
        from trading_cotrader.repositories.research_snapshot import ResearchSnapshotRepository

        repo = ResearchSnapshotRepository(session)
        today = date.today()
        count = 0

        for symbol, entry in self._data.items():
            if entry.timestamp is None:
                continue  # Not populated yet

            data = {
                'name': entry.name,
                'asset_class': entry.asset_class,
                'current_price': entry.current_price,
                'atr': entry.atr,
                'atr_pct': entry.atr_pct,
                'vwma_20': entry.vwma_20,
                'rsi_14': entry.rsi_14,
                'rsi_overbought': entry.rsi_overbought,
                'rsi_oversold': entry.rsi_oversold,
                'sma_20': entry.sma_20,
                'sma_50': entry.sma_50,
                'sma_200': entry.sma_200,
                'ema_9': entry.ema_9,
                'ema_21': entry.ema_21,
                'price_vs_sma_20_pct': entry.price_vs_sma_20_pct,
                'price_vs_sma_50_pct': entry.price_vs_sma_50_pct,
                'price_vs_sma_200_pct': entry.price_vs_sma_200_pct,
                'bollinger_upper': entry.bollinger_upper,
                'bollinger_lower': entry.bollinger_lower,
                'bollinger_pct_b': entry.bollinger_pct_b,
                'bollinger_bandwidth': entry.bollinger_bandwidth,
                'macd_histogram': entry.macd_histogram,
                'macd_bullish_cross': entry.macd_bullish_cross,
                'macd_bearish_cross': entry.macd_bearish_cross,
                'stochastic_k': entry.stochastic_k,
                'stochastic_d': entry.stochastic_d,
                'stochastic_overbought': entry.stochastic_overbought,
                'stochastic_oversold': entry.stochastic_oversold,
                'support': entry.support,
                'resistance': entry.resistance,
                'price_vs_support_pct': entry.price_vs_support_pct,
                'price_vs_resistance_pct': entry.price_vs_resistance_pct,
                'signals': entry.signals,
                'hmm_regime_id': entry.hmm_regime_id,
                'hmm_regime_label': entry.hmm_regime_label,
                'hmm_confidence': entry.hmm_confidence,
                'hmm_trend_direction': entry.hmm_trend_direction,
                'hmm_strategy_comment': entry.hmm_strategy_comment,
                'long_name': entry.long_name,
                'sector': entry.sector,
                'industry': entry.industry,
                'market_cap': entry.market_cap,
                'beta': entry.beta,
                'pe_ratio': entry.pe_ratio,
                'forward_pe': entry.forward_pe,
                'peg_ratio': entry.peg_ratio,
                'earnings_growth': entry.earnings_growth,
                'revenue_growth': entry.revenue_growth,
                'dividend_yield': entry.dividend_yield,
                'profit_margins': entry.profit_margins,
                'pct_from_52w_high': entry.pct_from_52w_high,
                'pct_from_52w_low': entry.pct_from_52w_low,
                'next_earnings_date': entry.next_earnings_date,
                'days_to_earnings': entry.days_to_earnings,
                # Phase
                'phase_name': entry.phase_name,
                'phase_confidence': entry.phase_confidence,
                'phase_description': entry.phase_description,
                'phase_higher_highs': entry.phase_higher_highs,
                'phase_higher_lows': entry.phase_higher_lows,
                'phase_lower_highs': entry.phase_lower_highs,
                'phase_lower_lows': entry.phase_lower_lows,
                'phase_range_compression': entry.phase_range_compression,
                'phase_volume_trend': entry.phase_volume_trend,
                'phase_price_vs_sma_50_pct': entry.phase_price_vs_sma_50_pct,
                # VCP
                'vcp_stage': entry.vcp_stage,
                'vcp_score': entry.vcp_score,
                'vcp_contraction_count': entry.vcp_contraction_count,
                'vcp_current_range_pct': entry.vcp_current_range_pct,
                'vcp_range_compression': entry.vcp_range_compression,
                'vcp_volume_trend': entry.vcp_volume_trend,
                'vcp_pivot_price': entry.vcp_pivot_price,
                'vcp_pivot_distance_pct': entry.vcp_pivot_distance_pct,
                'vcp_days_in_base': entry.vcp_days_in_base,
                'vcp_above_sma_50': entry.vcp_above_sma_50,
                'vcp_above_sma_200': entry.vcp_above_sma_200,
                'vcp_description': entry.vcp_description,
                # Screening
                'triggered_templates': entry.triggered_templates,
            }
            try:
                repo.upsert_research(symbol, today, data)
                count += 1
            except Exception as e:
                logger.warning(f"Failed to save research for {symbol}: {e}")

        # Save macro
        if self._macro.timestamp is not None:
            try:
                repo.upsert_macro(today, {
                    'next_event_name': self._macro.next_event_name,
                    'next_event_date': self._macro.next_event_date,
                    'next_event_impact': self._macro.next_event_impact,
                    'next_event_options_impact': self._macro.next_event_options_impact,
                    'days_to_next_event': self._macro.days_to_next_event,
                    'next_fomc_date': self._macro.next_fomc_date,
                    'days_to_fomc': self._macro.days_to_fomc,
                    'events_7d': self._macro.events_7d,
                    'events_30d': self._macro.events_30d,
                })
            except Exception as e:
                logger.warning(f"Failed to save macro snapshot: {e}")

        if count > 0:
            logger.info(f"ResearchContainer saved {count} entries to DB")

        return count

    @property
    def loaded_from_db(self) -> bool:
        """Whether this container was loaded from DB (vs populated live)."""
        return self._loaded_from_db

    # -----------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------

    def _get_or_create(self, symbol: str) -> ResearchEntry:
        if symbol not in self._data:
            self._data[symbol] = ResearchEntry(symbol=symbol)
        return self._data[symbol]
