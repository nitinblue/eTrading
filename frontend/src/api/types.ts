// TypeScript interfaces mirroring backend ORM models

export interface Portfolio {
  id: string
  name: string
  portfolio_type: 'real' | 'paper' | 'what_if' | 'backtest' | 'deprecated'
  broker: string | null
  account_id: string | null
  currency: string

  // Capital
  initial_capital: number
  cash_balance: number
  buying_power: number
  total_equity: number

  // Greeks
  portfolio_delta: number
  portfolio_gamma: number
  portfolio_theta: number
  portfolio_vega: number

  // Risk limits
  max_portfolio_delta: number
  max_portfolio_gamma: number
  min_portfolio_theta: number
  max_portfolio_vega: number
  max_position_size_pct: number
  max_single_trade_risk_pct: number
  max_total_risk_pct: number

  // Risk metrics
  var_1d_95: number
  var_1d_99: number

  // Performance
  total_pnl: number
  daily_pnl: number
  realized_pnl: number
  unrealized_pnl: number

  // Computed
  deployed_pct: number
  open_trade_count: number
}

export interface Leg {
  id: string
  symbol_ticker: string
  asset_type: string
  option_type: string | null
  strike: number | null
  expiration: string | null
  quantity: number
  side: string

  // Prices
  entry_price: number | null
  current_price: number | null
  exit_price: number | null

  // Greeks
  entry_delta: number
  entry_gamma: number
  entry_theta: number
  entry_vega: number
  delta: number
  gamma: number
  theta: number
  vega: number

  // Costs
  fees: number
  commission: number
}

export interface Trade {
  id: string
  portfolio_id: string
  portfolio_name: string
  strategy_type: string | null
  trade_type: string
  trade_status: string
  underlying_symbol: string
  trade_source: string

  // Timestamps
  created_at: string
  opened_at: string | null
  closed_at: string | null

  // Opening state
  entry_price: number | null
  entry_underlying_price: number | null
  entry_iv: number | null
  entry_delta: number
  entry_gamma: number
  entry_theta: number
  entry_vega: number

  // Current state
  current_price: number | null
  current_underlying_price: number | null
  current_iv: number | null
  current_delta: number
  current_gamma: number
  current_theta: number
  current_vega: number

  // P&L
  total_pnl: number
  delta_pnl: number
  gamma_pnl: number
  theta_pnl: number
  vega_pnl: number
  unexplained_pnl: number

  // Risk
  max_risk: number | null
  stop_loss: number | null
  profit_target: number | null

  // Linkage
  rolled_from_id: string | null
  rolled_to_id: string | null
  recommendation_id: string | null

  // DTE (computed by backend)
  dte: number | null

  // State
  is_open: boolean
  notes: string | null
  tags: string[] | null

  // Legs
  legs: Leg[]
}

export interface Recommendation {
  id: string
  recommendation_type: 'entry' | 'exit' | 'roll' | 'adjust'
  source: string
  screener_name: string | null
  underlying: string
  strategy_type: string
  legs: LegSpec[] | null
  confidence: number
  rationale: string | null
  risk_category: string
  suggested_portfolio: string | null
  status: 'pending' | 'accepted' | 'rejected' | 'expired'
  created_at: string
  reviewed_at: string | null

  // Financials (computed)
  max_loss_display: string
  max_profit_display: string
  risk_display: string
  spread_width: number | null
}

export interface LegSpec {
  symbol: string
  option_type: string
  strike: number
  expiration: string
  quantity: number
  side: string
}

export interface WorkflowStatus {
  current_state: string
  previous_state: string | null
  cycle_count: number
  halted: boolean
  halt_reason: string | null
  last_transition_at: string | null
  vix: number | null
  macro_regime: string | null
  trades_today: number
  pending_recommendations: number
}

export interface GreeksUtilization {
  name: string
  delta: number
  gamma: number
  theta: number
  vega: number
  max_delta: number
  max_gamma: number
  min_theta: number
  max_vega: number
  delta_pct: number
  gamma_pct: number
  theta_pct: number
  vega_pct: number
}

export interface CapitalUtilization {
  name: string
  initial_capital: number
  total_equity: number
  cash_balance: number
  deployed_pct: number
  idle_capital: number
  severity: string
  opp_cost_daily?: number
}

export interface RiskSummary {
  var: {
    var_95: number | null
    var_99: number | null
    expected_shortfall_95: number | null
  }
  macro: {
    regime: string | null
    vix: number | null
    confidence: number | null
    rationale: string
  }
  circuit_breakers: Record<string, boolean>
  trading_constraints: {
    trades_today: number
    max_trades_per_day: number
    halted: boolean
    halt_reason: string | null
  }
}

export interface DecisionLogEntry {
  id: string
  recommendation_id: string | null
  decision_type: string
  presented_at: string
  responded_at: string | null
  response: string | null
  rationale: string | null
  time_to_decision_seconds: number | null
}

// ---------------------------------------------------------------------------
// Admin Config Types
// ---------------------------------------------------------------------------

export interface PortfolioConfig {
  display_name: string
  description: string
  broker_firm: string
  account_number: string
  portfolio_type: 'real' | 'what_if'
  currency: string
  initial_capital: number
  target_annual_return_pct: number
  exit_rule_profile: string
  tags: string[]
  allowed_strategies: string[]
  active_strategies: string[]
  risk_limits: PortfolioRiskLimits
  preferred_underlyings: string[]
  mirrors_real?: string
}

export interface PortfolioRiskLimits {
  max_portfolio_delta: number
  max_positions: number
  max_single_position_pct: number
  max_single_trade_risk_pct: number
  max_total_risk_pct: number
  min_cash_reserve_pct: number
  max_concentration_pct?: number
}

export interface VarConfig {
  confidence_level: number
  horizon_days: number
  max_var_percent: number
  warning_threshold: number
}

export interface GreeksLimitsConfig {
  max_portfolio_delta: number
  max_portfolio_gamma: number
  max_portfolio_theta_percent: number
  max_portfolio_vega_percent: number
}

export interface DrawdownConfig {
  max_drawdown_percent: number
  daily_loss_limit_percent: number
}

export interface PortfolioRiskConfig {
  var: VarConfig
  greeks: GreeksLimitsConfig
  drawdown: DrawdownConfig
}

export interface ConcentrationLimit {
  max_percent?: number
  warning_percent?: number
  max_long_percent?: number
}

export interface ConcentrationConfig {
  single_underlying: ConcentrationLimit
  strategy_type: ConcentrationLimit
  direction: ConcentrationLimit
  expiration: ConcentrationLimit
  sector: ConcentrationLimit
}

export interface ExitRuleProfile {
  profit_target_pct: number
  stop_loss_multiplier: number
  roll_dte: number
  close_dte: number
}

export interface LiquidityThreshold {
  min_open_interest: number
  max_bid_ask_spread_pct: number
  min_daily_volume: number
}

export interface LiquidityConfig {
  entry: LiquidityThreshold
  adjustment: LiquidityThreshold
}

export interface MarginConfig {
  min_buying_power_reserve: number
  margin_warning_percent: number
  margin_critical_percent: number
  max_single_trade_margin_percent: number
}

export interface RiskSettingsResponse {
  portfolio_risk: PortfolioRiskConfig
  concentration: ConcentrationConfig
  exit_rule_profiles: Record<string, ExitRuleProfile>
  exit_rules: Record<string, unknown[]>
  liquidity_thresholds: LiquidityConfig
  margin: MarginConfig
  iv_settings: Record<string, number>
}

export interface EntryFilters {
  rsi_range?: [number, number]
  directional_regime?: string[]
  volatility_regime?: string[]
  min_atr_percent?: number
  min_iv_percentile?: number
  max_atr_pct?: number
}

export interface StrategyRule {
  min_iv_rank: number
  preferred_iv_rank?: number
  market_outlook: string[]
  dte_range: [number, number]
  entry_filters?: EntryFilters
  requires?: string
  profit_target_pct?: number
  stop_loss_multiplier?: number
  time_stop?: string
  avoid_events?: string[]
}

export interface CircuitBreakerSettings {
  daily_loss_pct: number
  weekly_loss_pct: number
  vix_halt_threshold: number
  consecutive_loss_pause: number
  consecutive_loss_halt: number
  max_portfolio_drawdown: Record<string, number>
}

export interface TradingConstraintSettings {
  max_trades_per_day: number
  max_trades_per_week_per_portfolio: number
  no_entry_first_minutes: number
  no_entry_last_minutes: number
  require_approval_undefined_risk: boolean
  no_adding_to_losers_without_rationale: boolean
}

export interface TradingScheduleSettings {
  daily: string[]
  wednesday: string[]
  friday: string[]
  monthly_dte_window: [number, number]
  skip_0dte_on_fomc: boolean
  fomc_dates: string[]
}

export interface ExecutionDefaultSettings {
  order_type: string
  time_in_force: string
  price_strategy: string
  price_offset: number
  require_dry_run: boolean
  allowed_brokers: string[]
}

export interface WorkflowRulesResponse {
  workflow: {
    cycle_frequency_minutes: number
    market_hours: { open: string; close: string; timezone: string }
    boot_time_minutes_before_open: number
    eod_eval_time: string
    report_time: string
  }
  circuit_breakers: CircuitBreakerSettings
  trading_constraints: TradingConstraintSettings
  trading_schedule: TradingScheduleSettings
  decision_timeouts: Record<string, unknown>
  execution_defaults: ExecutionDefaultSettings
  notifications: Record<string, unknown>
  qa: Record<string, unknown>
}

export interface CapitalPlanResponse {
  idle_alert_pct: Record<string, number>
  escalation: {
    warning_days_idle: number
    critical_days_idle: number
    nag_frequency_hours: number
  }
  target_annual_return_pct: Record<string, number>
  staggered_deployment: {
    ramp_weeks: number
    max_deploy_per_week_pct: Record<string, number>
  }
}

// WebSocket message types
export type WSMessageType =
  | 'cell_update'
  | 'agent_status'
  | 'alert'
  | 'gate_update'
  | 'workflow_state'
  | 'pnl_tick'

export interface WSMessage {
  type: WSMessageType
  payload: unknown
  timestamp: string
}
