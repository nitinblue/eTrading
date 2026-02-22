/**
 * AgentBadge — Small inline badge showing which agent owns a section.
 * Usage: <AgentBadge agent="risk" /> or <AgentBadge agent="circuit_breaker" />
 */

import { clsx } from 'clsx'
import { AGENT_ICONS, CATEGORY_CONFIG, type AgentCategory } from '../../config/agentConfig'

// Agent name → category lookup (duplicated from backend for offline use)
const AGENT_CATEGORY: Record<string, AgentCategory> = {
  circuit_breaker: 'safety',
  risk: 'analysis',
  quant_research: 'analysis',
  tech_architect: 'execution',
  trade_discipline: 'learning',
}

// Human-friendly display names
const AGENT_DISPLAY: Record<string, string> = {
  circuit_breaker: 'Circuit Breaker',
  risk: 'Risk',
  quant_research: 'Quant Research',
  tech_architect: 'Tech Architect',
  trade_discipline: 'Trade Discipline',
}

interface AgentBadgeProps {
  agent: string
  label?: string
  size?: 'xs' | 'sm'
  showLabel?: boolean
}

export function AgentBadge({ agent, label, size = 'xs', showLabel = true }: AgentBadgeProps) {
  const category = AGENT_CATEGORY[agent] || 'analysis'
  const cat = CATEGORY_CONFIG[category]
  const Icon = AGENT_ICONS[agent]
  const displayName = label || AGENT_DISPLAY[agent] || agent

  if (!Icon) return null

  const iconSize = size === 'xs' ? 10 : 12
  const textClass = size === 'xs' ? 'text-[9px]' : 'text-2xs'

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-0.5 px-1 py-0.5 rounded',
        cat.bg, cat.border, 'border',
      )}
      title={`Owned by ${displayName} agent`}
    >
      <Icon size={iconSize} className={cat.color} />
      {showLabel && <span className={clsx(textClass, cat.color, 'font-medium')}>{displayName}</span>}
    </span>
  )
}

/**
 * AgentOwnerStrip — Shows all agent owners for a page section.
 * Usage: <AgentOwnerStrip page="research" />
 */

import { PAGE_OWNERSHIP } from '../../config/agentConfig'

interface AgentOwnerStripProps {
  page: string
}

export function AgentOwnerStrip({ page }: AgentOwnerStripProps) {
  const owners = PAGE_OWNERSHIP[page]
  if (!owners || owners.length === 0) return null

  return (
    <div className="flex items-center gap-1.5">
      {owners.map((o) => (
        <AgentBadge key={o.agent} agent={o.agent} label={o.label} size="xs" />
      ))}
    </div>
  )
}
