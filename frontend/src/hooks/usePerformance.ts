import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { reportEndpoints } from '../api/endpoints'
import type { PerformanceMetricsReport, WeeklyPnLEntry } from '../api/types'

export function usePerformanceMetrics(portfolio?: string) {
  return useQuery<PerformanceMetricsReport[]>({
    queryKey: ['performance', 'metrics', portfolio],
    queryFn: async () => {
      const { data } = await api.get(reportEndpoints.performance, {
        params: portfolio ? { portfolio } : {},
      })
      return Array.isArray(data) ? data : []
    },
  })
}

export function useWeeklyPnL(portfolio: string, weeks = 12) {
  return useQuery<WeeklyPnLEntry[]>({
    queryKey: ['performance', 'weeklyPnl', portfolio, weeks],
    queryFn: async () => {
      const { data } = await api.get(reportEndpoints.weeklyPnl, {
        params: { portfolio, weeks },
      })
      return data?.weeks ?? []
    },
    enabled: !!portfolio,
  })
}

interface BreakdownEntry {
  label: string
  total_trades: number
  winning_trades: number
  total_pnl: number
  avg_win: number
  avg_loss: number
  win_rate: number
  profit_factor: number
  sharpe_ratio: number
  biggest_win: number
  biggest_loss: number
}

export function useStrategyBreakdown(portfolio: string) {
  return useQuery<BreakdownEntry[]>({
    queryKey: ['performance', 'strategy', portfolio],
    queryFn: async () => {
      const { data } = await api.get(reportEndpoints.strategyBreakdown, {
        params: { portfolio },
      })
      // API returns { portfolio, strategies: { name: metrics } }
      const strategies = data?.strategies ?? {}
      return Object.entries(strategies).map(([name, m]) => ({
        label: name,
        ...(m as object),
      })) as BreakdownEntry[]
    },
    enabled: !!portfolio,
  })
}

export function useSourceAttribution(portfolio: string) {
  return useQuery<BreakdownEntry[]>({
    queryKey: ['performance', 'source', portfolio],
    queryFn: async () => {
      const { data } = await api.get(reportEndpoints.sourceAttribution, {
        params: { portfolio },
      })
      const sources = data?.sources ?? {}
      return Object.entries(sources).map(([name, m]) => ({
        label: name,
        ...(m as object),
      })) as BreakdownEntry[]
    },
    enabled: !!portfolio,
  })
}
