const V2 = '/api/v2'

export const endpoints = {
  // Portfolios
  portfolios: `${V2}/portfolios`,
  portfolio: (name: string) => `${V2}/portfolios/${name}`,
  portfolioTrades: (name: string) => `${V2}/portfolios/${name}/trades`,
  portfolioHistory: (name: string) => `${V2}/portfolios/${name}/history`,

  // Positions
  positions: `${V2}/positions`,
  position: (tradeId: string) => `${V2}/positions/${tradeId}`,

  // Trades
  trades: `${V2}/trades`,

  // Recommendations
  recommendations: `${V2}/recommendations`,
  recommendationDetail: (id: string) => `${V2}/recommendations/${id}`,
  approveRec: (id: string) => `/api/approve/${id}`,
  rejectRec: (id: string) => `/api/reject/${id}`,
  deferRec: (id: string) => `/api/defer/${id}`,

  // Workflow
  workflowStatus: `${V2}/workflow/status`,
  workflowAgents: `${V2}/workflow/agents`,
  workflowTimeline: `${V2}/workflow/timeline`,
  haltWorkflow: '/api/halt',
  resumeWorkflow: '/api/resume',

  // Risk
  risk: `${V2}/risk`,
  riskVar: `${V2}/risk/var`,
  riskFactors: `${V2}/risk/factors`,
  riskFactor: (underlying: string) => `${V2}/risk/factors/${underlying}`,

  // Broker Positions (synced from broker)
  brokerPositions: `${V2}/broker-positions`,

  // Capital
  capital: `${V2}/capital`,

  // Performance
  performance: `${V2}/performance`,

  // Decisions
  decisions: `${V2}/decisions`,

  // Execution
  execute: (tradeId: string) => `${V2}/execute/${tradeId}`,
  orders: `${V2}/orders`,

  // Agents
  agents: `${V2}/agents`,
  agentsSummary: `${V2}/agents/summary`,
  agentsLatestRuns: `${V2}/agents/runs/latest`,
  agentsContext: `${V2}/agents/context`,
  agentsTimeline: `${V2}/agents/timeline`,
  agentsMlStatus: `${V2}/agents/ml-status`,
  agent: (name: string) => `${V2}/agents/${name}`,
  agentRuns: (name: string) => `${V2}/agents/${name}/runs`,
  agentObjectives: (name: string) => `${V2}/agents/${name}/objectives`,

  // Agent Intelligence (LLM-powered)
  agentBrief: `${V2}/agent/brief`,
  agentChat: `${V2}/agent/chat`,
  agentAnalyze: (symbol: string) => `${V2}/agent/analyze/${symbol}`,
  agentIntelStatus: `${V2}/agent/status`,

  // Account Activity
  accountTransactions: `${V2}/account/transactions`,
  accountOrders: `${V2}/account/orders`,
  liveOrders: `${V2}/account/live-orders`,
  equityCurve: `${V2}/account/equity-curve`,
  marketMetrics: `${V2}/account/market-metrics`,

  // Trading Dashboard
  tradingDashboard: (portfolio: string) => `${V2}/trading-dashboard/${portfolio}`,
  refreshDashboard: (portfolio: string) => `${V2}/trading-dashboard/${portfolio}/refresh`,
  addWhatIf: (portfolio: string) => `${V2}/trading-dashboard/${portfolio}/add-whatif`,
  bookTrade: (portfolio: string) => `${V2}/trading-dashboard/${portfolio}/book`,
  deleteWhatIf: (portfolio: string, tradeId: string) => `${V2}/trading-dashboard/${portfolio}/whatif/${tradeId}`,

  // Research Container (unified research data)
  research: `${V2}/research`,
  researchTicker: (ticker: string) => `${V2}/research/${ticker}`,
  researchRefresh: `${V2}/research/refresh`,
  researchWatchlist: `${V2}/research/watchlist`,
  researchWatchlistTicker: (ticker: string) => `${V2}/research/watchlist/${ticker}`,

  // Market Watchlist + Regime
  marketWatchlist: `${V2}/market/watchlist`,
  regime: (ticker: string) => `${V2}/regime/${ticker}`,
  regimeBatch: `${V2}/regime/batch`,
  regimeResearch: (ticker: string) => `${V2}/regime/${ticker}/research`,
  regimeChart: (ticker: string) => `${V2}/regime/${ticker}/chart`,
  regimeResearchBatch: `${V2}/regime/research`,
  technicals: (ticker: string) => `${V2}/technicals/${ticker}`,
  fundamentals: (ticker: string) => `${V2}/fundamentals/${ticker}`,
  macroCalendar: `${V2}/macro/calendar`,

  // Levels Analysis
  levels: (ticker: string) => `${V2}/levels/${ticker}`,

  // Phase Detection
  phase: (ticker: string) => `${V2}/phase/${ticker}`,

  // Opportunity Assessments
  opportunityZeroDte: (ticker: string) => `${V2}/opportunity/zero-dte/${ticker}`,
  opportunityLeap: (ticker: string) => `${V2}/opportunity/leap/${ticker}`,
  opportunityBreakout: (ticker: string) => `${V2}/opportunity/breakout/${ticker}`,
  opportunityMomentum: (ticker: string) => `${V2}/opportunity/momentum/${ticker}`,
  opportunityIronCondor: (ticker: string) => `${V2}/opportunity/iron-condor/${ticker}`,
  opportunityIronButterfly: (ticker: string) => `${V2}/opportunity/iron-butterfly/${ticker}`,
  opportunityCalendar: (ticker: string) => `${V2}/opportunity/calendar/${ticker}`,
  opportunityDiagonal: (ticker: string) => `${V2}/opportunity/diagonal/${ticker}`,
  opportunityMeanReversion: (ticker: string) => `${V2}/opportunity/mean-reversion/${ticker}`,

  // Black Swan / Tail Risk
  blackSwan: `${V2}/black-swan`,

  // Market Context (pre-trade gate)
  marketContext: `${V2}/context`,

  // Screening
  screening: `${V2}/screening`,

  // Ranking
  ranking: `${V2}/ranking`,

  // Daily Trading Plan
  plan: `${V2}/plan`,

  // Terminal
  terminalExecute: `${V2}/terminal/execute`,

  // WebSocket
  ws: '/ws',
} as const

// Reports
const REPORTS = '/api/reports'

export const reportEndpoints = {
  tradeJournal: `${REPORTS}/trade-journal`,
  performance: `${REPORTS}/performance`,
  strategyBreakdown: `${REPORTS}/strategy-breakdown`,
  sourceAttribution: `${REPORTS}/source-attribution`,
  weeklyPnl: `${REPORTS}/weekly-pnl`,
  decisions: `${REPORTS}/decisions`,
  recommendations: `${REPORTS}/recommendations`,
  tradeEvents: `${REPORTS}/trade-events`,
  dailySnapshots: `${REPORTS}/daily-snapshots`,
  greeksHistory: `${REPORTS}/greeks-history`,
} as const

// Data Explorer
const EXPLORER = '/api/explorer'

export const explorerEndpoints = {
  tables: `${EXPLORER}/tables`,
  table: (name: string) => `${EXPLORER}/tables/${name}`,
  query: `${EXPLORER}/query`,
  queryCsv: `${EXPLORER}/query/csv`,
} as const
