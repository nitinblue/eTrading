import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'
import type { BlackSwanAlert } from '../api/types'

export function useBlackSwan() {
  return useQuery<BlackSwanAlert>({
    queryKey: ['black-swan'],
    queryFn: async () => {
      const { data } = await api.get(endpoints.blackSwan, { timeout: 30_000 })
      return data
    },
    refetchInterval: 300_000, // 5min
    staleTime: 120_000,
    retry: 1,
  })
}
