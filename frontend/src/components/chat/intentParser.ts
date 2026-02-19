import { api } from '../../api/client'
import { endpoints, reportEndpoints } from '../../api/endpoints'

export interface ChatResponse {
  text: string
  data?: unknown
  action?: 'navigate' | 'none'
  navigateTo?: string
}

interface Intent {
  pattern: RegExp
  action: string
}

const intents: Intent[] = [
  // Agent queries
  { pattern: /(?:how|what).*agent.*(?:status|perform|doing|run)/i, action: 'agent_summary' },
  { pattern: /agent\s+(?:status|list|summary)/i, action: 'agent_summary' },
  { pattern: /(?:show|get|list)\s+agents/i, action: 'agent_summary' },

  // Portfolio queries
  { pattern: /(?:delta|gamma|theta|vega)\s*(?:exposure|risk)?/i, action: 'greeks_summary' },
  { pattern: /(?:my|portfolio)\s*(?:exposure|risk|greeks|summary)/i, action: 'greeks_summary' },
  { pattern: /(?:what|show).*(?:position|portfolio)/i, action: 'portfolio_summary' },

  // Capital queries
  { pattern: /(?:capital|idle|deployed|cash)/i, action: 'capital_summary' },
  { pattern: /(?:how much|what).*(?:idle|deployed|cash|capital)/i, action: 'capital_summary' },

  // Recommendation queries
  { pattern: /(?:pending|new)\s*(?:rec|recommendation)/i, action: 'pending_recs' },
  { pattern: /(?:show|list|get)\s*(?:rec|recommendation)/i, action: 'pending_recs' },
  { pattern: /(?:approve|reject)\s/i, action: 'rec_action_hint' },

  // Workflow control
  { pattern: /(?:halt|stop|pause)\s*(?:trading|workflow|engine)?/i, action: 'halt_hint' },
  { pattern: /(?:resume|start|continue)\s*(?:trading|workflow|engine)?/i, action: 'resume_hint' },
  { pattern: /(?:workflow|engine)\s*(?:status|state)/i, action: 'workflow_status' },

  // Performance
  { pattern: /(?:performance|win\s*rate|sharpe|pnl|p&l|profit)/i, action: 'performance_summary' },

  // Help
  { pattern: /(?:help|what can you do|commands)/i, action: 'help' },
]

export async function parseIntent(input: string): Promise<ChatResponse> {
  const trimmed = input.trim()
  if (!trimmed) return { text: 'Please type a message.' }

  for (const intent of intents) {
    if (intent.pattern.test(trimmed)) {
      return await executeIntent(intent.action)
    }
  }

  return {
    text: `I'm not sure how to help with that. Try asking about:\n- Agent status\n- Portfolio exposure / greeks\n- Capital deployment\n- Pending recommendations\n- Workflow status\n- Performance metrics\n\nOr type **help** for all available commands.`,
  }
}

async function executeIntent(action: string): Promise<ChatResponse> {
  try {
    switch (action) {
      case 'agent_summary':
        return await fetchAgentSummary()
      case 'greeks_summary':
        return await fetchGreeksSummary()
      case 'portfolio_summary':
        return await fetchPortfolioSummary()
      case 'capital_summary':
        return await fetchCapitalSummary()
      case 'pending_recs':
        return await fetchPendingRecs()
      case 'workflow_status':
        return await fetchWorkflowStatus()
      case 'performance_summary':
        return await fetchPerformanceSummary()
      case 'halt_hint':
        return {
          text: 'To halt the workflow, go to the **Workflow** page and click the HALT button. This requires confirmation.',
          action: 'navigate',
          navigateTo: '/workflow',
        }
      case 'resume_hint':
        return {
          text: 'To resume the workflow, go to the **Workflow** page and click RESUME. You\'ll need to provide a rationale.',
          action: 'navigate',
          navigateTo: '/workflow',
        }
      case 'rec_action_hint':
        return {
          text: 'To approve or reject recommendations, go to the **Recommendations** page and click on a recommendation to see action options.',
          action: 'navigate',
          navigateTo: '/recommendations',
        }
      case 'help':
        return {
          text: `**Available queries:**\n- "agent status" - Agent summary and recent runs\n- "delta exposure" / "my greeks" - Portfolio Greeks\n- "portfolio summary" - Portfolio overview\n- "capital" / "idle capital" - Capital deployment\n- "pending recs" - Pending recommendations\n- "workflow status" - Current engine state\n- "performance" / "win rate" - Performance metrics\n- "halt" / "resume" - Workflow control hints`,
        }
      default:
        return { text: 'Unknown action.' }
    }
  } catch (err) {
    return { text: `Error fetching data: ${err instanceof Error ? err.message : 'Unknown error'}. Is the backend running?` }
  }
}

async function fetchAgentSummary(): Promise<ChatResponse> {
  const { data } = await api.get(endpoints.agentsSummary)
  const s = data
  return {
    text: `**Agent Summary**\n- Total agents: ${s.total_agents}\n- Runs today: ${s.today_runs}\n- Errors today: ${s.today_errors}\n- Avg duration: ${s.avg_duration_ms?.toFixed(0) ?? 0}ms\n- Cycles: ${s.cycle_count}\n- Current state: ${s.current_state?.replace(/_/g, ' ').toUpperCase() ?? 'OFFLINE'}`,
    data: s,
  }
}

async function fetchGreeksSummary(): Promise<ChatResponse> {
  const { data } = await api.get(endpoints.portfolios)
  const portfolios = Array.isArray(data) ? data : []
  const real = portfolios.filter((p: { portfolio_type: string; name: string }) => p.portfolio_type === 'real' && !p.name.startsWith('research_'))

  const delta = real.reduce((s: number, p: { portfolio_delta: number }) => s + p.portfolio_delta, 0)
  const gamma = real.reduce((s: number, p: { portfolio_gamma: number }) => s + p.portfolio_gamma, 0)
  const theta = real.reduce((s: number, p: { portfolio_theta: number }) => s + p.portfolio_theta, 0)
  const vega = real.reduce((s: number, p: { portfolio_vega: number }) => s + p.portfolio_vega, 0)

  return {
    text: `**Greeks Exposure (Real Portfolios)**\n- Net Delta: ${delta >= 0 ? '+' : ''}${delta.toFixed(1)}\n- Net Gamma: ${gamma >= 0 ? '+' : ''}${gamma.toFixed(2)}\n- Net Theta: ${theta >= 0 ? '+' : ''}${theta.toFixed(1)}/day\n- Net Vega: ${vega >= 0 ? '+' : ''}${vega.toFixed(1)}`,
    action: 'navigate',
    navigateTo: '/risk',
  }
}

async function fetchPortfolioSummary(): Promise<ChatResponse> {
  const { data } = await api.get(endpoints.portfolios)
  const portfolios = Array.isArray(data) ? data : []
  const real = portfolios.filter((p: { portfolio_type: string; name: string }) => p.portfolio_type === 'real' && !p.name.startsWith('research_'))

  const totalEquity = real.reduce((s: number, p: { total_equity: number }) => s + p.total_equity, 0)
  const dailyPnl = real.reduce((s: number, p: { daily_pnl: number }) => s + p.daily_pnl, 0)
  const openTrades = real.reduce((s: number, p: { open_trade_count: number }) => s + p.open_trade_count, 0)

  const lines = real.map((p: { name: string; total_equity: number; open_trade_count: number; deployed_pct: number }) =>
    `  - **${p.name}**: $${p.total_equity.toLocaleString()} | ${p.open_trade_count} trades | ${p.deployed_pct.toFixed(0)}% deployed`
  )

  return {
    text: `**Portfolio Summary**\n- Total equity: $${totalEquity.toLocaleString()}\n- Daily P&L: ${dailyPnl >= 0 ? '+' : ''}$${Math.abs(dailyPnl).toFixed(2)}\n- Open trades: ${openTrades}\n\n${lines.join('\n')}`,
    action: 'navigate',
    navigateTo: '/portfolio',
  }
}

async function fetchCapitalSummary(): Promise<ChatResponse> {
  const { data } = await api.get(endpoints.capital)
  const items = Array.isArray(data) ? data : data?.portfolios ?? []

  const idle = items.reduce((s: number, c: { idle_capital: number }) => s + c.idle_capital, 0)
  const total = items.reduce((s: number, c: { total_equity: number }) => s + c.total_equity, 0)
  const deployed = total - idle

  return {
    text: `**Capital Deployment**\n- Total equity: $${total.toLocaleString()}\n- Deployed: $${deployed.toLocaleString()} (${total > 0 ? ((deployed / total) * 100).toFixed(1) : 0}%)\n- Idle: $${idle.toLocaleString()}`,
    action: 'navigate',
    navigateTo: '/capital',
  }
}

async function fetchPendingRecs(): Promise<ChatResponse> {
  const { data } = await api.get(endpoints.recommendations, { params: { status: 'pending' } })
  const recs = Array.isArray(data) ? data : data?.recommendations ?? []

  if (recs.length === 0) {
    return { text: 'No pending recommendations right now.' }
  }

  const lines = recs.slice(0, 5).map((r: { recommendation_type: string; underlying: string; strategy_type: string; confidence: number }) =>
    `  - **${r.recommendation_type.toUpperCase()}** ${r.underlying} ${r.strategy_type} (${(r.confidence * 100).toFixed(0)}% conf)`
  )

  return {
    text: `**${recs.length} Pending Recommendation${recs.length > 1 ? 's' : ''}**\n${lines.join('\n')}${recs.length > 5 ? `\n  ...and ${recs.length - 5} more` : ''}`,
    action: 'navigate',
    navigateTo: '/recommendations',
  }
}

async function fetchWorkflowStatus(): Promise<ChatResponse> {
  const { data } = await api.get(endpoints.workflowStatus)
  return {
    text: `**Workflow Status**\n- State: ${data.current_state?.replace(/_/g, ' ').toUpperCase() ?? 'OFFLINE'}\n- Cycle: #${data.cycle_count ?? 0}\n- Halted: ${data.halted ? 'YES' : 'NO'}${data.halt_reason ? ` (${data.halt_reason})` : ''}\n- Trades today: ${data.trades_today ?? 0}\n- Pending recs: ${data.pending_recommendations ?? 0}\n- VIX: ${data.vix?.toFixed(1) ?? '--'}`,
    action: 'navigate',
    navigateTo: '/workflow',
  }
}

async function fetchPerformanceSummary(): Promise<ChatResponse> {
  const { data } = await api.get(reportEndpoints.performance)
  const metrics = Array.isArray(data) ? data : []

  if (metrics.length === 0) {
    return { text: 'No performance data yet. Metrics will appear after trades are closed.' }
  }

  const total = metrics.reduce((s: number, m: { total_trades: number }) => s + m.total_trades, 0)
  const wins = metrics.reduce((s: number, m: { winning_trades: number }) => s + m.winning_trades, 0)
  const pnl = metrics.reduce((s: number, m: { total_pnl: number }) => s + m.total_pnl, 0)

  return {
    text: `**Performance Summary**\n- Total trades: ${total}\n- Win rate: ${total > 0 ? ((wins / total) * 100).toFixed(0) : 0}%\n- Total P&L: ${pnl >= 0 ? '+' : ''}$${Math.abs(pnl).toFixed(2)}`,
    action: 'navigate',
    navigateTo: '/performance',
  }
}
