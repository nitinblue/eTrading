import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'
import type { BrokerPosition } from '../api/types'

interface BrokerPositionsResponse {
  positions: BrokerPosition[]
  count: number
}

export function useBrokerPositions(portfolioName?: string) {
  return useQuery<BrokerPosition[]>({
    queryKey: ['brokerPositions', portfolioName],
    queryFn: async () => {
      const params: Record<string, string> = {}
      if (portfolioName) params.portfolio = portfolioName
      const { data } = await api.get<BrokerPositionsResponse>(endpoints.brokerPositions, { params })
      return data.positions || []
    },
    refetchInterval: 15_000,
  })
}
