import { useState, useMemo, useCallback, useRef } from 'react'
import { AgGridReact } from 'ag-grid-react'
import type { ColDef, GridApi } from 'ag-grid-community'
import { clsx } from 'clsx'
import { Download } from 'lucide-react'
import { Spinner } from '../components/common/Spinner'
import { AgentBadge } from '../components/common/AgentBadge'
import { EmptyState } from '../components/common/EmptyState'
import {
  PnLRenderer,
  StatusBadgeRenderer,
  GreeksRenderer,
  CurrencyRenderer,
  PercentRenderer,
} from '../components/grids/cellRenderers'
import {
  useTradeJournal,
  usePerformanceReport,
  useStrategyBreakdown,
  useSourceAttribution,
  useWeeklyPnl,
  useDecisionAudit,
  useRecommendationsReport,
  useTradeEvents,
} from '../hooks/useReports'
import { usePortfolios } from '../hooks/usePortfolios'

const TABS = [
  'Trade Journal',
  'Performance',
  'Strategy',
  'Source',
  'Decisions',
  'Weekly P&L',
  'Recommendations',
  'Events',
] as const

type TabName = (typeof TABS)[number]

const defaultColDef: ColDef = {
  sortable: true,
  resizable: true,
  filter: true,
  suppressMovable: true,
}

const gridTheme = {
  headerHeight: 28,
  rowHeight: 28,
}

function DateRenderer({ value }: { value: unknown }) {
  if (!value) return <span className="text-text-muted">--</span>
  const d = new Date(value as string)
  return <span className="font-mono-num text-text-secondary">{d.toLocaleDateString()}</span>
}

function DurationRenderer({ value }: { value: unknown }) {
  if (value == null) return <span className="text-text-muted">--</span>
  return <span className="font-mono-num text-text-secondary">{String(value)}d</span>
}

// ---------------------------------------------------------------------------
// Filter bar component
// ---------------------------------------------------------------------------

function FilterBar({
  portfolios,
  selectedPortfolio,
  onPortfolioChange,
  children,
}: {
  portfolios: { name: string }[]
  selectedPortfolio: string
  onPortfolioChange: (v: string) => void
  children?: React.ReactNode
}) {
  return (
    <div className="flex items-center gap-3 px-4 py-2 border-b border-border-secondary bg-bg-secondary/50">
      <select
        value={selectedPortfolio}
        onChange={(e) => onPortfolioChange(e.target.value)}
        className="bg-bg-primary border border-border-primary rounded px-2 py-1 text-xs text-text-primary"
      >
        <option value="">All Portfolios</option>
        {portfolios.map((p) => (
          <option key={p.name} value={p.name}>{p.name}</option>
        ))}
      </select>
      {children}
    </div>
  )
}

function ExportButton({ gridApi }: { gridApi: GridApi | null }) {
  return (
    <button
      onClick={() => gridApi?.exportDataAsCsv()}
      className="flex items-center gap-1 px-2 py-1 text-xs text-text-secondary hover:text-text-primary border border-border-primary rounded hover:bg-bg-hover"
    >
      <Download size={12} />
      CSV
    </button>
  )
}

// ---------------------------------------------------------------------------
// Trade Journal Tab
// ---------------------------------------------------------------------------

function TradeJournalTab({ portfolios }: { portfolios: { name: string }[] }) {
  const [portfolio, setPortfolio] = useState('')
  const [status, setStatus] = useState('')
  const gridRef = useRef<GridApi | null>(null)

  const { data, isLoading } = useTradeJournal({
    portfolio: portfolio || undefined,
    status: status || undefined,
    limit: 500,
  })

  const columnDefs = useMemo<ColDef[]>(() => [
    { field: 'portfolio_name', headerName: 'Portfolio', width: 130 },
    { field: 'underlying_symbol', headerName: 'Symbol', width: 80 },
    { field: 'strategy_type', headerName: 'Strategy', width: 140 },
    { field: 'trade_status', headerName: 'Status', width: 90, cellRenderer: StatusBadgeRenderer },
    { field: 'trade_source', headerName: 'Source', width: 110 },
    { field: 'legs_count', headerName: 'Legs', width: 60, type: 'numericColumn' },
    { field: 'entry_price', headerName: 'Entry', width: 80, cellRenderer: CurrencyRenderer },
    { field: 'exit_price', headerName: 'Exit', width: 80, cellRenderer: CurrencyRenderer },
    { field: 'total_pnl', headerName: 'P&L', width: 100, cellRenderer: PnLRenderer },
    { field: 'delta_pnl', headerName: 'Delta P&L', width: 90, cellRenderer: PnLRenderer },
    { field: 'theta_pnl', headerName: 'Theta P&L', width: 90, cellRenderer: PnLRenderer },
    { field: 'duration_days', headerName: 'Duration', width: 80, cellRenderer: DurationRenderer },
    { field: 'created_at', headerName: 'Created', width: 100, cellRenderer: DateRenderer },
    { field: 'opened_at', headerName: 'Opened', width: 100, cellRenderer: DateRenderer },
    { field: 'closed_at', headerName: 'Closed', width: 100, cellRenderer: DateRenderer },
    { field: 'notes', headerName: 'Notes', width: 200, flex: 1 },
  ], [])

  if (isLoading) return <div className="flex justify-center py-12"><Spinner /></div>

  return (
    <>
      <FilterBar portfolios={portfolios} selectedPortfolio={portfolio} onPortfolioChange={setPortfolio}>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="bg-bg-primary border border-border-primary rounded px-2 py-1 text-xs text-text-primary"
        >
          <option value="">All Status</option>
          <option value="open">Open</option>
          <option value="closed">Closed</option>
        </select>
        <span className="text-2xs text-text-muted ml-auto">{data?.total ?? 0} trades</span>
        <ExportButton gridApi={gridRef.current} />
      </FilterBar>
      <div className="ag-theme-custom flex-1">
        <AgGridReact
          rowData={data?.trades ?? []}
          columnDefs={columnDefs}
          defaultColDef={defaultColDef}
          headerHeight={gridTheme.headerHeight}
          rowHeight={gridTheme.rowHeight}
          onGridReady={(p) => { gridRef.current = p.api }}
          animateRows={false}
          suppressCellFocus
        />
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// Performance Tab
// ---------------------------------------------------------------------------

function PerformanceTab({ portfolios }: { portfolios: { name: string }[] }) {
  const [portfolio, setPortfolio] = useState('')
  const gridRef = useRef<GridApi | null>(null)
  const { data, isLoading } = usePerformanceReport(portfolio || undefined)

  const columnDefs = useMemo<ColDef[]>(() => [
    { field: 'label', headerName: 'Portfolio', width: 150 },
    { field: 'total_trades', headerName: 'Trades', width: 70, type: 'numericColumn' },
    { field: 'winning_trades', headerName: 'Wins', width: 60, type: 'numericColumn' },
    { field: 'losing_trades', headerName: 'Losses', width: 70, type: 'numericColumn' },
    { field: 'win_rate', headerName: 'Win %', width: 70, cellRenderer: PercentRenderer },
    { field: 'total_pnl', headerName: 'Total P&L', width: 110, cellRenderer: PnLRenderer },
    { field: 'avg_win', headerName: 'Avg Win', width: 90, cellRenderer: PnLRenderer },
    { field: 'avg_loss', headerName: 'Avg Loss', width: 90, cellRenderer: PnLRenderer },
    { field: 'biggest_win', headerName: 'Best', width: 90, cellRenderer: PnLRenderer },
    { field: 'biggest_loss', headerName: 'Worst', width: 90, cellRenderer: PnLRenderer },
    { field: 'profit_factor', headerName: 'PF', width: 60, cellRenderer: GreeksRenderer },
    { field: 'expectancy', headerName: 'Expect.', width: 90, cellRenderer: PnLRenderer },
    { field: 'sharpe_ratio', headerName: 'Sharpe', width: 70, cellRenderer: GreeksRenderer },
    { field: 'max_drawdown_pct', headerName: 'Max DD%', width: 80, cellRenderer: PercentRenderer },
    { field: 'cagr_pct', headerName: 'CAGR%', width: 70, cellRenderer: PercentRenderer },
    { field: 'return_pct', headerName: 'Return%', width: 80, cellRenderer: PercentRenderer },
    { field: 'initial_capital', headerName: 'Capital', width: 100, cellRenderer: CurrencyRenderer },
    { field: 'current_equity', headerName: 'Equity', width: 100, cellRenderer: CurrencyRenderer },
  ], [])

  if (isLoading) return <div className="flex justify-center py-12"><Spinner /></div>

  return (
    <>
      <FilterBar portfolios={portfolios} selectedPortfolio={portfolio} onPortfolioChange={setPortfolio}>
        <ExportButton gridApi={gridRef.current} />
      </FilterBar>
      <div className="ag-theme-custom flex-1">
        <AgGridReact
          rowData={data ?? []}
          columnDefs={columnDefs}
          defaultColDef={defaultColDef}
          headerHeight={gridTheme.headerHeight}
          rowHeight={gridTheme.rowHeight}
          onGridReady={(p) => { gridRef.current = p.api }}
          animateRows={false}
          suppressCellFocus
        />
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// Strategy Breakdown Tab
// ---------------------------------------------------------------------------

function StrategyTab({ portfolios }: { portfolios: { name: string }[] }) {
  const [portfolio, setPortfolio] = useState(portfolios[0]?.name ?? '')
  const gridRef = useRef<GridApi | null>(null)
  const { data, isLoading } = useStrategyBreakdown(portfolio)

  const rows = useMemo(() => {
    if (!data?.strategies) return []
    return Object.values(data.strategies)
  }, [data])

  const columnDefs = useMemo<ColDef[]>(() => [
    { field: 'label', headerName: 'Strategy', width: 160 },
    { field: 'total_trades', headerName: 'Trades', width: 70, type: 'numericColumn' },
    { field: 'win_rate', headerName: 'Win %', width: 70, cellRenderer: PercentRenderer },
    { field: 'total_pnl', headerName: 'Total P&L', width: 110, cellRenderer: PnLRenderer },
    { field: 'avg_win', headerName: 'Avg Win', width: 90, cellRenderer: PnLRenderer },
    { field: 'avg_loss', headerName: 'Avg Loss', width: 90, cellRenderer: PnLRenderer },
    { field: 'profit_factor', headerName: 'PF', width: 60, cellRenderer: GreeksRenderer },
    { field: 'expectancy', headerName: 'Expect.', width: 90, cellRenderer: PnLRenderer },
    { field: 'sharpe_ratio', headerName: 'Sharpe', width: 70, cellRenderer: GreeksRenderer },
  ], [])

  if (isLoading) return <div className="flex justify-center py-12"><Spinner /></div>

  return (
    <>
      <FilterBar portfolios={portfolios} selectedPortfolio={portfolio} onPortfolioChange={setPortfolio}>
        <ExportButton gridApi={gridRef.current} />
      </FilterBar>
      {!portfolio ? (
        <EmptyState message="Select a portfolio" />
      ) : (
        <div className="ag-theme-custom flex-1">
          <AgGridReact
            rowData={rows}
            columnDefs={columnDefs}
            defaultColDef={defaultColDef}
            headerHeight={gridTheme.headerHeight}
            rowHeight={gridTheme.rowHeight}
            onGridReady={(p) => { gridRef.current = p.api }}
            animateRows={false}
            suppressCellFocus
          />
        </div>
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// Source Attribution Tab
// ---------------------------------------------------------------------------

function SourceTab({ portfolios }: { portfolios: { name: string }[] }) {
  const [portfolio, setPortfolio] = useState(portfolios[0]?.name ?? '')
  const gridRef = useRef<GridApi | null>(null)
  const { data, isLoading } = useSourceAttribution(portfolio)

  const rows = useMemo(() => {
    if (!data?.sources) return []
    return Object.values(data.sources)
  }, [data])

  const columnDefs = useMemo<ColDef[]>(() => [
    { field: 'label', headerName: 'Source', width: 160 },
    { field: 'total_trades', headerName: 'Trades', width: 70, type: 'numericColumn' },
    { field: 'win_rate', headerName: 'Win %', width: 70, cellRenderer: PercentRenderer },
    { field: 'total_pnl', headerName: 'Total P&L', width: 110, cellRenderer: PnLRenderer },
    { field: 'avg_win', headerName: 'Avg Win', width: 90, cellRenderer: PnLRenderer },
    { field: 'avg_loss', headerName: 'Avg Loss', width: 90, cellRenderer: PnLRenderer },
    { field: 'profit_factor', headerName: 'PF', width: 60, cellRenderer: GreeksRenderer },
    { field: 'expectancy', headerName: 'Expect.', width: 90, cellRenderer: PnLRenderer },
  ], [])

  if (isLoading) return <div className="flex justify-center py-12"><Spinner /></div>

  return (
    <>
      <FilterBar portfolios={portfolios} selectedPortfolio={portfolio} onPortfolioChange={setPortfolio}>
        <ExportButton gridApi={gridRef.current} />
      </FilterBar>
      {!portfolio ? (
        <EmptyState message="Select a portfolio" />
      ) : (
        <div className="ag-theme-custom flex-1">
          <AgGridReact
            rowData={rows}
            columnDefs={columnDefs}
            defaultColDef={defaultColDef}
            headerHeight={gridTheme.headerHeight}
            rowHeight={gridTheme.rowHeight}
            onGridReady={(p) => { gridRef.current = p.api }}
            animateRows={false}
            suppressCellFocus
          />
        </div>
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// Decisions Tab
// ---------------------------------------------------------------------------

function DecisionsTab() {
  const gridRef = useRef<GridApi | null>(null)
  const [responseFilter, setResponseFilter] = useState('')
  const { data, isLoading } = useDecisionAudit({
    response: responseFilter || undefined,
    limit: 200,
  })

  const columnDefs = useMemo<ColDef[]>(() => [
    { field: 'decision_type', headerName: 'Type', width: 90 },
    { field: 'response', headerName: 'Response', width: 90, cellRenderer: StatusBadgeRenderer },
    { field: 'presented_at', headerName: 'Presented', width: 140, cellRenderer: DateRenderer },
    { field: 'responded_at', headerName: 'Responded', width: 140, cellRenderer: DateRenderer },
    {
      field: 'time_to_decision_seconds',
      headerName: 'Response Time',
      width: 110,
      type: 'numericColumn',
      valueFormatter: (p) => {
        if (p.value == null) return '--'
        const s = Number(p.value)
        if (s < 60) return `${s}s`
        if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`
        return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
      },
    },
    { field: 'escalation_count', headerName: 'Escalations', width: 90, type: 'numericColumn' },
    { field: 'rationale', headerName: 'Rationale', width: 300, flex: 1 },
    { field: 'recommendation_id', headerName: 'Rec ID', width: 120 },
  ], [])

  if (isLoading) return <div className="flex justify-center py-12"><Spinner /></div>

  return (
    <>
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border-secondary bg-bg-secondary/50">
        <select
          value={responseFilter}
          onChange={(e) => setResponseFilter(e.target.value)}
          className="bg-bg-primary border border-border-primary rounded px-2 py-1 text-xs text-text-primary"
        >
          <option value="">All Responses</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="deferred">Deferred</option>
          <option value="expired">Expired</option>
        </select>
        <span className="text-2xs text-text-muted ml-auto">{data?.total ?? 0} decisions</span>
        <ExportButton gridApi={gridRef.current} />
      </div>
      <div className="ag-theme-custom flex-1">
        <AgGridReact
          rowData={data?.decisions ?? []}
          columnDefs={columnDefs}
          defaultColDef={defaultColDef}
          headerHeight={gridTheme.headerHeight}
          rowHeight={gridTheme.rowHeight}
          onGridReady={(p) => { gridRef.current = p.api }}
          animateRows={false}
          suppressCellFocus
        />
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// Weekly P&L Tab
// ---------------------------------------------------------------------------

function WeeklyPnlTab({ portfolios }: { portfolios: { name: string }[] }) {
  const [portfolio, setPortfolio] = useState(portfolios[0]?.name ?? '')
  const gridRef = useRef<GridApi | null>(null)
  const { data, isLoading } = useWeeklyPnl(portfolio, 26)

  const columnDefs = useMemo<ColDef[]>(() => [
    { field: 'week_start', headerName: 'Week Start', width: 120, cellRenderer: DateRenderer },
    { field: 'week_end', headerName: 'Week End', width: 120, cellRenderer: DateRenderer },
    { field: 'pnl', headerName: 'Weekly P&L', width: 120, cellRenderer: PnLRenderer },
    { field: 'trade_count', headerName: 'Trades', width: 80, type: 'numericColumn' },
    { field: 'cumulative_pnl', headerName: 'Cumulative', width: 120, cellRenderer: PnLRenderer },
  ], [])

  if (isLoading) return <div className="flex justify-center py-12"><Spinner /></div>

  return (
    <>
      <FilterBar portfolios={portfolios} selectedPortfolio={portfolio} onPortfolioChange={setPortfolio}>
        <ExportButton gridApi={gridRef.current} />
      </FilterBar>
      {!portfolio ? (
        <EmptyState message="Select a portfolio" />
      ) : (
        <div className="ag-theme-custom flex-1">
          <AgGridReact
            rowData={data?.weeks ?? []}
            columnDefs={columnDefs}
            defaultColDef={defaultColDef}
            headerHeight={gridTheme.headerHeight}
            rowHeight={gridTheme.rowHeight}
            onGridReady={(p) => { gridRef.current = p.api }}
            animateRows={false}
            suppressCellFocus
          />
        </div>
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// Recommendations Tab
// ---------------------------------------------------------------------------

function RecommendationsTab() {
  const gridRef = useRef<GridApi | null>(null)
  const [statusFilter, setStatusFilter] = useState('')
  const { data, isLoading } = useRecommendationsReport({
    status: statusFilter || undefined,
    limit: 200,
  })

  const columnDefs = useMemo<ColDef[]>(() => [
    { field: 'recommendation_type', headerName: 'Type', width: 80 },
    { field: 'underlying', headerName: 'Symbol', width: 80 },
    { field: 'strategy_type', headerName: 'Strategy', width: 140 },
    { field: 'status', headerName: 'Status', width: 90, cellRenderer: StatusBadgeRenderer },
    { field: 'source', headerName: 'Source', width: 110 },
    { field: 'confidence', headerName: 'Conf.', width: 60, type: 'numericColumn' },
    { field: 'risk_category', headerName: 'Risk', width: 80 },
    { field: 'suggested_portfolio', headerName: 'Portfolio', width: 120 },
    { field: 'exit_urgency', headerName: 'Urgency', width: 80 },
    { field: 'created_at', headerName: 'Created', width: 120, cellRenderer: DateRenderer },
    { field: 'reviewed_at', headerName: 'Reviewed', width: 120, cellRenderer: DateRenderer },
    { field: 'rationale', headerName: 'Rationale', width: 250, flex: 1 },
  ], [])

  if (isLoading) return <div className="flex justify-center py-12"><Spinner /></div>

  return (
    <>
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border-secondary bg-bg-secondary/50">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="bg-bg-primary border border-border-primary rounded px-2 py-1 text-xs text-text-primary"
        >
          <option value="">All Status</option>
          <option value="pending">Pending</option>
          <option value="accepted">Accepted</option>
          <option value="rejected">Rejected</option>
          <option value="expired">Expired</option>
        </select>
        <span className="text-2xs text-text-muted ml-auto">{data?.total ?? 0} recs</span>
        <ExportButton gridApi={gridRef.current} />
      </div>
      <div className="ag-theme-custom flex-1">
        <AgGridReact
          rowData={data?.recommendations ?? []}
          columnDefs={columnDefs}
          defaultColDef={defaultColDef}
          headerHeight={gridTheme.headerHeight}
          rowHeight={gridTheme.rowHeight}
          onGridReady={(p) => { gridRef.current = p.api }}
          animateRows={false}
          suppressCellFocus
        />
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// Events Tab
// ---------------------------------------------------------------------------

function EventsTab() {
  const gridRef = useRef<GridApi | null>(null)
  const { data, isLoading } = useTradeEvents({ limit: 200 })

  const columnDefs = useMemo<ColDef[]>(() => [
    { field: 'event_type', headerName: 'Event', width: 120 },
    { field: 'underlying_symbol', headerName: 'Symbol', width: 80 },
    { field: 'strategy_type', headerName: 'Strategy', width: 140 },
    { field: 'timestamp', headerName: 'Time', width: 140, cellRenderer: DateRenderer },
    { field: 'net_credit_debit', headerName: 'Net Cr/Dr', width: 100, cellRenderer: PnLRenderer },
    { field: 'entry_delta', headerName: 'Delta', width: 70, cellRenderer: GreeksRenderer },
    { field: 'entry_theta', headerName: 'Theta', width: 70, cellRenderer: GreeksRenderer },
    { field: 'trade_id', headerName: 'Trade ID', width: 120 },
    {
      field: 'tags',
      headerName: 'Tags',
      width: 200,
      flex: 1,
      valueFormatter: (p) => (p.value ? (p.value as string[]).join(', ') : ''),
    },
  ], [])

  if (isLoading) return <div className="flex justify-center py-12"><Spinner /></div>

  return (
    <>
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border-secondary bg-bg-secondary/50">
        <span className="text-2xs text-text-muted ml-auto">{data?.total ?? 0} events</span>
        <ExportButton gridApi={gridRef.current} />
      </div>
      <div className="ag-theme-custom flex-1">
        <AgGridReact
          rowData={data?.events ?? []}
          columnDefs={columnDefs}
          defaultColDef={defaultColDef}
          headerHeight={gridTheme.headerHeight}
          rowHeight={gridTheme.rowHeight}
          onGridReady={(p) => { gridRef.current = p.api }}
          animateRows={false}
          suppressCellFocus
        />
      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// Main Reports Page
// ---------------------------------------------------------------------------

export function ReportsPage() {
  const [activeTab, setActiveTab] = useState<TabName>('Trade Journal')
  const { data: portfolios } = usePortfolios()

  const portfolioNames = useMemo(
    () => (portfolios ?? []).map((p) => ({ name: p.name })),
    [portfolios],
  )

  return (
    <div className="flex flex-col h-full">
      {/* Agent ownership + Tab bar */}
      <div className="flex items-center gap-1.5 px-2 pt-1">
        <AgentBadge agent="atlas" />
        <AgentBadge agent="maverick" />
      </div>
      <div className="flex border-b border-border-primary bg-bg-primary px-2">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={clsx(
              'px-3 py-2 text-xs font-medium border-b-2 transition-colors',
              activeTab === tab
                ? 'border-accent-blue text-accent-blue'
                : 'border-transparent text-text-secondary hover:text-text-primary hover:border-border-primary',
            )}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 flex flex-col min-h-0">
        {activeTab === 'Trade Journal' && <TradeJournalTab portfolios={portfolioNames} />}
        {activeTab === 'Performance' && <PerformanceTab portfolios={portfolioNames} />}
        {activeTab === 'Strategy' && <StrategyTab portfolios={portfolioNames} />}
        {activeTab === 'Source' && <SourceTab portfolios={portfolioNames} />}
        {activeTab === 'Decisions' && <DecisionsTab />}
        {activeTab === 'Weekly P&L' && <WeeklyPnlTab portfolios={portfolioNames} />}
        {activeTab === 'Recommendations' && <RecommendationsTab />}
        {activeTab === 'Events' && <EventsTab />}
      </div>
    </div>
  )
}
