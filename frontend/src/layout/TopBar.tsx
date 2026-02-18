import { Activity, AlertTriangle, TrendingUp } from 'lucide-react'
import { useWorkflowStatus } from '../hooks/useWorkflowStatus'

const stateColors: Record<string, string> = {
  idle: 'text-text-muted',
  boot: 'text-accent-yellow',
  macro_check: 'text-accent-cyan',
  screening: 'text-accent-blue',
  recommendation_review: 'text-accent-orange',
  execution: 'text-accent-green',
  monitoring: 'text-accent-blue',
  trade_management: 'text-accent-purple',
  trade_review: 'text-accent-orange',
  reporting: 'text-accent-cyan',
}

export function TopBar() {
  const { data: status } = useWorkflowStatus()

  const stateLabel = status?.current_state?.replace(/_/g, ' ').toUpperCase() || 'OFFLINE'
  const stateColor = stateColors[status?.current_state || ''] || 'text-text-muted'

  return (
    <header className="h-10 bg-bg-primary border-b border-border-primary flex items-center justify-between px-4">
      {/* Left: workflow state */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Activity size={14} className={stateColor} />
          <span className={`text-xs font-mono font-semibold ${stateColor}`}>
            {stateLabel}
          </span>
        </div>

        {status?.cycle_count != null && (
          <span className="text-2xs text-text-muted font-mono">
            Cycle #{status.cycle_count}
          </span>
        )}

        {status?.halted && (
          <div className="flex items-center gap-1 text-accent-red">
            <AlertTriangle size={12} />
            <span className="text-2xs font-semibold">HALTED</span>
          </div>
        )}
      </div>

      {/* Right: market info */}
      <div className="flex items-center gap-4">
        {status?.vix != null && (
          <div className="flex items-center gap-1">
            <TrendingUp size={12} className="text-text-muted" />
            <span className="text-2xs text-text-muted">VIX</span>
            <span className={`text-xs font-mono font-semibold ${
              status.vix > 30 ? 'text-accent-red' :
              status.vix > 20 ? 'text-accent-yellow' : 'text-accent-green'
            }`}>
              {status.vix.toFixed(1)}
            </span>
          </div>
        )}

        {status?.macro_regime && (
          <span className={`text-2xs font-mono px-1.5 py-0.5 rounded ${
            status.macro_regime === 'risk_off' ? 'bg-red-900/30 text-accent-red' :
            status.macro_regime === 'uncertain' ? 'bg-yellow-900/30 text-accent-yellow' :
            'bg-green-900/30 text-accent-green'
          }`}>
            {status.macro_regime.toUpperCase()}
          </span>
        )}

        <span className="text-2xs text-text-muted font-mono">
          {new Date().toLocaleTimeString('en-US', { hour12: false })}
        </span>
      </div>
    </header>
  )
}
