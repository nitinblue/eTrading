import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'
import type { AgentTimelineCycle } from '../api/types'

export function useHaltWorkflow() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post(endpoints.haltWorkflow)
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['workflowStatus'] })
    },
  })
}

export function useResumeWorkflow() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (rationale: string) => {
      const { data } = await api.post(endpoints.resumeWorkflow, { rationale })
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['workflowStatus'] })
    },
  })
}

export function useAgentTimeline(cycles = 3) {
  return useQuery<Record<string, AgentTimelineCycle[]>>({
    queryKey: ['agentTimeline', cycles],
    queryFn: async () => {
      const { data } = await api.get(endpoints.agentsTimeline, { params: { cycles } })
      return data
    },
    refetchInterval: 15_000,
  })
}
