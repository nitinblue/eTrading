import { useQueries } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'

// Strategy definitions with their endpoint functions
const STRATEGIES = [
  { key: 'iron_condor', label: 'Iron Condor', endpoint: endpoints.opportunityIronCondor },
  { key: 'iron_butterfly', label: 'Iron Butterfly', endpoint: endpoints.opportunityIronButterfly },
  { key: 'calendar', label: 'Calendar', endpoint: endpoints.opportunityCalendar },
  { key: 'diagonal', label: 'Diagonal', endpoint: endpoints.opportunityDiagonal },
  { key: 'zero_dte', label: '0DTE', endpoint: endpoints.opportunityZeroDte },
  { key: 'breakout', label: 'Breakout', endpoint: endpoints.opportunityBreakout },
  { key: 'momentum', label: 'Momentum', endpoint: endpoints.opportunityMomentum },
  { key: 'mean_reversion', label: 'Mean Reversion', endpoint: endpoints.opportunityMeanReversion },
  { key: 'leap', label: 'LEAP', endpoint: endpoints.opportunityLeap },
] as const

export type StrategyKey = typeof STRATEGIES[number]['key']

export interface StrategyResult {
  ticker: string
  strategy: StrategyKey
  label: string
  verdict: string | null
  confidence: number | null
  direction: string | null
  summary: string | null
  strategy_name: string | null
  trade_spec: any | null
  loading: boolean
  error: boolean
}

export { STRATEGIES }

/**
 * Fetch all 9 strategy assessments for a single ticker.
 * Returns results progressively as each completes.
 */
export function useTickerStrategies(ticker: string | null) {
  const queries = useQueries({
    queries: STRATEGIES.map(s => ({
      queryKey: ['strategy', ticker, s.key],
      queryFn: async () => {
        if (!ticker) return null
        const { data } = await api.get(s.endpoint(ticker), { timeout: 30_000 })
        return data
      },
      enabled: !!ticker,
      staleTime: 600_000,
      retry: false,
    })),
  })

  const results: StrategyResult[] = STRATEGIES.map((s, i) => {
    const q = queries[i]
    const d = q.data
    return {
      ticker: ticker || '',
      strategy: s.key,
      label: s.label,
      verdict: d?.verdict ?? null,
      confidence: d?.confidence ?? null,
      direction: d?.direction ?? d?.trend_direction ?? null,
      summary: d?.summary ?? null,
      strategy_name: d?.strategy?.name ?? d?.strategy ?? null,
      trade_spec: d?.trade_spec ?? null,
      loading: q.isLoading,
      error: q.isError,
    }
  })

  return {
    results,
    completedCount: queries.filter(q => q.isSuccess || q.isError).length,
    totalCount: STRATEGIES.length,
    isAllDone: queries.every(q => !q.isLoading),
  }
}
