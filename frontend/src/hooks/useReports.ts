import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { reportEndpoints } from '../api/endpoints'
import type {
  TradeJournalEntry,
  PerformanceMetricsReport,
  WeeklyPnLEntry,
  DecisionAuditEntry,
  TradeEventEntry,
  RecommendationReport,
} from '../api/types'

// ---------------------------------------------------------------------------
// Trade Journal
// ---------------------------------------------------------------------------

interface TradeJournalParams {
  portfolio?: string
  status?: string
  date_from?: string
  date_to?: string
  source?: string
  strategy?: string
  limit?: number
  offset?: number
}

export function useTradeJournal(params: TradeJournalParams = {}) {
  return useQuery<{ total: number; trades: TradeJournalEntry[] }>({
    queryKey: ['reports', 'trade-journal', params],
    queryFn: async () => {
      const { data } = await api.get(reportEndpoints.tradeJournal, { params })
      return data
    },
  })
}

// ---------------------------------------------------------------------------
// Performance
// ---------------------------------------------------------------------------

export function usePerformanceReport(portfolio?: string) {
  return useQuery<PerformanceMetricsReport[]>({
    queryKey: ['reports', 'performance', portfolio],
    queryFn: async () => {
      const { data } = await api.get(reportEndpoints.performance, {
        params: portfolio ? { portfolio } : {},
      })
      return data
    },
  })
}

// ---------------------------------------------------------------------------
// Strategy Breakdown
// ---------------------------------------------------------------------------

export function useStrategyBreakdown(portfolio: string) {
  return useQuery<{ portfolio: string; strategies: Record<string, PerformanceMetricsReport> }>({
    queryKey: ['reports', 'strategy-breakdown', portfolio],
    queryFn: async () => {
      const { data } = await api.get(reportEndpoints.strategyBreakdown, {
        params: { portfolio },
      })
      return data
    },
    enabled: !!portfolio,
  })
}

// ---------------------------------------------------------------------------
// Source Attribution
// ---------------------------------------------------------------------------

export function useSourceAttribution(portfolio: string) {
  return useQuery<{ portfolio: string; sources: Record<string, PerformanceMetricsReport> }>({
    queryKey: ['reports', 'source-attribution', portfolio],
    queryFn: async () => {
      const { data } = await api.get(reportEndpoints.sourceAttribution, {
        params: { portfolio },
      })
      return data
    },
    enabled: !!portfolio,
  })
}

// ---------------------------------------------------------------------------
// Weekly P&L
// ---------------------------------------------------------------------------

export function useWeeklyPnl(portfolio: string, weeks = 12) {
  return useQuery<{ portfolio: string; weeks: WeeklyPnLEntry[] }>({
    queryKey: ['reports', 'weekly-pnl', portfolio, weeks],
    queryFn: async () => {
      const { data } = await api.get(reportEndpoints.weeklyPnl, {
        params: { portfolio, weeks },
      })
      return data
    },
    enabled: !!portfolio,
  })
}

// ---------------------------------------------------------------------------
// Decision Audit
// ---------------------------------------------------------------------------

interface DecisionAuditParams {
  decision_type?: string
  response?: string
  date_from?: string
  date_to?: string
  limit?: number
  offset?: number
}

export function useDecisionAudit(params: DecisionAuditParams = {}) {
  return useQuery<{ total: number; decisions: DecisionAuditEntry[] }>({
    queryKey: ['reports', 'decisions', params],
    queryFn: async () => {
      const { data } = await api.get(reportEndpoints.decisions, { params })
      return data
    },
  })
}

// ---------------------------------------------------------------------------
// Recommendations Report
// ---------------------------------------------------------------------------

interface RecommendationsParams {
  status?: string
  source?: string
  underlying?: string
  date_from?: string
  date_to?: string
  limit?: number
  offset?: number
}

export function useRecommendationsReport(params: RecommendationsParams = {}) {
  return useQuery<{ total: number; recommendations: RecommendationReport[] }>({
    queryKey: ['reports', 'recommendations', params],
    queryFn: async () => {
      const { data } = await api.get(reportEndpoints.recommendations, { params })
      return data
    },
  })
}

// ---------------------------------------------------------------------------
// Trade Events
// ---------------------------------------------------------------------------

interface TradeEventsParams {
  trade_id?: string
  event_type?: string
  underlying?: string
  date_from?: string
  date_to?: string
  limit?: number
  offset?: number
}

export function useTradeEvents(params: TradeEventsParams = {}) {
  return useQuery<{ total: number; events: TradeEventEntry[] }>({
    queryKey: ['reports', 'trade-events', params],
    queryFn: async () => {
      const { data } = await api.get(reportEndpoints.tradeEvents, { params })
      return data
    },
  })
}

// ---------------------------------------------------------------------------
// Daily Snapshots
// ---------------------------------------------------------------------------

export function useDailySnapshots(portfolio?: string, days = 30) {
  return useQuery({
    queryKey: ['reports', 'daily-snapshots', portfolio, days],
    queryFn: async () => {
      const { data } = await api.get(reportEndpoints.dailySnapshots, {
        params: { ...(portfolio ? { portfolio } : {}), days },
      })
      return data
    },
  })
}
