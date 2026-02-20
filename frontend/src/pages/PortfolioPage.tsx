import { useState, useMemo } from 'react'
import { usePortfolios } from '../hooks/usePortfolios'
import { usePositions } from '../hooks/usePositions'
import { useBrokerPositions } from '../hooks/useBrokerPositions'
import { PortfolioGrid } from '../components/grids/PortfolioGrid'
import { PositionGrid } from '../components/grids/PositionGrid'
import { BrokerPositionGrid } from '../components/grids/BrokerPositionGrid'
import { PortfolioCard } from '../components/cards/PortfolioCard'
import { PnLDisplay } from '../components/common/PnLDisplay'
import { GreeksBar } from '../components/common/GreeksBar'
import { Spinner } from '../components/common/Spinner'
import { EmptyState } from '../components/common/EmptyState'
import { clsx } from 'clsx'

type ViewMode = 'real' | 'whatif' | 'fund' | 'all'

export function PortfolioPage() {
  const { data: portfolios, isLoading: loadingPortfolios } = usePortfolios()
  const [selectedPortfolio, setSelectedPortfolio] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('real')

  const { data: positions, isLoading: loadingPositions } = usePositions(
    selectedPortfolio || undefined,
  )
  const { data: brokerPositions, isLoading: loadingBrokerPositions } = useBrokerPositions(
    selectedPortfolio || undefined,
  )

  const filteredPortfolios = useMemo(() => {
    if (!portfolios) return []
    // Always exclude research portfolios from main view
    const nonResearch = portfolios.filter((p) => !p.name.startsWith('research_'))
    if (viewMode === 'real') return nonResearch.filter((p) => p.portfolio_type === 'real' && p.broker !== 'stallion')
    if (viewMode === 'whatif') return nonResearch.filter((p) => p.portfolio_type === 'what_if')
    if (viewMode === 'fund') return nonResearch.filter((p) => p.broker === 'stallion')
    return nonResearch
  }, [portfolios, viewMode])

  const selected = useMemo(
    () => portfolios?.find((p) => p.name === selectedPortfolio),
    [portfolios, selectedPortfolio],
  )

  // Aggregate totals
  const totals = useMemo(() => {
    if (!portfolios) return null
    const real = portfolios.filter((p) => p.portfolio_type === 'real')
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
                {(['real', 'whatif', 'fund', 'all'] as ViewMode[]).map((mode) => (
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
                    {mode === 'whatif' ? 'WhatIf' : mode === 'fund' ? 'Funds' : mode.charAt(0).toUpperCase() + mode.slice(1)}
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
              <GreeksBar label="\u0394" value={selected.portfolio_delta} limit={selected.max_portfolio_delta} />
              <GreeksBar label="\u0393" value={selected.portfolio_gamma} limit={selected.max_portfolio_gamma} />
              <GreeksBar label="\u0398" value={selected.portfolio_theta} limit={selected.min_portfolio_theta} />
              <GreeksBar label="\u03BD" value={selected.portfolio_vega} limit={selected.max_portfolio_vega} />
            </div>
          </div>
        </div>
      )}

      {/* System Trades (booked via workflow) */}
      <div className="card">
        <div className="card-header">
          <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
            {selectedPortfolio ? `${selectedPortfolio} Trades` : 'All Open Trades'}
            {positions && ` (${positions.length})`}
          </h2>
        </div>
        {loadingPositions ? (
          <div className="card-body flex justify-center py-8">
            <Spinner />
          </div>
        ) : positions && positions.length > 0 ? (
          <PositionGrid trades={positions} />
        ) : (
          <EmptyState message="No system-booked trades" />
        )}
      </div>

      {/* Broker Positions (synced from TastyTrade/broker) */}
      <div className="card">
        <div className="card-header">
          <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
            Broker Positions
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
    </div>
  )
}
