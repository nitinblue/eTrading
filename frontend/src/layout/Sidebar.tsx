import { NavLink } from 'react-router-dom'
import { clsx } from 'clsx'
import {
  LayoutDashboard,
  Briefcase,
  ListChecks,
  Activity,
  BarChart3,
  ShieldAlert,
  DollarSign,
  Bot,
  Settings,
  Database,
  ArrowLeftRight,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { useState } from 'react'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard', phase: 2 },
  { to: '/portfolio', icon: Briefcase, label: 'Portfolio', phase: 1 },
  { to: '/recommendations', icon: ListChecks, label: 'Recommendations', phase: 2 },
  { to: '/workflow', icon: Activity, label: 'Workflow', phase: 3 },
  { to: '/risk', icon: ShieldAlert, label: 'Risk', phase: 2 },
  { to: '/performance', icon: BarChart3, label: 'Performance', phase: 3 },
  { to: '/capital', icon: DollarSign, label: 'Capital', phase: 2 },
  { to: '/agents', icon: Bot, label: 'Agents', phase: 3 },
  { to: '/config', icon: Settings, label: 'Config', phase: 3 },
  { to: '/data', icon: Database, label: 'Data Explorer', phase: 4 },
  { to: '/trading', icon: ArrowLeftRight, label: 'Trading', phase: 4 },
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
        {navItems.map(({ to, icon: Icon, label, phase }) => {
          const disabled = phase > 1 && to !== '/portfolio'
          return (
            <NavLink
              key={to}
              to={disabled ? '#' : to}
              onClick={(e) => disabled && e.preventDefault()}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2 mx-1 rounded text-xs transition-colors',
                  isActive && !disabled
                    ? 'bg-bg-active text-accent-blue'
                    : disabled
                      ? 'text-text-muted cursor-not-allowed opacity-40'
                      : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary',
                )
              }
            >
              <Icon size={16} className="shrink-0" />
              {!collapsed && <span className="truncate">{label}</span>}
            </NavLink>
          )
        })}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="h-8 flex items-center justify-center border-t border-border-secondary text-text-muted hover:text-text-primary"
      >
        {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
      </button>
    </aside>
  )
}
