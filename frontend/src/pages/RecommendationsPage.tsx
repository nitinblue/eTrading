import { useState, useMemo, useCallback } from 'react'
import { AgGridReact } from 'ag-grid-react'
import { ColDef, RowClickedEvent, ICellRendererParams } from 'ag-grid-community'
import { defaultGridOptions, numericColDef } from '../components/grids/gridTheme'
import { StatusBadgeRenderer } from '../components/grids/cellRenderers'
import { useRecommendations, useApproveRec, useRejectRec, useDeferRec } from '../hooks/useRecommendations'
import { RecommendationModal } from '../components/modals/RecommendationModal'
import { Spinner } from '../components/common/Spinner'
import { AgentBadge } from '../components/common/AgentBadge'
import { EmptyState } from '../components/common/EmptyState'
import { showToast } from '../components/common/Toast'
import { clsx } from 'clsx'
import type { Recommendation } from '../api/types'

function TypeBadgeRenderer({ value }: ICellRendererParams) {
  const colors: Record<string, string> = {
    entry: 'bg-green-900/30 text-green-400 border-green-800',
    exit: 'bg-red-900/30 text-red-400 border-red-800',
    roll: 'bg-cyan-900/30 text-cyan-400 border-cyan-800',
    adjust: 'bg-purple-900/30 text-purple-400 border-purple-800',
  }
  const cls = colors[value] || 'bg-zinc-800/50 text-zinc-400 border-zinc-700'
  return (
    <span className={`px-1.5 py-0.5 rounded text-2xs font-semibold border ${cls}`}>
      {(value || '').toUpperCase()}
    </span>
  )
}

function ConfidenceRenderer({ value }: ICellRendererParams) {
  if (value == null) return <span className="text-text-muted">--</span>
  const pct = (Number(value) * 100)
  const color = pct >= 70 ? 'bg-green-500' : pct >= 50 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-1.5 w-full">
      <div className="flex-1 h-2 bg-bg-tertiary rounded overflow-hidden">
        <div className={`h-full ${color} rounded`} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono-num text-text-secondary text-2xs w-8 text-right">
        {pct.toFixed(0)}%
      </span>
    </div>
  )
}

const columnDefs: ColDef[] = [
  { field: 'recommendation_type', headerName: 'Type', width: 80, cellRenderer: TypeBadgeRenderer },
  { field: 'source', headerName: 'Source', width: 100 },
  { field: 'underlying', headerName: 'Underlying', width: 90, cellStyle: { fontWeight: 600 } },
  { field: 'strategy_type', headerName: 'Strategy', width: 140 },
  { field: 'confidence', headerName: 'Confidence', width: 120, cellRenderer: ConfidenceRenderer },
  { field: 'risk_category', headerName: 'Risk', width: 80 },
  { field: 'suggested_portfolio', headerName: 'Portfolio', width: 120 },
  { field: 'max_loss_display', headerName: 'Max Loss', width: 100, ...numericColDef },
  { field: 'max_profit_display', headerName: 'Max Profit', width: 100, ...numericColDef },
  {
    field: 'rationale',
    headerName: 'Rationale',
    flex: 1,
    minWidth: 200,
    cellStyle: { fontSize: '11px', color: '#8888a0' },
    valueFormatter: ({ value }) => value ? (value.length > 80 ? value.substring(0, 80) + '...' : value) : '',
  },
  { field: 'status', headerName: 'Status', width: 90, cellRenderer: StatusBadgeRenderer },
  {
    field: 'created_at',
    headerName: 'Created',
    width: 130,
    valueFormatter: ({ value }) => value ? new Date(value).toLocaleString() : '--',
    sort: 'desc',
  },
]

const STATUS_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'accepted', label: 'Accepted' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'expired', label: 'Expired' },
]

export function RecommendationsPage() {
  const [statusFilter, setStatusFilter] = useState('pending')
  const { data: recs, isLoading } = useRecommendations({ status: statusFilter || undefined })
  const [selectedRec, setSelectedRec] = useState<Recommendation | null>(null)

  const approveMut = useApproveRec()
  const rejectMut = useRejectRec()
  const deferMut = useDeferRec()

  const onRowClicked = useCallback((e: RowClickedEvent) => {
    setSelectedRec(e.data as Recommendation)
  }, [])

  const gridHeight = useMemo(() => {
    const count = recs?.length || 0
    return Math.max(Math.min(count * 28 + 36, 600), 200)
  }, [recs?.length])

  const handleApprove = useCallback(
    (portfolio: string, notes: string) => {
      if (!selectedRec) return
      approveMut.mutate(
        { id: selectedRec.id, portfolio, notes },
        {
          onSuccess: () => {
            showToast('success', `Approved: ${selectedRec.underlying} ${selectedRec.strategy_type}`)
            setSelectedRec(null)
          },
          onError: () => showToast('error', 'Failed to approve recommendation'),
        },
      )
    },
    [selectedRec, approveMut],
  )

  const handleReject = useCallback(
    (reason: string) => {
      if (!selectedRec) return
      rejectMut.mutate(
        { id: selectedRec.id, reason },
        {
          onSuccess: () => {
            showToast('success', `Rejected: ${selectedRec.underlying}`)
            setSelectedRec(null)
          },
          onError: () => showToast('error', 'Failed to reject recommendation'),
        },
      )
    },
    [selectedRec, rejectMut],
  )

  const handleDefer = useCallback(() => {
    if (!selectedRec) return
    deferMut.mutate(selectedRec.id, {
      onSuccess: () => {
        showToast('success', `Deferred: ${selectedRec.underlying}`)
        setSelectedRec(null)
      },
      onError: () => showToast('error', 'Failed to defer recommendation'),
    })
  }, [selectedRec, deferMut])

  if (isLoading) {
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
        <AgentBadge agent="quant_research" />
        <AgentBadge agent="circuit_breaker" />
      </div>
      {/* Filter bar */}
      <div className="card">
        <div className="card-body">
          <div className="flex items-center gap-3">
            <span className="text-2xs text-text-muted uppercase">Status:</span>
            {STATUS_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setStatusFilter(opt.value)}
                className={clsx(
                  'px-2.5 py-1 rounded text-xs font-medium transition-colors',
                  statusFilter === opt.value
                    ? 'bg-accent-blue text-white'
                    : 'bg-bg-tertiary text-text-secondary hover:bg-bg-hover',
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Grid */}
      <div className="card">
        <div className="card-header">
          <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
            Recommendations {recs && `(${recs.length})`}
          </h2>
        </div>
        {recs && recs.length > 0 ? (
          <div className="ag-theme-alpine-dark w-full" style={{ height: gridHeight }}>
            <AgGridReact
              {...defaultGridOptions}
              rowData={recs}
              columnDefs={columnDefs}
              onRowClicked={onRowClicked}
              rowStyle={{ cursor: 'pointer' }}
              getRowId={(params) => params.data.id}
            />
          </div>
        ) : (
          <EmptyState message={statusFilter ? `No ${statusFilter} recommendations` : 'No recommendations yet. Run a workflow cycle to generate recommendations.'} />
        )}
      </div>

      {/* Detail modal */}
      {selectedRec && (
        <RecommendationModal
          rec={selectedRec}
          onApprove={handleApprove}
          onReject={handleReject}
          onDefer={handleDefer}
          onClose={() => setSelectedRec(null)}
          isLoading={approveMut.isPending || rejectMut.isPending || deferMut.isPending}
        />
      )}
    </div>
  )
}
