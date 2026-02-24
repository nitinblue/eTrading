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

export type AgentCategory = 'safety' | 'perception' | 'analysis' | 'execution' | 'learning' | 'domain'

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
  domain: {
    icon: Shield,
    label: 'Domain',
    color: 'text-blue-400',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/20',
    dot: 'bg-blue-400',
  },
}

// ---------------------------------------------------------------------------
// Per-agent icon mapping
// ---------------------------------------------------------------------------

export const AGENT_ICONS: Record<string, LucideIcon> = {
  sentinel: Siren,
  scout: FlaskConical,
  steward: Gauge,
  maverick: Scale,
  atlas: GitBranch,
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
    { agent: 'scout', label: 'Scout', section: 'Watchlist & Templates' },
  ],
  // Portfolio page
  'portfolio': [
    { agent: 'steward', label: 'Steward', section: 'Positions & Risk Factors' },
  ],
  // Trading Sheet
  'trading-sheet': [
    { agent: 'scout', label: 'Scout', section: 'Template Evaluation' },
    { agent: 'sentinel', label: 'Sentinel', section: 'Risk Factors & Fitness' },
    { agent: 'sentinel', label: 'Sentinel', section: 'WhatIf & Booking' },
  ],
  // Recommendations
  'recommendations': [
    { agent: 'scout', label: 'Scout', section: 'Recommendations' },
    { agent: 'sentinel', label: 'Sentinel', section: 'Approval Gate' },
  ],
  // Risk
  'risk': [
    { agent: 'sentinel', label: 'Sentinel', section: 'VaR & Greeks' },
    { agent: 'sentinel', label: 'Sentinel', section: 'Circuit Breakers' },
  ],
  // Workflow
  'workflow': [
    { agent: 'sentinel', label: 'Sentinel', section: 'Safety Gate' },
    { agent: 'maverick', label: 'Maverick', section: 'Daily Goals' },
  ],
  // Reports
  'reports': [
    { agent: 'atlas', label: 'Atlas', section: 'Reports' },
    { agent: 'maverick', label: 'Maverick', section: 'Decision Audit' },
  ],
  // Performance
  'performance': [
    { agent: 'atlas', label: 'Atlas', section: 'Performance Metrics' },
    { agent: 'maverick', label: 'Maverick', section: 'Win Rate & Expectancy' },
  ],
  // Capital
  'capital': [
    { agent: 'steward', label: 'Steward', section: 'Deployment & Idle' },
  ],
  // Dashboard
  'dashboard': [
    { agent: 'sentinel', label: 'Sentinel', section: 'Circuit Breakers' },
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
