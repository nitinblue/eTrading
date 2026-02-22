import { useState, useMemo } from 'react'
import { usePortfolios } from '../hooks/usePortfolios'
import { useBrokerPositions } from '../hooks/useBrokerPositions'
import { useRiskFactors } from '../hooks/useRisk'
import { useLiveOrders } from '../hooks/useLiveOrders'
import { PortfolioGrid } from '../components/grids/PortfolioGrid'
import { BrokerPositionGrid } from '../components/grids/BrokerPositionGrid'
import { PortfolioCard } from '../components/cards/PortfolioCard'
import { PnLDisplay } from '../components/common/PnLDisplay'
import { GreeksBar } from '../components/common/GreeksBar'
import { AgentBadge } from '../components/common/AgentBadge'
import { Spinner } from '../components/common/Spinner'
import { EmptyState } from '../components/common/EmptyState'
import { clsx } from 'clsx'

type ViewMode = 'real' | 'whatif' | 'all'

export function PortfolioPage() {
  const { data: portfolios, isLoading: loadingPortfolios } = usePortfolios()
  const [selectedPortfolio, setSelectedPortfolio] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('real')

  const { data: brokerPositions, isLoading: loadingBrokerPositions } = useBrokerPositions(
    selectedPortfolio || undefined,
  )
  const { data: riskFactors } = useRiskFactors(selectedPortfolio || undefined)
  const { data: liveOrders } = useLiveOrders()

  const filteredPortfolios = useMemo(() => {
    if (!portfolios) return []
    // Exclude research + fund/stallion portfolios (funds have their own page)
    const base = portfolios.filter((p) => !p.name.startsWith('research_') && p.broker !== 'stallion')
    if (viewMode === 'real') return base.filter((p) => p.portfolio_type === 'real')
    if (viewMode === 'whatif') return base.filter((p) => p.portfolio_type === 'what_if')
    return base
  }, [portfolios, viewMode])

  const selected = useMemo(
    () => portfolios?.find((p) => p.name === selectedPortfolio),
    [portfolios, selectedPortfolio],
  )

  // Aggregate totals — real USD portfolios only (exclude funds/stallion which are INR)
  const totals = useMemo(() => {
    if (!portfolios) return null
    const real = portfolios.filter((p) => p.portfolio_type === 'real' && p.broker !== 'stallion')
    return {
      equity: real.reduce((sum, p) => sum + p.total_equity, 0),
      dailyPnl: real.reduce((sum, p) => sum + p.daily_pnl, 0),
      totalPnl: real.reduce((sum, p) => sum + p.total_pnl, 0),
      delta: real.reduce((sum, p) => sum + p.portfolio_delta, 0),
      theta: real.reduce((sum, p) => sum + p.portfolio_theta, 0),
      openTrades: real.reduce((sum, p) => sum + (p.open_trade_count || 0), 0),
    }
  }, [portfolios])

  if (loadingPortfolios) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Agent ownership */}
      <div className="flex items-center gap-1.5">
        <AgentBadge agent="risk" />
      </div>
      {/* Summary header */}
      {totals && (
        <div className="card">
          <div className="card-body">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-6">
                <div>
                  <div className="text-2xs text-text-muted uppercase">Total Equity (Real)</div>
                  <div className="text-lg font-mono font-bold text-text-primary">
                    ${totals.equity.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                  </div>
                </div>
                <div>
                  <div className="text-2xs text-text-muted uppercase">Daily P&L</div>
                  <PnLDisplay value={totals.dailyPnl} size="md" />
                </div>
                <div>
                  <div className="text-2xs text-text-muted uppercase">Total P&L</div>
                  <PnLDisplay value={totals.totalPnl} size="md" />
                </div>
                <div>
                  <div className="text-2xs text-text-muted uppercase">Net Delta</div>
                  <span className="text-sm font-mono text-text-primary">
                    {totals.delta >= 0 ? '+' : ''}{totals.delta.toFixed(1)}
                  </span>
                </div>
                <div>
                  <div className="text-2xs text-text-muted uppercase">Net Theta</div>
                  <span className="text-sm font-mono text-accent-green">
                    {totals.theta >= 0 ? '+' : ''}{totals.theta.toFixed(1)}/day
                  </span>
                </div>
                <div>
                  <div className="text-2xs text-text-muted uppercase">Open Trades</div>
                  <span className="text-sm font-mono text-text-primary">{totals.openTrades}</span>
                </div>
              </div>

              {/* View mode toggle */}
              <div className="flex items-center gap-1 bg-bg-tertiary rounded p-0.5">
                {(['real', 'whatif', 'all'] as ViewMode[]).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => setViewMode(mode)}
                    className={clsx(
                      'px-2 py-1 rounded text-2xs font-semibold transition-colors',
                      viewMode === mode
                        ? 'bg-bg-active text-text-primary'
                        : 'text-text-muted hover:text-text-secondary',
                    )}
                  >
                    {mode === 'whatif' ? 'WhatIf' : mode.charAt(0).toUpperCase() + mode.slice(1)}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Portfolio grid */}
      <div className="card">
        <div className="card-header flex items-center justify-between">
          <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
            Portfolios ({filteredPortfolios.length})
          </h2>
          {selectedPortfolio && (
            <button
              onClick={() => setSelectedPortfolio(null)}
              className="text-2xs text-accent-blue hover:underline"
            >
              Show all positions
            </button>
          )}
        </div>
        <PortfolioGrid
          portfolios={filteredPortfolios}
          onPortfolioClick={setSelectedPortfolio}
        />
      </div>

      {/* Selected portfolio detail */}
      {selected && (
        <div className="card">
          <div className="card-header flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h2 className="text-xs font-semibold text-text-primary">
                {selected.name}
              </h2>
              <span className="text-2xs text-text-muted">{selected.broker}</span>
            </div>
            <PnLDisplay value={selected.total_pnl} size="sm" />
          </div>
          <div className="card-body">
            <div className="grid grid-cols-4 gap-2 mb-3">
              <GreeksBar label="Delta" value={selected.portfolio_delta} limit={selected.max_portfolio_delta} />
              <GreeksBar label="Gamma" value={selected.portfolio_gamma} limit={selected.max_portfolio_gamma} />
              <GreeksBar label="Theta" value={selected.portfolio_theta} limit={selected.min_portfolio_theta} />
              <GreeksBar label="Vega" value={selected.portfolio_vega} limit={selected.max_portfolio_vega} />
            </div>
          </div>
        </div>
      )}

      {/* Broker Positions (synced from TastyTrade/broker) — shown first since these are the real positions */}
      <div className="card">
        <div className="card-header">
          <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
            Live Positions
            {brokerPositions && ` (${brokerPositions.length})`}
          </h2>
        </div>
        {loadingBrokerPositions ? (
          <div className="card-body flex justify-center py-8">
            <Spinner />
          </div>
        ) : brokerPositions && brokerPositions.length > 0 ? (
          <BrokerPositionGrid positions={brokerPositions} />
        ) : (
          <EmptyState message="No broker positions synced" />
        )}
      </div>

      {/* Risk Factors — per-underlying Greeks aggregation */}
      {riskFactors && riskFactors.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
              Risk Factors ({riskFactors.length})
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="border-b border-border-primary text-text-muted text-left">
                  <th className="px-3 py-2">Account</th>
                  <th className="px-3 py-2">Underlying</th>
                  <th className="px-3 py-2 text-right">Spot</th>
                  <th className="px-3 py-2 text-right">Delta</th>
                  <th className="px-3 py-2 text-right">Gamma</th>
                  <th className="px-3 py-2 text-right">Theta</th>
                  <th className="px-3 py-2 text-right">Vega</th>
                  <th className="px-3 py-2 text-right">Delta $</th>
                  <th className="px-3 py-2 text-right">Gamma $</th>
                  <th className="px-3 py-2 text-right">P&L</th>
                  <th className="px-3 py-2 text-right">Positions</th>
                </tr>
              </thead>
              <tbody>
                {riskFactors.map((rf) => (
                  <tr key={`${rf.account}-${rf.underlying}`} className="border-b border-border-primary hover:bg-bg-secondary">
                    <td className="px-3 py-2 text-text-muted">{rf.account ?? '-'}</td>
                    <td className="px-3 py-2 font-semibold text-text-primary">{rf.underlying}</td>
                    <td className="px-3 py-2 text-right">{rf.spot?.toFixed(2) ?? '-'}</td>
                    <td className="px-3 py-2 text-right">{rf.delta?.toFixed(2) ?? '-'}</td>
                    <td className="px-3 py-2 text-right">{rf.gamma?.toFixed(4) ?? '-'}</td>
                    <td className="px-3 py-2 text-right">{rf.theta?.toFixed(2) ?? '-'}</td>
                    <td className="px-3 py-2 text-right">{rf.vega?.toFixed(2) ?? '-'}</td>
                    <td className="px-3 py-2 text-right">{rf['delta_$']?.toLocaleString('en-US', { maximumFractionDigits: 0 }) ?? '-'}</td>
                    <td className="px-3 py-2 text-right">{rf['gamma_$']?.toLocaleString('en-US', { maximumFractionDigits: 0 }) ?? '-'}</td>
                    <td className={`px-3 py-2 text-right ${(rf.pnl ?? 0) > 0 ? 'text-pnl-profit' : (rf.pnl ?? 0) < 0 ? 'text-pnl-loss' : 'text-text-muted'}`}>
                      {rf.pnl?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? '-'}
                    </td>
                    <td className="px-3 py-2 text-right">{rf.positions}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                {(() => {
                  const totDelta$ = riskFactors.reduce((s, r) => s + (r['delta_$'] ?? 0), 0)
                  const totGamma$ = riskFactors.reduce((s, r) => s + (r['gamma_$'] ?? 0), 0)
                  const totPnl = riskFactors.reduce((s, r) => s + (r.pnl ?? 0), 0)
                  const totPositions = riskFactors.reduce((s, r) => s + (r.positions ?? 0), 0)
                  return (
                    <tr className="border-t-2 border-border-primary bg-bg-tertiary font-bold">
                      <td className="px-3 py-2"></td>
                      <td className="px-3 py-2 text-text-primary">TOTAL</td>
                      <td className="px-3 py-2"></td>
                      <td className="px-3 py-2"></td>
                      <td className="px-3 py-2"></td>
                      <td className="px-3 py-2"></td>
                      <td className="px-3 py-2"></td>
                      <td className="px-3 py-2 text-right">{totDelta$.toLocaleString('en-US', { maximumFractionDigits: 0 })}</td>
                      <td className="px-3 py-2 text-right">{totGamma$.toLocaleString('en-US', { maximumFractionDigits: 0 })}</td>
                      <td className={`px-3 py-2 text-right ${totPnl > 0 ? 'text-pnl-profit' : totPnl < 0 ? 'text-pnl-loss' : 'text-text-muted'}`}>
                        {totPnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td className="px-3 py-2 text-right">{totPositions}</td>
                    </tr>
                  )
                })()}
              </tfoot>
            </table>
          </div>
        </div>
      )}

      {/* Pending Orders — working orders not yet filled */}
      {liveOrders && liveOrders.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
              Pending Orders ({liveOrders.length})
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="border-b border-border-primary text-text-muted text-left">
                  <th className="px-3 py-2">Broker</th>
                  <th className="px-3 py-2">Underlying</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Legs</th>
                  <th className="px-3 py-2 text-right">Price</th>
                  <th className="px-3 py-2 text-right">Filled</th>
                  <th className="px-3 py-2">Received</th>
                </tr>
              </thead>
              <tbody>
                {liveOrders.map((order) => (
                  <tr key={order.order_id} className="border-b border-border-primary hover:bg-bg-secondary">
                    <td className="px-3 py-2 text-text-muted">{order.broker}</td>
                    <td className="px-3 py-2 font-semibold text-text-primary">{order.underlying}</td>
                    <td className="px-3 py-2">
                      <span className="px-1.5 py-0.5 rounded text-2xs font-semibold bg-orange-900/30 text-orange-400 border border-orange-800">
                        {order.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-text-secondary">
                      {order.legs.map((leg, i) => (
                        <div key={i}>
                          {leg.action} {leg.quantity} {leg.symbol}
                        </div>
                      ))}
                    </td>
                    <td className="px-3 py-2 text-right">{order.price?.toFixed(2) ?? '-'}</td>
                    <td className="px-3 py-2 text-right">{order.filled_quantity}</td>
                    <td className="px-3 py-2 text-text-muted">
                      {order.received_at ? new Date(order.received_at).toLocaleString() : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

    </div>
  )
}
