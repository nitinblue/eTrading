import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { adminEndpoints } from '../api/adminEndpoints'
import type {
  PortfolioConfig,
  RiskSettingsResponse,
  StrategyRule,
  WorkflowRulesResponse,
  CapitalPlanResponse,
} from '../api/types'

// ---------------------------------------------------------------------------
// Portfolios
// ---------------------------------------------------------------------------

export function useAdminPortfolios() {
  return useQuery<Record<string, PortfolioConfig>>({
    queryKey: ['admin', 'portfolios'],
    queryFn: async () => {
      const { data } = await api.get(adminEndpoints.portfolios)
      return data.portfolios
    },
  })
}

export function useAdminPortfolio(name: string) {
  return useQuery<PortfolioConfig & { name: string }>({
    queryKey: ['admin', 'portfolios', name],
    queryFn: async () => {
      const { data } = await api.get(adminEndpoints.portfolio(name))
      return data
    },
    enabled: !!name,
  })
}

export function useUpdatePortfolio() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ name, updates }: { name: string; updates: Partial<PortfolioConfig> }) => {
      const { data } = await api.put(adminEndpoints.portfolio(name), updates)
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'portfolios'] })
    },
  })
}

// ---------------------------------------------------------------------------
// Risk Settings
// ---------------------------------------------------------------------------

export function useAdminRisk() {
  return useQuery<RiskSettingsResponse>({
    queryKey: ['admin', 'risk'],
    queryFn: async () => {
      const { data } = await api.get(adminEndpoints.risk)
      return data
    },
  })
}

export function useUpdateRisk() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (updates: Partial<RiskSettingsResponse>) => {
      const { data } = await api.put(adminEndpoints.risk, updates)
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'risk'] })
    },
  })
}

// ---------------------------------------------------------------------------
// Strategy Rules
// ---------------------------------------------------------------------------

export function useAdminStrategies() {
  return useQuery<Record<string, StrategyRule>>({
    queryKey: ['admin', 'strategies'],
    queryFn: async () => {
      const { data } = await api.get(adminEndpoints.strategies)
      return data.strategy_rules
    },
  })
}

export function useUpdateStrategy() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ name, updates }: { name: string; updates: Partial<StrategyRule> }) => {
      const { data } = await api.put(adminEndpoints.strategy(name), updates)
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'strategies'] })
    },
  })
}

// ---------------------------------------------------------------------------
// Workflow Rules
// ---------------------------------------------------------------------------

export function useAdminWorkflow() {
  return useQuery<WorkflowRulesResponse>({
    queryKey: ['admin', 'workflow'],
    queryFn: async () => {
      const { data } = await api.get(adminEndpoints.workflow)
      return data
    },
  })
}

export function useUpdateWorkflow() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (updates: Record<string, unknown>) => {
      const { data } = await api.put(adminEndpoints.workflow, updates)
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'workflow'] })
    },
  })
}

// ---------------------------------------------------------------------------
// Capital Plan
// ---------------------------------------------------------------------------

export function useAdminCapitalPlan() {
  return useQuery<CapitalPlanResponse>({
    queryKey: ['admin', 'capital-plan'],
    queryFn: async () => {
      const { data } = await api.get(adminEndpoints.capitalPlan)
      return data
    },
  })
}

export function useUpdateCapitalPlan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (updates: Partial<CapitalPlanResponse>) => {
      const { data } = await api.put(adminEndpoints.capitalPlan, updates)
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'capital-plan'] })
    },
  })
}

// ---------------------------------------------------------------------------
// Reload
// ---------------------------------------------------------------------------

export function useReloadConfigs() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { data } = await api.post(adminEndpoints.reload)
      return data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin'] })
    },
  })
}
