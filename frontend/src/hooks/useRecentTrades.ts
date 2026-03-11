import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { reportEndpoints } from '../api/endpoints'

export interface RecentTrade {
  id: string
  underlying_symbol: string
  strategy_type: string | null
  trade_type: string
  trade_status: string
  trade_source: string | null
  entry_price: number | null
  exit_price: number | null
  total_pnl: number | null
  delta_pnl: number | null
  theta_pnl: number | null
  vega_pnl: number | null
  max_risk: number | null
  exit_reason: string | null
  is_open: boolean
  duration_days: number | null
  legs_count: number | null
  created_at: string
  opened_at: string | null
  closed_at: string | null
  portfolio_name: string | null
  notes: string | null
}

export function useRecentTrades(limit = 20) {
  return useQuery<{ total: number; trades: RecentTrade[] }>({
    queryKey: ['recentTrades', limit],
    queryFn: async () => {
      const { data } = await api.get(reportEndpoints.tradeJournal, {
        params: { limit, offset: 0 },
      })
      return data
    },
    refetchInterval: 15_000,
    retry: 1,
  })
}

export function useClosedTrades(limit = 100) {
  return useQuery<{ total: number; trades: RecentTrade[] }>({
    queryKey: ['closedTrades', limit],
    queryFn: async () => {
      const { data } = await api.get(reportEndpoints.tradeJournal, {
        params: { limit, offset: 0, status: 'closed' },
      })
      return data
    },
    refetchInterval: 30_000,
    retry: 1,
  })
}
