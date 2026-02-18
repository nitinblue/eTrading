import { clsx } from 'clsx'
import { Badge } from '../common/Badge'
import { PnLDisplay } from '../common/PnLDisplay'
import { GreeksBar } from '../common/GreeksBar'
import type { Portfolio } from '../../api/types'

interface PortfolioCardProps {
  portfolio: Portfolio
  selected?: boolean
  onClick?: () => void
}

export function PortfolioCard({ portfolio, selected, onClick }: PortfolioCardProps) {
  const p = portfolio
  const currency = p.currency === 'INR' ? '\u20B9' : '$'

  return (
    <div
      className={clsx(
        'card cursor-pointer transition-colors',
        selected ? 'border-accent-blue bg-bg-tertiary' : 'hover:border-border-primary',
      )}
      onClick={onClick}
    >
      {/* Header */}
      <div className="card-header flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-text-primary">{p.name}</span>
          <Badge variant={p.portfolio_type}>{p.portfolio_type.toUpperCase()}</Badge>
        </div>
        {p.broker && (
          <span className="text-2xs text-text-muted">{p.broker}</span>
        )}
      </div>

      {/* Body */}
      <div className="card-body space-y-2">
        {/* Equity + P&L row */}
        <div className="flex justify-between items-baseline">
          <div>
            <div className="text-2xs text-text-muted">Equity</div>
            <div className="text-sm font-mono font-semibold text-text-primary">
              {currency}{p.total_equity.toLocaleString('en-US', { maximumFractionDigits: 0 })}
            </div>
          </div>
          <div className="text-right">
            <div className="text-2xs text-text-muted">Daily P&L</div>
            <PnLDisplay value={p.daily_pnl} size="sm" currency={currency} />
          </div>
          <div className="text-right">
            <div className="text-2xs text-text-muted">Total P&L</div>
            <PnLDisplay value={p.total_pnl} size="sm" currency={currency} />
          </div>
        </div>

        {/* Greeks bars */}
        <div className="space-y-1">
          <GreeksBar label="\u0394" value={p.portfolio_delta} limit={p.max_portfolio_delta} />
          <GreeksBar label="\u0398" value={p.portfolio_theta} limit={p.min_portfolio_theta} />
          <GreeksBar label="\u03BD" value={p.portfolio_vega} limit={p.max_portfolio_vega} />
        </div>

        {/* Footer stats */}
        <div className="flex justify-between text-2xs text-text-muted pt-1 border-t border-border-secondary">
          <span>{p.open_trade_count || 0} open</span>
          <span>{p.deployed_pct?.toFixed(0) || 0}% deployed</span>
          <span>VaR ${Math.abs(p.var_1d_95).toFixed(0)}</span>
        </div>
      </div>
    </div>
  )
}
