import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'
import type { MarketWatchlistItem, TickerResearch, RegimeChartResponse, TechnicalSnapshot, FundamentalsSnapshot, MacroCalendar } from '../api/types'

export function useMarketWatchlist() {
  return useQuery<MarketWatchlistItem[]>({
    queryKey: ['marketWatchlist'],
    queryFn: async () => {
      const { data } = await api.get(endpoints.marketWatchlist)
      return data
    },
    refetchInterval: 300_000,
  })
}

export function useRegimeResearch(ticker: string | null) {
  return useQuery<TickerResearch>({
    queryKey: ['regimeResearch', ticker],
    queryFn: async () => {
      const { data } = await api.get(endpoints.regimeResearch(ticker!))
      return data
    },
    enabled: !!ticker,
    refetchInterval: 300_000,
  })
}

export function useRegimeChart(ticker: string | null) {
  return useQuery<RegimeChartResponse>({
    queryKey: ['regimeChart', ticker],
    queryFn: async () => {
      const { data } = await api.get(endpoints.regimeChart(ticker!))
      return data
    },
    enabled: !!ticker,
    refetchInterval: 300_000,
  })
}

export function useTechnicals(ticker: string | null) {
  return useQuery<TechnicalSnapshot>({
    queryKey: ['technicals', ticker],
    queryFn: async () => {
      const { data } = await api.get(endpoints.technicals(ticker!))
      return data
    },
    enabled: !!ticker,
    refetchInterval: 300_000,
  })
}

export function useFundamentals(ticker: string | null) {
  return useQuery<FundamentalsSnapshot>({
    queryKey: ['fundamentals', ticker],
    queryFn: async () => {
      const { data } = await api.get(endpoints.fundamentals(ticker!))
      return data
    },
    enabled: !!ticker,
    refetchInterval: 600_000,
  })
}

export function useMacroCalendar() {
  return useQuery<MacroCalendar>({
    queryKey: ['macroCalendar'],
    queryFn: async () => {
      const { data } = await api.get(endpoints.macroCalendar)
      return data
    },
    refetchInterval: 600_000,
  })
}
