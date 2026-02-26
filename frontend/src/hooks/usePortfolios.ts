import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'
import type { Portfolio } from '../api/types'

export function usePortfolios() {
  return useQuery<Portfolio[]>({
    queryKey: ['portfolios'],
    queryFn: async () => {
      const { data } = await api.get(endpoints.portfolios, { timeout: 30_000 })
      return data
    },
    refetchInterval: 15_000,
    retry: 2,
    retryDelay: 3_000,
  })
}

export function usePortfolio(name: string) {
  return useQuery<Portfolio>({
    queryKey: ['portfolio', name],
    queryFn: async () => {
      const { data } = await api.get(endpoints.portfolio(name))
      return data
    },
    enabled: !!name,
    refetchInterval: 15_000,
  })
}
