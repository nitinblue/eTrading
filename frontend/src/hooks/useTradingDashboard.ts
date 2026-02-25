import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'
import type { TradingDashboardData, RefreshResult, TemplateEvaluationResult } from '../api/types'

export function useTradingDashboard(portfolio: string) {
  return useQuery<TradingDashboardData>({
    queryKey: ['trading-dashboard', portfolio],
    queryFn: async () => {
      const { data } = await api.get(endpoints.tradingDashboard(portfolio), { timeout: 30_000 })
      return data
    },
    refetchInterval: 60_000,
    enabled: !!portfolio,
    retry: 1,
    retryDelay: 5_000,
  })
}

export function useRefreshDashboard(portfolio: string) {
  const qc = useQueryClient()
  return useMutation<RefreshResult, Error, boolean>({
    mutationFn: async (snapshot: boolean) => {
      const { data } = await api.post(
        endpoints.refreshDashboard(portfolio) + (snapshot ? '?snapshot=true' : ''),
      )
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trading-dashboard', portfolio] })
    },
  })
}

export function useEvaluateTemplate(portfolio: string) {
  const qc = useQueryClient()
  return useMutation<TemplateEvaluationResult, Error, string>({
    mutationFn: async (templateName: string) => {
      const { data } = await api.post(endpoints.evaluateTemplate(portfolio), {
        template_name: templateName,
      })
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trading-dashboard', portfolio] })
    },
  })
}

export function useAddWhatIf(portfolio: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (trade: {
      underlying: string
      strategy_type: string
      legs: Array<Record<string, unknown>>
      notes?: string
    }) => {
      const { data } = await api.post(endpoints.addWhatIf(portfolio), trade)
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trading-dashboard', portfolio] })
    },
  })
}

export function useBookTrade(portfolio: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (whatifTradeId: string) => {
      const { data } = await api.post(endpoints.bookTrade(portfolio), {
        whatif_trade_id: whatifTradeId,
      })
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trading-dashboard'] })
    },
  })
}

export function useDeleteWhatIf(portfolio: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (tradeId: string) => {
      const { data } = await api.delete(
        endpoints.deleteWhatIf(portfolio, tradeId),
      )
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trading-dashboard'] })
    },
  })
}
