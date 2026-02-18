import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'
import type { Trade } from '../api/types'

export function usePositions(portfolioName?: string) {
  return useQuery<Trade[]>({
    queryKey: ['positions', portfolioName],
    queryFn: async () => {
      const params: Record<string, string> = {}
      if (portfolioName) params.portfolio = portfolioName
      const { data } = await api.get(endpoints.positions, { params })
      return data
    },
    refetchInterval: 15_000,
  })
}

export function usePosition(tradeId: string) {
  return useQuery<Trade>({
    queryKey: ['position', tradeId],
    queryFn: async () => {
      const { data } = await api.get(endpoints.position(tradeId))
      return data
    },
    enabled: !!tradeId,
    refetchInterval: 15_000,
  })
}

export function usePortfolioTrades(portfolioName: string) {
  return useQuery<Trade[]>({
    queryKey: ['portfolioTrades', portfolioName],
    queryFn: async () => {
      const { data } = await api.get(endpoints.portfolioTrades(portfolioName))
      return data
    },
    enabled: !!portfolioName,
    refetchInterval: 15_000,
  })
}
