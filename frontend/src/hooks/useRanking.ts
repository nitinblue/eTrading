import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'
import type { TradeRankingResult } from '../api/types'

export function useRanking(tickers: string[]) {
  return useQuery<TradeRankingResult>({
    queryKey: ['ranking', tickers],
    queryFn: async () => {
      const { data } = await api.post(endpoints.ranking, { tickers })
      return data
    },
    enabled: tickers.length > 0,
    refetchInterval: 300_000,
    staleTime: 120_000,
  })
}
