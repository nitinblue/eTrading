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

// ---------------------------------------------------------------------------
// Reports Types
// ---------------------------------------------------------------------------

export interface TradeJournalEntry {
  id: string
  portfolio_name: string
  strategy_type: string | null
  underlying_symbol: string
  trade_type: string
  trade_status: string
  trade_source: string
  is_open: boolean
  legs_count: number
  entry_price: number
  exit_price: number
  total_pnl: number
  delta_pnl: number
  theta_pnl: number
  vega_pnl: number
  max_risk: number
  duration_days: number | null
  created_at: string
  opened_at: string | null
  closed_at: string | null
  notes: string | null
  rolled_from_id: string | null
  rolled_to_id: string | null
}

export interface PerformanceMetricsReport {
  label: string
  portfolio_id: string
  total_trades: number
  winning_trades: number
  losing_trades: number
  breakeven_trades: number
  total_pnl: number
  total_wins: number
  total_losses: number
  avg_win: number
  avg_loss: number
  biggest_win: number
  biggest_loss: number
  win_rate: number
  profit_factor: number
  expectancy: number
  max_drawdown_pct: number
  cagr_pct: number
  sharpe_ratio: number
  mar_ratio: number
  initial_capital: number
  current_equity: number
  return_pct: number
}

export interface WeeklyPnLEntry {
  week_start: string
  week_end: string
  pnl: number
  trade_count: number
  cumulative_pnl: number
}

export interface DecisionAuditEntry {
  id: string
  recommendation_id: string | null
  decision_type: string
  presented_at: string
  responded_at: string | null
  response: string | null
  rationale: string | null
  escalation_count: number
  time_to_decision_seconds: number | null
}

export interface TradeEventEntry {
  event_id: string
  trade_id: string | null
  event_type: string
  timestamp: string
  strategy_type: string | null
  underlying_symbol: string
  net_credit_debit: number
  entry_delta: number
  entry_theta: number
  market_context: Record<string, unknown> | null
  outcome: Record<string, unknown> | null
  tags: string[] | null
}

export interface RecommendationReport {
  id: string
  recommendation_type: string
  source: string
  screener_name: string | null
  underlying: string
  strategy_type: string
  confidence: number
  rationale: string | null
  risk_category: string
  suggested_portfolio: string | null
  status: string
  created_at: string
  reviewed_at: string | null
  portfolio_name: string | null
  trade_id_to_close: string | null
  exit_action: string | null
  exit_urgency: string | null
  triggered_rules: string[] | null
}

// ---------------------------------------------------------------------------
// Data Explorer Types
// ---------------------------------------------------------------------------

export interface ColumnMeta {
  name: string
  type: 'string' | 'numeric' | 'datetime' | 'boolean' | 'json'
  nullable: boolean
}

export interface TableInfo {
  name: string
  row_count: number
  columns: ColumnMeta[]
  sample_rows?: Record<string, unknown>[]
}

export interface ExplorerFilterSpec {
  column: string
  operator: string
  value: string
  value2?: string
}

export interface ExplorerQuery {
  table: string
  columns?: string[]
  filters?: ExplorerFilterSpec[]
  sort_by?: string
  sort_desc?: boolean
  limit?: number
  offset?: number
}

export interface ExplorerResult {
  table: string
  total: number
  offset: number
  limit: number
  columns: ColumnMeta[]
  rows: Record<string, unknown>[]
}

// ---------------------------------------------------------------------------
// Agent Types
// ---------------------------------------------------------------------------

export interface AgentInfo {
  name: string
  display_name: string
  category: 'safety' | 'perception' | 'analysis' | 'execution' | 'learning'
  role: string
  description: string
  responsibilities: string[]
  runs_during: string[]
  capabilities_implemented: string[]
  capabilities_planned: string[]
  status: string
  last_run_at: string | null
  last_duration_ms: number | null
  last_error: string | null
  run_count: number
  today_grade: string | null
  today_objective: string | null
}

export interface AgentRun {
  id: string
  cycle_id: number | null
  workflow_state: string | null
  status: string
  started_at: string
  finished_at: string | null
  duration_ms: number | null
  messages: string[]
  data: Record<string, unknown>
  metrics: Record<string, unknown>
  objectives: string[]
  requires_human: boolean
  human_prompt: string | null
  error_message: string | null
}

export interface AgentObjective {
  id: string
  date: string
  objective: string | null
  target_metric: string | null
  target_value: number | null
  actual_value: number | null
  grade: string | null
  gap_analysis: string | null
  set_at: string | null
  evaluated_at: string | null
}

export interface AgentDetail extends Omit<AgentInfo, 'status' | 'last_run_at' | 'last_duration_ms' | 'last_error' | 'run_count' | 'today_grade' | 'today_objective'> {
  stats: {
    total_runs: number
    avg_duration_ms: number
    error_count: number
  }
  recent_runs: AgentRun[]
  objectives: AgentObjective[]
}

export interface AgentSummary {
  total_agents: number
  today_runs: number
  today_errors: number
  avg_duration_ms: number
  grade_distribution: Record<string, number>
  cycle_count: number
  current_state: string
}

export interface AgentRunsResponse {
  total: number
  offset: number
  limit: number
  runs: AgentRun[]
}

export interface AgentObjectivesResponse {
  agent_name: string
  days: number
  objectives: AgentObjective[]
}

export interface MLStatus {
  snapshots: number
  events: number
  events_with_outcomes: number
  closed_trades: number
  supervised_learning_ready: boolean
  supervised_trades_needed: number
  rl_ready: boolean
  rl_trades_needed: number
  features_defined: number
  feature_groups: {
    market: number
    position: number
    portfolio: number
  }
}

export interface AgentTimelineCycle {
  agent_name: string
  status: string
  workflow_state: string | null
  started_at: string
  duration_ms: number | null
  error_message: string | null
}

// ---------------------------------------------------------------------------
// Risk Factor & Broker Position Types
// ---------------------------------------------------------------------------

export interface RiskFactor {
  id: string
  underlying: string
  spot: number
  spot_chg: number
  delta: number
  gamma: number
  theta: number
  vega: number
  'delta_$': number
  positions: number
  long: number
  short: number
  pnl: number
  limit_used: number
  status: 'OK' | 'WARNING' | 'BREACH'
}

export interface BrokerPosition {
  id: string
  symbol: string
  underlying: string
  type: string
  strike: number | null
  expiry: string | null
  dte: number | null
  qty: number
  entry: number
  mark: number
  bid: number
  ask: number
  delta: number
  gamma: number
  theta: number
  vega: number
  iv: number | null
  pnl: number
  pnl_pct: number
  pnl_delta: number
  pnl_theta: number
  pnl_vega: number
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
