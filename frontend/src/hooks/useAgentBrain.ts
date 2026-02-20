import { useQuery, useMutation } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'

interface AgentBriefResponse {
  available: boolean
  brief: string
  generated_at?: string
  data_summary?: {
    positions: number
    transactions: number
    pending_recs: number
    has_market_metrics: boolean
  }
}

interface AgentChatResponse {
  available: boolean
  response: string
  generated_at?: string
}

interface AgentStatusResponse {
  llm_available: boolean
  broker_connected: boolean
  capabilities: {
    portfolio_brief: boolean
    position_analysis: boolean
    chat: boolean
    recommendations: boolean
    accountability: boolean
  }
}

export function useAgentBrief() {
  return useQuery<AgentBriefResponse>({
    queryKey: ['agentBrief'],
    queryFn: async () => {
      const { data } = await api.get<AgentBriefResponse>(endpoints.agentBrief)
      return data
    },
    refetchInterval: 5 * 60_000, // Refresh every 5 minutes
    staleTime: 2 * 60_000,
  })
}

export function useAgentStatus() {
  return useQuery<AgentStatusResponse>({
    queryKey: ['agentStatus'],
    queryFn: async () => {
      const { data } = await api.get<AgentStatusResponse>(endpoints.agentIntelStatus)
      return data
    },
    refetchInterval: 30_000,
  })
}

export function useAgentChat() {
  return useMutation<AgentChatResponse, Error, string>({
    mutationFn: async (message: string) => {
      const { data } = await api.post<AgentChatResponse>(endpoints.agentChat, { message })
      return data
    },
  })
}

export function useAgentAnalysis(symbol: string) {
  return useQuery<{ available: boolean; analysis: string; position?: Record<string, unknown> }>({
    queryKey: ['agentAnalysis', symbol],
    queryFn: async () => {
      const { data } = await api.get(endpoints.agentAnalyze(symbol))
      return data
    },
    enabled: !!symbol,
  })
}
