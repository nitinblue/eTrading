import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'
import type { CapitalUtilization } from '../api/types'

export function useCapitalData() {
  return useQuery<CapitalUtilization[]>({
    queryKey: ['capital'],
    queryFn: async () => {
      const { data } = await api.get(endpoints.capital)
      return Array.isArray(data) ? data : data?.portfolios ?? []
    },
    refetchInterval: 15_000,
  })
}
