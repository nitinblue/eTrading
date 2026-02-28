import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'
import type { DailyTradingPlan } from '../api/types'

export function usePlan(tickers: string[]) {
  return useQuery<DailyTradingPlan>({
    queryKey: ['plan', tickers],
    queryFn: async () => {
      const { data } = await api.post(endpoints.plan, { tickers }, { timeout: 120_000 })
      return data
    },
    enabled: tickers.length > 0,
    refetchInterval: 600_000,
    staleTime: 300_000,
    retry: false,
  })
}
