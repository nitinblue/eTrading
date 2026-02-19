import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'
import type { Recommendation } from '../api/types'

interface RecommendationParams {
  status?: string
  source?: string
  portfolio?: string
}

export function useRecommendations(params: RecommendationParams = {}) {
  return useQuery<Recommendation[]>({
    queryKey: ['recommendations', params],
    queryFn: async () => {
      const { data } = await api.get(endpoints.recommendations, { params })
      return Array.isArray(data) ? data : data.recommendations ?? []
    },
    refetchInterval: 10_000,
  })
}

export function useApproveRec() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, portfolio, notes }: { id: string; portfolio?: string; notes?: string }) => {
      const { data } = await api.post(endpoints.approveRec(id), { portfolio, notes })
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recommendations'] })
      qc.invalidateQueries({ queryKey: ['workflowStatus'] })
    },
  })
}

export function useRejectRec() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, reason }: { id: string; reason?: string }) => {
      const { data } = await api.post(endpoints.rejectRec(id), { reason })
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recommendations'] })
    },
  })
}

export function useDeferRec() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.post(endpoints.deferRec(id))
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recommendations'] })
    },
  })
}
