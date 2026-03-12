import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'
import type { DailyTradingPlan } from '../api/types'

export function usePlan(tickers: string[]) {
  return useQuery<DailyTradingPlan>({
    queryKey: ['plan', tickers],
    queryFn: async () => {
      const { data } = await api.post(endpoints.plan, { tickers }, { timeout: 15_000 })
      // If plan is still generating, throw to trigger retry
      if (data.status === 'generating') {
        throw new Error(data.message || 'Plan is being generated...')
      }
      return data
    },
    enabled: tickers.length > 0,
    refetchInterval: 900_000,  // refresh every 15 min
    staleTime: 600_000,
    retry: 6,                  // retry up to 6 times while generating
    retryDelay: 15_000,        // every 15s (6 × 15s = 90s coverage)
  })
}
