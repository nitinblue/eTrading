import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'
import type { ResearchResponse, ResearchEntry, WatchlistResponse } from '../api/types'

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

export function useResearchTicker(ticker: string | null) {
  return useQuery<ResearchEntry>({
    queryKey: ['research-ticker', ticker],
    queryFn: async () => {
      const { data } = await api.get(endpoints.researchTicker(ticker!))
      return data
    },
    enabled: !!ticker,
    refetchInterval: 300_000,
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

export function useWatchlist() {
  return useQuery<WatchlistResponse>({
    queryKey: ['watchlist'],
    queryFn: async () => {
      const { data } = await api.get(endpoints.researchWatchlist)
      return data
    },
  })
}

export function useAddWatchlistTicker() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { ticker: string; name?: string; asset_class?: string }) => {
      const { data } = await api.post(endpoints.researchWatchlist, body)
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['watchlist'] })
      qc.invalidateQueries({ queryKey: ['research'] })
    },
  })
}

export function useRemoveWatchlistTicker() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (ticker: string) => {
      const { data } = await api.delete(endpoints.researchWatchlistTicker(ticker))
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['watchlist'] })
      qc.invalidateQueries({ queryKey: ['research'] })
    },
  })
}
