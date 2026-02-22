/**
 * Shared agent configuration: icons, colors, and page ownership.
 * Used across all pages to show which agent owns each section.
 */

import {
  Shield, Eye, BarChart3, Zap, GraduationCap,
  Siren,
  Gauge, GitBranch,
  Scale, FlaskConical,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

// ---------------------------------------------------------------------------
// Category config (colors + icons)
// ---------------------------------------------------------------------------

export type AgentCategory = 'safety' | 'perception' | 'analysis' | 'execution' | 'learning'

export interface CategoryConfig {
  icon: LucideIcon
  label: string
  color: string        // text color class
  bg: string           // background class
  border: string       // border class
  dot: string          // dot/accent color
}

export const CATEGORY_CONFIG: Record<AgentCategory, CategoryConfig> = {
  safety: {
    icon: Shield,
    label: 'Safety',
    color: 'text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/20',
    dot: 'bg-red-400',
  },
  perception: {
    icon: Eye,
    label: 'Perception',
    color: 'text-blue-400',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/20',
    dot: 'bg-blue-400',
  },
  analysis: {
    icon: BarChart3,
    label: 'Analysis',
    color: 'text-purple-400',
    bg: 'bg-purple-500/10',
    border: 'border-purple-500/20',
    dot: 'bg-purple-400',
  },
  execution: {
    icon: Zap,
    label: 'Execution',
    color: 'text-green-400',
    bg: 'bg-green-500/10',
    border: 'border-green-500/20',
    dot: 'bg-green-400',
  },
  learning: {
    icon: GraduationCap,
    label: 'Learning',
    color: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/20',
    dot: 'bg-amber-400',
  },
}

// ---------------------------------------------------------------------------
// Per-agent icon mapping
// ---------------------------------------------------------------------------

export const AGENT_ICONS: Record<string, LucideIcon> = {
  circuit_breaker: Siren,
  risk: Gauge,
  tech_architect: GitBranch,
  trade_discipline: Scale,
  quant_research: FlaskConical,
}

// ---------------------------------------------------------------------------
// Page-to-agent ownership mapping
// Shows which agent(s) own data on each page/section
// ---------------------------------------------------------------------------

export interface AgentOwnership {
  agent: string
  label: string
  section?: string  // optional sub-section
}

export const PAGE_OWNERSHIP: Record<string, AgentOwnership[]> = {
  // Research Dashboard
  'research': [
    { agent: 'quant_research', label: 'Quant Research', section: 'Watchlist & Templates' },
  ],
  // Portfolio page
  'portfolio': [
    { agent: 'risk', label: 'Risk', section: 'Positions & Risk Factors' },
  ],
  // Trading Sheet
  'trading-sheet': [
    { agent: 'quant_research', label: 'Quant Research', section: 'Template Evaluation' },
    { agent: 'risk', label: 'Risk', section: 'Risk Factors & Fitness' },
    { agent: 'risk', label: 'Risk', section: 'WhatIf & Booking' },
  ],
  // Recommendations
  'recommendations': [
    { agent: 'quant_research', label: 'Quant Research', section: 'Recommendations' },
    { agent: 'circuit_breaker', label: 'Circuit Breaker', section: 'Approval Gate' },
  ],
  // Risk
  'risk': [
    { agent: 'risk', label: 'Risk', section: 'VaR & Greeks' },
    { agent: 'circuit_breaker', label: 'Circuit Breaker', section: 'Circuit Breakers' },
  ],
  // Workflow
  'workflow': [
    { agent: 'circuit_breaker', label: 'Circuit Breaker', section: 'Safety Gate' },
    { agent: 'trade_discipline', label: 'Trade Discipline', section: 'Daily Goals' },
  ],
  // Reports
  'reports': [
    { agent: 'tech_architect', label: 'Tech Architect', section: 'Reports' },
    { agent: 'trade_discipline', label: 'Trade Discipline', section: 'Decision Audit' },
  ],
  // Performance
  'performance': [
    { agent: 'tech_architect', label: 'Tech Architect', section: 'Performance Metrics' },
    { agent: 'trade_discipline', label: 'Trade Discipline', section: 'Win Rate & Expectancy' },
  ],
  // Capital
  'capital': [
    { agent: 'risk', label: 'Risk', section: 'Deployment & Idle' },
  ],
  // Dashboard
  'dashboard': [
    { agent: 'circuit_breaker', label: 'Circuit Breaker', section: 'Circuit Breakers' },
  ],
}

// ---------------------------------------------------------------------------
// Helper: get agent icon + color for a given agent name
// ---------------------------------------------------------------------------

export function getAgentStyle(agentName: string, category?: AgentCategory) {
  const icon = AGENT_ICONS[agentName]
  const cat = category ? CATEGORY_CONFIG[category] : undefined
  return { icon, category: cat }
}
