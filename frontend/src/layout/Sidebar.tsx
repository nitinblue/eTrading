import { NavLink } from 'react-router-dom'
import { clsx } from 'clsx'
import {
  Briefcase,
  ShieldAlert,
  Bot,
  Settings,
  Database,
  FileText,
  TrendingUp,
  Terminal,
  ChevronLeft,
  ChevronRight,
  LayoutDashboard,
  Target,
  BookOpen,
  HelpCircle,
} from 'lucide-react'
import { useState } from 'react'

interface NavItem {
  to: string
  icon: React.ElementType
  label: string
  description: string
}

const navItems: NavItem[] = [
  { to: '/', icon: LayoutDashboard, label: 'Overview', description: 'System overview — philosophy, pipeline, capabilities' },
  { to: '/desks', icon: Target, label: 'Desks', description: 'Trading desks — P&L, health, scan/deploy/mark actions' },
  { to: '/journey', icon: BookOpen, label: 'Trade Journey', description: 'Anatomy of a trade — 15 steps from scan to learn' },
  { to: '/research', icon: TrendingUp, label: 'Research', description: 'Market research — regime, technicals, opportunities' },
  { to: '/trading', icon: Terminal, label: 'Trading', description: 'Trading terminal — blotter, positions, Greeks' },
  { to: '/portfolio', icon: Briefcase, label: 'Portfolio', description: 'Portfolio — positions, performance, capital' },
  { to: '/risk', icon: ShieldAlert, label: 'Risk', description: 'Risk dashboard — VaR, concentration, circuit breakers' },
  { to: '/agents', icon: Bot, label: 'Agents', description: 'Agent monitor — Chanakya, Arjuna, Bhishma, Kubera, Vishwakarma' },
  { to: '/reports', icon: FileText, label: 'Reports', description: 'Reports — daily P&L, performance, trade journal' },
  { to: '/data', icon: Database, label: 'Data Explorer', description: 'Data explorer — raw DB tables, queries' },
  { to: '/settings', icon: Settings, label: 'Config', description: 'Configuration — desks, risk limits, strategies' },
  { to: '/manual', icon: HelpCircle, label: 'Manual', description: 'User manual — complete guide to CoTrader' },
]

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(true)

  return (
    <aside
      className={clsx(
        'flex flex-col h-full bg-bg-primary border-r border-border-primary transition-all duration-200',
        collapsed ? 'w-[52px]' : 'w-[200px]',
      )}
    >
      {/* Logo */}
      <div className="h-12 flex items-center justify-center border-b border-border-secondary">
        <span className="text-accent-blue font-bold text-sm">
          {collapsed ? 'CT' : 'CoTrader'}
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-2 overflow-y-auto">
        {navItems.map(({ to, icon: Icon, label, description }) => (
          <NavLink
            key={to}
            to={to}
            title={description}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2 mx-1 rounded text-xs transition-colors group relative',
                isActive
                  ? 'bg-bg-active text-accent-blue'
                  : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary',
              )
            }
          >
            <Icon size={16} className="shrink-0" />
            {!collapsed && <span className="truncate">{label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="h-8 flex items-center justify-center border-t border-border-secondary text-text-muted hover:text-text-primary"
        title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
      </button>
    </aside>
  )
}
