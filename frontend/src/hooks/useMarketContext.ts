import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'
import type { MarketContextData } from '../api/types'

export function useMarketContext() {
  return useQuery<MarketContextData>({
    queryKey: ['market-context'],
    queryFn: async () => {
      const { data } = await api.get(endpoints.marketContext, { timeout: 30_000 })
      return data
    },
    refetchInterval: 300_000, // 5min
    staleTime: 120_000,
    retry: 1,
  })
}
