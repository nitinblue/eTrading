import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'
import type { RiskFactor, BrokerPosition } from '../api/types'

export function useRiskFactors(portfolio?: string) {
  return useQuery<RiskFactor[]>({
    queryKey: ['riskFactors', portfolio],
    queryFn: async () => {
      const params: Record<string, string> = {}
      if (portfolio) params.portfolio = portfolio
      const { data } = await api.get(endpoints.riskFactors, { params })
      return data.factors ?? []
    },
    refetchInterval: 15_000,
  })
}

export function useBrokerPositions(portfolio?: string) {
  return useQuery<BrokerPosition[]>({
    queryKey: ['brokerPositions', portfolio],
    queryFn: async () => {
      const params: Record<string, string> = {}
      if (portfolio) params.portfolio = portfolio
      const { data } = await api.get(endpoints.brokerPositions, { params })
      return data.positions ?? []
    },
    refetchInterval: 15_000,
  })
}
