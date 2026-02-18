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
