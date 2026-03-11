import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'

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

