import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'
import type { ResearchResponse } from '../api/types'

export function useResearch(skipFundamentals = false) {
  return useQuery<ResearchResponse>({
    queryKey: ['research', skipFundamentals],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (skipFundamentals) params.set('skip_fundamentals', 'true')
      const url = params.toString()
        ? `${endpoints.research}?${params}`
        : endpoints.research
      const { data } = await api.get(url)
      return data
    },
    refetchInterval: 300_000, // 5 min
  })
}

export function useRefreshResearch() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (tickers?: string[]) => {
      const body = tickers ? { tickers } : {}
      const { data } = await api.post(endpoints.researchRefresh, body)
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['research'] })
    },
  })
}
