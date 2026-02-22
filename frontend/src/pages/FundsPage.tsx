import { useState, useMemo } from 'react'
import { usePortfolios } from '../hooks/usePortfolios'
import { usePositions } from '../hooks/usePositions'
import { PortfolioGrid } from '../components/grids/PortfolioGrid'
import { PositionGrid } from '../components/grids/PositionGrid'
import { PnLDisplay } from '../components/common/PnLDisplay'
import { Spinner } from '../components/common/Spinner'
import { EmptyState } from '../components/common/EmptyState'

export function FundsPage() {
  const { data: portfolios, isLoading: loadingPortfolios } = usePortfolios()
  const [selectedPortfolio, setSelectedPortfolio] = useState<string | null>(null)

  const { data: positions, isLoading: loadingPositions } = usePositions(
    selectedPortfolio || undefined,
  )

  const fundPortfolios = useMemo(() => {
    if (!portfolios) return []
    return portfolios.filter((p) => p.broker === 'stallion')
  }, [portfolios])

  const totals = useMemo(() => {
    if (!fundPortfolios.length) return null
    return {
      equity: fundPortfolios.reduce((sum, p) => sum + p.total_equity, 0),
      totalPnl: fundPortfolios.reduce((sum, p) => sum + p.total_pnl, 0),
      currency: fundPortfolios[0]?.currency || 'INR',
    }
  }, [fundPortfolios])

  // Only show fund positions
  const fundPositions = useMemo(() => {
    if (!positions) return []
    return positions.filter((p: any) => p.portfolio_name === 'stallion_fund' || fundPortfolios.some(fp => fp.name === p.portfolio_name))
  }, [positions, fundPortfolios])

  if (loadingPortfolios) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner size="lg" />
      </div>
    )
  }

  if (fundPortfolios.length === 0) {
    return <EmptyState message="No fund portfolios configured" />
  }

  return (
    <div className="space-y-3">
      {/* Summary header */}
      {totals && (
        <div className="card">
          <div className="card-body">
            <div className="flex items-center gap-6">
              <div>
                <div className="text-2xs text-text-muted uppercase">Total Equity (Funds)</div>
                <div className="text-lg font-mono font-bold text-text-primary">
                  {totals.currency === 'INR' ? '\u20B9' : '$'}{totals.equity.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                </div>
              </div>
              <div>
                <div className="text-2xs text-text-muted uppercase">Total P&L</div>
                <PnLDisplay value={totals.totalPnl} size="md" />
              </div>
              <div>
                <div className="text-2xs text-text-muted uppercase">Portfolios</div>
                <span className="text-sm font-mono text-text-primary">{fundPortfolios.length}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Portfolio grid */}
      <div className="card">
        <div className="card-header flex items-center justify-between">
          <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
            Fund Portfolios ({fundPortfolios.length})
          </h2>
          {selectedPortfolio && (
            <button
              onClick={() => setSelectedPortfolio(null)}
              className="text-2xs text-accent-blue hover:underline"
            >
              Show all
            </button>
          )}
        </div>
        <PortfolioGrid
          portfolios={fundPortfolios}
          onPortfolioClick={setSelectedPortfolio}
        />
      </div>

      {/* Fund Positions */}
      {fundPositions.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
              Fund Positions ({fundPositions.length})
            </h2>
          </div>
          {loadingPositions ? (
            <div className="card-body flex justify-center py-8">
              <Spinner />
            </div>
          ) : (
            <PositionGrid trades={fundPositions} />
          )}
        </div>
      )}
    </div>
  )
}
