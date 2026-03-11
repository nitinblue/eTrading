import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'
import type { DailyTradingPlan } from '../api/types'

export function usePlan(tickers: string[]) {
  return useQuery<DailyTradingPlan>({
    queryKey: ['plan', tickers],
    queryFn: async () => {
      const { data } = await api.post(endpoints.plan, { tickers }, { timeout: 180_000 })
      return data
    },
    enabled: tickers.length > 0,
    refetchInterval: 900_000,
    staleTime: 600_000,
    retry: false,
  })
}
