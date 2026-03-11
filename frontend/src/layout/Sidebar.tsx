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
} from 'lucide-react'
import { useState } from 'react'

interface NavItem {
  to: string
  icon: React.ElementType
  label: string
}

const navItems: NavItem[] = [
  { to: '/', icon: TrendingUp, label: 'Research' },
  { to: '/trading', icon: Terminal, label: 'Trading' },
  { to: '/portfolio', icon: Briefcase, label: 'Portfolio' },
  { to: '/risk', icon: ShieldAlert, label: 'Risk' },
  { to: '/agents', icon: Bot, label: 'Agents' },
  { to: '/reports', icon: FileText, label: 'Reports' },
  { to: '/data', icon: Database, label: 'Data Explorer' },
  { to: '/settings', icon: Settings, label: 'Config' },
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
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2 mx-1 rounded text-xs transition-colors',
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
      >
        {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
      </button>
    </aside>
  )
}
