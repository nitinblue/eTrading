import { X, ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react'
import { PnLDisplay } from '../common/PnLDisplay'
import { Badge } from '../common/Badge'
import type { Trade, Leg } from '../../api/types'

interface TradeDetailModalProps {
  trade: Trade
  onClose: () => void
}

export function TradeDetailModal({ trade, onClose }: TradeDetailModalProps) {
  const t = trade

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-bg-secondary border border-border-primary rounded-lg w-[700px] max-h-[85vh] overflow-y-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border-secondary">
          <div className="flex items-center gap-3">
            <span className="text-sm font-bold text-text-primary">{t.underlying_symbol}</span>
            <span className="text-xs text-text-muted">{t.strategy_type?.replace(/_/g, ' ')}</span>
            <Badge variant={t.trade_status}>{t.trade_status.toUpperCase()}</Badge>
            {t.trade_type === 'what_if' && <Badge variant="what_if">WHATIF</Badge>}
          </div>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary">
            <X size={18} />
          </button>
        </div>

        {/* P&L Summary */}
        <div className="px-4 py-3 border-b border-border-secondary">
          <div className="grid grid-cols-5 gap-4">
            <MetricCell label="Total P&L" value={<PnLDisplay value={t.total_pnl} size="md" />} />
            <MetricCell label="Entry" value={`$${t.entry_price?.toFixed(2) || '--'}`} />
            <MetricCell label="Current" value={`$${t.current_price?.toFixed(2) || '--'}`} />
            <MetricCell label="DTE" value={t.dte != null ? `${t.dte}d` : '--'} />
            <MetricCell label="Source" value={t.trade_source?.replace('screener_', '') || '--'} />
          </div>
        </div>

        {/* P&L Attribution */}
        <div className="px-4 py-3 border-b border-border-secondary">
          <h3 className="text-2xs text-text-muted font-semibold uppercase mb-2">P&L Attribution</h3>
          <div className="grid grid-cols-6 gap-3">
            <PnLAttrCell label="Delta" value={t.delta_pnl} />
            <PnLAttrCell label="Gamma" value={t.gamma_pnl} />
            <PnLAttrCell label="Theta" value={t.theta_pnl} />
            <PnLAttrCell label="Vega" value={t.vega_pnl} />
            <PnLAttrCell label="Other" value={t.unexplained_pnl} />
            <PnLAttrCell label="Total" value={t.total_pnl} bold />
          </div>
        </div>

        {/* Greeks */}
        <div className="px-4 py-3 border-b border-border-secondary">
          <h3 className="text-2xs text-text-muted font-semibold uppercase mb-2">Greeks (Entry → Current)</h3>
          <div className="grid grid-cols-4 gap-3">
            <GreekChangeCell label="Delta" entry={t.entry_delta} current={t.current_delta} />
            <GreekChangeCell label="Gamma" entry={t.entry_gamma} current={t.current_gamma} />
            <GreekChangeCell label="Theta" entry={t.entry_theta} current={t.current_theta} />
            <GreekChangeCell label="Vega" entry={t.entry_vega} current={t.current_vega} />
          </div>
        </div>

        {/* Legs table */}
        <div className="px-4 py-3 border-b border-border-secondary">
          <h3 className="text-2xs text-text-muted font-semibold uppercase mb-2">
            Legs ({t.legs?.length || 0})
          </h3>
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="text-text-muted text-left border-b border-border-secondary">
                <th className="py-1 pr-2">Symbol</th>
                <th className="py-1 pr-2">Type</th>
                <th className="py-1 pr-2">Strike</th>
                <th className="py-1 pr-2">Exp</th>
                <th className="py-1 pr-2">Qty</th>
                <th className="py-1 pr-2">Side</th>
                <th className="py-1 pr-2 text-right">Entry</th>
                <th className="py-1 pr-2 text-right">Current</th>
                <th className="py-1 text-right">\u0394</th>
              </tr>
            </thead>
            <tbody>
              {(t.legs || []).map((leg) => (
                <LegRow key={leg.id} leg={leg} />
              ))}
            </tbody>
          </table>
        </div>

        {/* Timeline */}
        <div className="px-4 py-3">
          <h3 className="text-2xs text-text-muted font-semibold uppercase mb-2">Timeline</h3>
          <div className="space-y-1 text-xs text-text-secondary">
            {t.created_at && <TimelineItem label="Created" time={t.created_at} />}
            {t.opened_at && <TimelineItem label="Opened" time={t.opened_at} />}
            {t.closed_at && <TimelineItem label="Closed" time={t.closed_at} />}
            {t.rolled_from_id && (
              <div className="text-accent-cyan">Rolled from {t.rolled_from_id.slice(0, 8)}...</div>
            )}
            {t.rolled_to_id && (
              <div className="text-accent-cyan">Rolled to {t.rolled_to_id.slice(0, 8)}...</div>
            )}
          </div>
          {t.notes && (
            <div className="mt-2 p-2 bg-bg-tertiary rounded text-xs text-text-secondary">
              {t.notes}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function MetricCell({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="text-2xs text-text-muted">{label}</div>
      <div className="text-xs font-mono text-text-primary">{value}</div>
    </div>
  )
}

function PnLAttrCell({ label, value, bold }: { label: string; value: number; bold?: boolean }) {
  return (
    <div className={bold ? 'border-l border-border-primary pl-2' : ''}>
      <div className="text-2xs text-text-muted">{label}</div>
      <PnLDisplay value={value} size="sm" className={bold ? 'font-bold' : ''} />
    </div>
  )
}

function GreekChangeCell({ label, entry, current }: { label: string; entry: number; current: number }) {
  const diff = current - entry
  const Icon = diff > 0.01 ? ArrowUpRight : diff < -0.01 ? ArrowDownRight : Minus
  const color = Math.abs(diff) < 0.01 ? 'text-text-muted' : diff > 0 ? 'text-accent-green' : 'text-accent-red'

  return (
    <div>
      <div className="text-2xs text-text-muted">{label}</div>
      <div className="flex items-center gap-1">
        <span className="text-xs font-mono text-text-secondary">{entry.toFixed(2)}</span>
        <span className="text-text-muted">→</span>
        <span className={`text-xs font-mono ${color}`}>{current.toFixed(2)}</span>
        <Icon size={10} className={color} />
      </div>
    </div>
  )
}

function LegRow({ leg }: { leg: Leg }) {
  const exp = leg.expiration ? new Date(leg.expiration).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' }) : '--'
  return (
    <tr className="border-b border-border-secondary/50 hover:bg-bg-hover">
      <td className="py-1 pr-2 text-text-primary">{leg.symbol_ticker}</td>
      <td className="py-1 pr-2 text-text-muted">{leg.option_type || leg.asset_type}</td>
      <td className="py-1 pr-2">{leg.strike ? `$${leg.strike}` : '--'}</td>
      <td className="py-1 pr-2 text-text-muted">{exp}</td>
      <td className="py-1 pr-2">{leg.quantity > 0 ? `+${leg.quantity}` : leg.quantity}</td>
      <td className="py-1 pr-2 text-text-muted">{leg.side}</td>
      <td className="py-1 pr-2 text-right">{leg.entry_price ? `$${leg.entry_price.toFixed(2)}` : '--'}</td>
      <td className="py-1 pr-2 text-right">{leg.current_price ? `$${leg.current_price.toFixed(2)}` : '--'}</td>
      <td className="py-1 text-right text-text-secondary">{leg.delta?.toFixed(2) || '--'}</td>
    </tr>
  )
}

function TimelineItem({ label, time }: { label: string; time: string }) {
  const d = new Date(time)
  return (
    <div className="flex items-center gap-2">
      <div className="w-1.5 h-1.5 rounded-full bg-accent-blue" />
      <span className="text-text-muted w-16">{label}</span>
      <span>{d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} {d.toLocaleTimeString('en-US', { hour12: false })}</span>
    </div>
  )
}
