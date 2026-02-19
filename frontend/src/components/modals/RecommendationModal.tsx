import { useState } from 'react'
import { X, Check, XCircle, Clock } from 'lucide-react'
import { clsx } from 'clsx'
import type { Recommendation } from '../../api/types'

interface RecommendationModalProps {
  rec: Recommendation
  onApprove: (portfolio: string, notes: string) => void
  onReject: (reason: string) => void
  onDefer: () => void
  onClose: () => void
  isLoading?: boolean
}

export function RecommendationModal({
  rec,
  onApprove,
  onReject,
  onDefer,
  onClose,
  isLoading,
}: RecommendationModalProps) {
  const [mode, setMode] = useState<'view' | 'approve' | 'reject'>('view')
  const [portfolio, setPortfolio] = useState(rec.suggested_portfolio || '')
  const [notes, setNotes] = useState('')
  const [reason, setReason] = useState('')

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="bg-bg-primary border border-border-primary rounded-lg shadow-xl w-full max-w-xl max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border-secondary">
          <div className="flex items-center gap-2">
            <span className={clsx(
              'px-2 py-0.5 rounded text-2xs font-semibold border',
              rec.recommendation_type === 'entry' ? 'bg-green-900/30 text-green-400 border-green-800' :
              rec.recommendation_type === 'exit' ? 'bg-red-900/30 text-red-400 border-red-800' :
              rec.recommendation_type === 'roll' ? 'bg-cyan-900/30 text-cyan-400 border-cyan-800' :
              'bg-purple-900/30 text-purple-400 border-purple-800',
            )}>
              {rec.recommendation_type.toUpperCase()}
            </span>
            <span className="text-sm font-semibold text-text-primary">{rec.underlying}</span>
            <span className="text-xs text-text-muted">{rec.strategy_type}</span>
          </div>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary">
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="p-4 space-y-4">
          {/* Metrics row */}
          <div className="grid grid-cols-4 gap-3">
            <MetricCard label="Confidence" value={`${(rec.confidence * 100).toFixed(0)}%`} />
            <MetricCard label="Risk" value={rec.risk_category} />
            <MetricCard label="Max Loss" value={rec.max_loss_display || '--'} />
            <MetricCard label="Max Profit" value={rec.max_profit_display || '--'} />
          </div>

          {/* Rationale */}
          {rec.rationale && (
            <div>
              <div className="text-2xs text-text-muted uppercase mb-1">Rationale</div>
              <p className="text-xs text-text-secondary bg-bg-secondary rounded p-2">{rec.rationale}</p>
            </div>
          )}

          {/* Legs */}
          {rec.legs && rec.legs.length > 0 && (
            <div>
              <div className="text-2xs text-text-muted uppercase mb-1">Legs</div>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-text-muted text-left border-b border-border-secondary">
                    <th className="py-1 pr-2">Side</th>
                    <th className="py-1 pr-2">Symbol</th>
                    <th className="py-1 pr-2">Type</th>
                    <th className="py-1 pr-2 text-right">Strike</th>
                    <th className="py-1 pr-2">Expiration</th>
                    <th className="py-1 text-right">Qty</th>
                  </tr>
                </thead>
                <tbody>
                  {rec.legs.map((leg, i) => (
                    <tr key={i} className="text-text-secondary border-b border-border-secondary/50">
                      <td className={clsx('py-1 pr-2 font-semibold', leg.side === 'BUY' ? 'text-pnl-profit' : 'text-pnl-loss')}>
                        {leg.side}
                      </td>
                      <td className="py-1 pr-2 font-mono">{leg.symbol}</td>
                      <td className="py-1 pr-2">{leg.option_type}</td>
                      <td className="py-1 pr-2 text-right font-mono">${leg.strike}</td>
                      <td className="py-1 pr-2">{leg.expiration}</td>
                      <td className="py-1 text-right font-mono">{leg.quantity}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Source + timing */}
          <div className="flex items-center gap-4 text-2xs text-text-muted">
            <span>Source: <span className="text-text-secondary">{rec.source}</span></span>
            {rec.screener_name && <span>Screener: <span className="text-text-secondary">{rec.screener_name}</span></span>}
            <span>Created: <span className="text-text-secondary">{new Date(rec.created_at).toLocaleString()}</span></span>
          </div>
        </div>

        {/* Actions */}
        <div className="px-4 py-3 border-t border-border-secondary">
          {mode === 'view' && rec.status === 'pending' && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setMode('approve')}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-green-900/40 text-green-400 border border-green-800 hover:bg-green-900/60"
              >
                <Check size={14} /> Approve
              </button>
              <button
                onClick={() => setMode('reject')}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-red-900/40 text-red-400 border border-red-800 hover:bg-red-900/60"
              >
                <XCircle size={14} /> Reject
              </button>
              <button
                onClick={onDefer}
                disabled={isLoading}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-bg-tertiary text-text-secondary border border-border-primary hover:bg-bg-hover"
              >
                <Clock size={14} /> Defer
              </button>
            </div>
          )}

          {mode === 'approve' && (
            <div className="space-y-2">
              <div>
                <label className="text-2xs text-text-muted block mb-1">Portfolio</label>
                <input
                  type="text"
                  value={portfolio}
                  onChange={(e) => setPortfolio(e.target.value)}
                  placeholder="Portfolio name"
                  className="w-full px-2 py-1.5 rounded text-xs bg-bg-secondary border border-border-primary text-text-primary focus:border-accent-blue focus:outline-none"
                />
              </div>
              <div>
                <label className="text-2xs text-text-muted block mb-1">Notes (optional)</label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={2}
                  className="w-full px-2 py-1.5 rounded text-xs bg-bg-secondary border border-border-primary text-text-primary focus:border-accent-blue focus:outline-none resize-none"
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => onApprove(portfolio, notes)}
                  disabled={isLoading || !portfolio}
                  className="px-3 py-1.5 rounded text-xs font-medium bg-green-700 text-white hover:bg-green-600 disabled:opacity-40"
                >
                  {isLoading ? 'Approving...' : 'Confirm Approve'}
                </button>
                <button
                  onClick={() => setMode('view')}
                  className="px-3 py-1.5 rounded text-xs text-text-muted hover:text-text-primary"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {mode === 'reject' && (
            <div className="space-y-2">
              <div>
                <label className="text-2xs text-text-muted block mb-1">Reason</label>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  rows={2}
                  placeholder="Why are you rejecting this?"
                  className="w-full px-2 py-1.5 rounded text-xs bg-bg-secondary border border-border-primary text-text-primary focus:border-accent-blue focus:outline-none resize-none"
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => onReject(reason)}
                  disabled={isLoading}
                  className="px-3 py-1.5 rounded text-xs font-medium bg-red-700 text-white hover:bg-red-600 disabled:opacity-40"
                >
                  {isLoading ? 'Rejecting...' : 'Confirm Reject'}
                </button>
                <button
                  onClick={() => setMode('view')}
                  className="px-3 py-1.5 rounded text-xs text-text-muted hover:text-text-primary"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {rec.status !== 'pending' && (
            <div className="text-xs text-text-muted">
              Status: <span className="font-semibold text-text-secondary">{rec.status.toUpperCase()}</span>
              {rec.reviewed_at && <> at {new Date(rec.reviewed_at).toLocaleString()}</>}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-bg-secondary rounded p-2">
      <div className="text-2xs text-text-muted uppercase">{label}</div>
      <div className="text-sm font-mono font-semibold text-text-primary">{value}</div>
    </div>
  )
}
