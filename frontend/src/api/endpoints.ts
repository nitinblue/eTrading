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
  approveRec: (id: string) => `${V2}/recommendations/${id}/approve`,
  rejectRec: (id: string) => `${V2}/recommendations/${id}/reject`,
  deferRec: (id: string) => `${V2}/recommendations/${id}/defer`,

  // Workflow
  workflowStatus: `${V2}/workflow/status`,
  workflowAgents: `${V2}/workflow/agents`,
  workflowTimeline: `${V2}/workflow/timeline`,

  // Risk
  risk: `${V2}/risk`,
  riskVar: `${V2}/risk/var`,

  // Capital
  capital: `${V2}/capital`,

  // Performance
  performance: `${V2}/performance`,

  // Decisions
  decisions: `${V2}/decisions`,

  // Execution
  execute: (tradeId: string) => `${V2}/execute/${tradeId}`,
  orders: `${V2}/orders`,

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
