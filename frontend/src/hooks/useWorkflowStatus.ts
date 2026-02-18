import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'
import type { WorkflowStatus } from '../api/types'

export function useWorkflowStatus() {
  return useQuery<WorkflowStatus>({
    queryKey: ['workflowStatus'],
    queryFn: async () => {
      const { data } = await api.get(endpoints.workflowStatus)
      return data
    },
    refetchInterval: 5_000,
  })
}
