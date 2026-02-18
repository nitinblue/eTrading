import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'
import type {
  AgentInfo,
  AgentDetail,
  AgentSummary,
  AgentRunsResponse,
  AgentObjectivesResponse,
  MLStatus,
  AgentTimelineCycle,
} from '../api/types'

// ---------------------------------------------------------------------------
// All agents list
// ---------------------------------------------------------------------------

export function useAgents() {
  return useQuery<AgentInfo[]>({
    queryKey: ['agents'],
    queryFn: async () => {
      const { data } = await api.get(endpoints.agents)
      return data
    },
    refetchInterval: 30_000,
  })
}

// ---------------------------------------------------------------------------
// Agent summary stats
// ---------------------------------------------------------------------------

export function useAgentSummary() {
  return useQuery<AgentSummary>({
    queryKey: ['agents', 'summary'],
    queryFn: async () => {
      const { data } = await api.get(endpoints.agentsSummary)
      return data
    },
    refetchInterval: 30_000,
  })
}

// ---------------------------------------------------------------------------
// Single agent detail
// ---------------------------------------------------------------------------

export function useAgentDetail(name: string) {
  return useQuery<AgentDetail>({
    queryKey: ['agents', name],
    queryFn: async () => {
      const { data } = await api.get(endpoints.agent(name))
      return data
    },
    enabled: !!name,
  })
}

// ---------------------------------------------------------------------------
// Agent run history (paginated)
// ---------------------------------------------------------------------------

export function useAgentRuns(name: string, limit = 50, offset = 0) {
  return useQuery<AgentRunsResponse>({
    queryKey: ['agents', name, 'runs', limit, offset],
    queryFn: async () => {
      const { data } = await api.get(endpoints.agentRuns(name), {
        params: { limit, offset },
      })
      return data
    },
    enabled: !!name,
  })
}

// ---------------------------------------------------------------------------
// Agent objectives history
// ---------------------------------------------------------------------------

export function useAgentObjectives(name: string, days = 30) {
  return useQuery<AgentObjectivesResponse>({
    queryKey: ['agents', name, 'objectives', days],
    queryFn: async () => {
      const { data } = await api.get(endpoints.agentObjectives(name), {
        params: { days },
      })
      return data
    },
    enabled: !!name,
  })
}

// ---------------------------------------------------------------------------
// ML pipeline status
// ---------------------------------------------------------------------------

export function useMLStatus() {
  return useQuery<MLStatus>({
    queryKey: ['agents', 'ml-status'],
    queryFn: async () => {
      const { data } = await api.get(endpoints.agentsMlStatus)
      return data
    },
  })
}

// ---------------------------------------------------------------------------
// Agent timeline (recent cycles)
// ---------------------------------------------------------------------------

export function useAgentTimeline(cycles = 3) {
  return useQuery<{ cycles: Record<string, AgentTimelineCycle[]> }>({
    queryKey: ['agents', 'timeline', cycles],
    queryFn: async () => {
      const { data } = await api.get(endpoints.agentsTimeline, {
        params: { cycles },
      })
      return data
    },
  })
}
