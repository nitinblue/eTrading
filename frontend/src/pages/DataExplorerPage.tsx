import { useState, useMemo, useCallback, useRef } from 'react'
import { AgGridReact } from 'ag-grid-react'
import type { ColDef, GridApi } from 'ag-grid-community'
import { clsx } from 'clsx'
import { Play, Download, X, Plus, Database, Table2 } from 'lucide-react'
import { Spinner } from '../components/common/Spinner'
import { EmptyState } from '../components/common/EmptyState'
import {
  useExplorerTables,
  useExplorerQuery,
  useExplorerCsvExport,
} from '../hooks/useExplorer'
import type { ColumnMeta, ExplorerFilterSpec, ExplorerQuery as ExplorerQueryType } from '../api/types'

const OPERATORS_BY_TYPE: Record<string, { value: string; label: string }[]> = {
  string: [
    { value: 'eq', label: '=' },
    { value: 'neq', label: '!=' },
    { value: 'contains', label: 'contains' },
    { value: 'starts_with', label: 'starts with' },
    { value: 'in', label: 'in (csv)' },
  ],
  numeric: [
    { value: 'eq', label: '=' },
    { value: 'neq', label: '!=' },
    { value: 'gt', label: '>' },
    { value: 'gte', label: '>=' },
    { value: 'lt', label: '<' },
    { value: 'lte', label: '<=' },
    { value: 'between', label: 'between' },
  ],
  datetime: [
    { value: 'eq', label: '=' },
    { value: 'gt', label: 'after' },
    { value: 'gte', label: 'on or after' },
    { value: 'lt', label: 'before' },
    { value: 'lte', label: 'on or before' },
    { value: 'between', label: 'between' },
  ],
  boolean: [
    { value: 'eq', label: '=' },
  ],
  json: [
    { value: 'contains', label: 'contains' },
  ],
}

interface FilterRow {
  id: number
  column: string
  operator: string
  value: string
  value2: string
}

let filterId = 0

// ---------------------------------------------------------------------------
// Table list (left panel)
// ---------------------------------------------------------------------------

function TableList({
  tables,
  selected,
  onSelect,
}: {
  tables: { name: string; row_count: number }[]
  selected: string
  onSelect: (name: string) => void
}) {
  return (
    <div className="w-[220px] border-r border-border-primary flex flex-col bg-bg-primary">
      <div className="px-3 py-2 border-b border-border-secondary">
        <div className="flex items-center gap-2 text-xs font-medium text-text-primary">
          <Database size={14} className="text-accent-blue" />
          Tables ({tables.length})
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        {tables.map((t) => (
          <button
            key={t.name}
            onClick={() => onSelect(t.name)}
            className={clsx(
              'w-full text-left px-3 py-1.5 text-xs flex items-center justify-between hover:bg-bg-hover transition-colors',
              selected === t.name
                ? 'bg-bg-active text-accent-blue'
                : 'text-text-secondary',
            )}
          >
            <span className="flex items-center gap-1.5 truncate">
              <Table2 size={12} className="shrink-0 opacity-50" />
              {t.name}
            </span>
            <span className="text-2xs text-text-muted font-mono-num">{t.row_count}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Filter builder
// ---------------------------------------------------------------------------

function FilterBuilder({
  columns,
  filters,
  onFiltersChange,
}: {
  columns: ColumnMeta[]
  filters: FilterRow[]
  onFiltersChange: (filters: FilterRow[]) => void
}) {
  const addFilter = () => {
    const first = columns[0]
    onFiltersChange([
      ...filters,
      {
        id: ++filterId,
        column: first?.name ?? '',
        operator: 'eq',
        value: '',
        value2: '',
      },
    ])
  }

  const removeFilter = (id: number) => {
    onFiltersChange(filters.filter((f) => f.id !== id))
  }

  const updateFilter = (id: number, key: keyof FilterRow, val: string) => {
    onFiltersChange(
      filters.map((f) => {
        if (f.id !== id) return f
        const updated = { ...f, [key]: val }
        // Reset operator if column changes type
        if (key === 'column') {
          const col = columns.find((c) => c.name === val)
          const ops = OPERATORS_BY_TYPE[col?.type ?? 'string']
          if (ops && !ops.some((o) => o.value === f.operator)) {
            updated.operator = ops[0].value
          }
        }
        return updated
      }),
    )
  }

  const colMap = useMemo(() => {
    const m: Record<string, ColumnMeta> = {}
    columns.forEach((c) => { m[c.name] = c })
    return m
  }, [columns])

  return (
    <div className="space-y-1.5">
      {filters.map((f) => {
        const colType = colMap[f.column]?.type ?? 'string'
        const ops = OPERATORS_BY_TYPE[colType] ?? OPERATORS_BY_TYPE.string
        const isBetween = f.operator === 'between'
        const isDatetime = colType === 'datetime'

        return (
          <div key={f.id} className="flex items-center gap-2">
            <select
              value={f.column}
              onChange={(e) => updateFilter(f.id, 'column', e.target.value)}
              className="bg-bg-primary border border-border-primary rounded px-2 py-1 text-xs text-text-primary w-[160px]"
            >
              {columns.map((c) => (
                <option key={c.name} value={c.name}>{c.name}</option>
              ))}
            </select>
            <select
              value={f.operator}
              onChange={(e) => updateFilter(f.id, 'operator', e.target.value)}
              className="bg-bg-primary border border-border-primary rounded px-2 py-1 text-xs text-text-primary w-[100px]"
            >
              {ops.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <input
              type={isDatetime ? 'date' : 'text'}
              value={f.value}
              onChange={(e) => updateFilter(f.id, 'value', e.target.value)}
              placeholder="value"
              className="bg-bg-primary border border-border-primary rounded px-2 py-1 text-xs text-text-primary w-[140px]"
            />
            {isBetween && (
              <>
                <span className="text-2xs text-text-muted">to</span>
                <input
                  type={isDatetime ? 'date' : 'text'}
                  value={f.value2}
                  onChange={(e) => updateFilter(f.id, 'value2', e.target.value)}
                  placeholder="value2"
                  className="bg-bg-primary border border-border-primary rounded px-2 py-1 text-xs text-text-primary w-[140px]"
                />
              </>
            )}
            <button
              onClick={() => removeFilter(f.id)}
              className="p-1 text-text-muted hover:text-accent-red transition-colors"
            >
              <X size={12} />
            </button>
          </div>
        )
      })}
      <button
        onClick={addFilter}
        className="flex items-center gap-1 text-2xs text-accent-blue hover:text-blue-300 transition-colors"
      >
        <Plus size={10} />
        Add Filter
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function DataExplorerPage() {
  const { data: tables, isLoading: tablesLoading } = useExplorerTables()
  const [selectedTable, setSelectedTable] = useState('')
  const [filters, setFilters] = useState<FilterRow[]>([])
  const [sortBy, setSortBy] = useState('')
  const [sortDesc, setSortDesc] = useState(false)
  const [limit, setLimit] = useState(100)
  const [submittedQuery, setSubmittedQuery] = useState<ExplorerQueryType | null>(null)
  const gridRef = useRef<GridApi | null>(null)
  const csvExport = useExplorerCsvExport()

  const { data: result, isLoading: queryLoading, isFetching } = useExplorerQuery(submittedQuery)

  // Get columns for selected table
  const tableColumns = useMemo(() => {
    if (!tables || !selectedTable) return []
    const t = tables.find((t) => t.name === selectedTable)
    return t?.columns ?? []
  }, [tables, selectedTable])

  // Build AG Grid column defs dynamically from result
  const columnDefs = useMemo<ColDef[]>(() => {
    if (!result?.columns) return []
    return result.columns.map((col) => {
      const def: ColDef = {
        field: col.name,
        headerName: col.name,
        sortable: true,
        resizable: true,
        filter: true,
        suppressMovable: true,
      }
      if (col.type === 'numeric') {
        def.type = 'numericColumn'
        def.width = 100
        def.cellClass = 'font-mono-num text-right'
      } else if (col.type === 'datetime') {
        def.width = 150
        def.valueFormatter = (p) => {
          if (!p.value) return ''
          return new Date(p.value).toLocaleString()
        }
        def.cellClass = 'font-mono-num'
      } else if (col.type === 'boolean') {
        def.width = 70
        def.cellRenderer = (p: { value: unknown }) => (
          <span className={p.value ? 'text-green-400' : 'text-text-muted'}>
            {p.value ? 'true' : 'false'}
          </span>
        )
      } else if (col.type === 'json') {
        def.width = 200
        def.valueFormatter = (p) => (p.value ? JSON.stringify(p.value) : '')
      } else {
        def.width = 140
      }
      return def
    })
  }, [result?.columns])

  const handleSelectTable = useCallback((name: string) => {
    setSelectedTable(name)
    setFilters([])
    setSortBy('')
    setSubmittedQuery(null)
  }, [])

  const handleRun = useCallback(() => {
    if (!selectedTable) return
    const query: ExplorerQueryType = {
      table: selectedTable,
      limit,
      offset: 0,
    }
    if (filters.length > 0) {
      query.filters = filters
        .filter((f) => f.value.trim())
        .map((f): ExplorerFilterSpec => ({
          column: f.column,
          operator: f.operator,
          value: f.value,
          ...(f.operator === 'between' && f.value2 ? { value2: f.value2 } : {}),
        }))
    }
    if (sortBy) {
      query.sort_by = sortBy
      query.sort_desc = sortDesc
    }
    setSubmittedQuery(query)
  }, [selectedTable, filters, sortBy, sortDesc, limit])

  const handleExport = useCallback(() => {
    if (!submittedQuery) return
    csvExport.mutate({ ...submittedQuery, limit: 1000 })
  }, [submittedQuery, csvExport])

  const handleClear = useCallback(() => {
    setFilters([])
    setSortBy('')
    setSortDesc(false)
    setSubmittedQuery(null)
  }, [])

  if (tablesLoading) {
    return <div className="flex items-center justify-center h-full"><Spinner size="lg" /></div>
  }

  return (
    <div className="flex h-full">
      {/* Left: table list */}
      <TableList
        tables={tables ?? []}
        selected={selectedTable}
        onSelect={handleSelectTable}
      />

      {/* Right: query builder + results */}
      <div className="flex-1 flex flex-col min-w-0">
        {!selectedTable ? (
          <div className="flex-1 flex items-center justify-center">
            <EmptyState message="Select a table to explore" />
          </div>
        ) : (
          <>
            {/* Query builder */}
            <div className="border-b border-border-primary bg-bg-secondary/50 px-4 py-3 space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-text-primary">{selectedTable}</span>
                <span className="text-2xs text-text-muted">
                  {tables?.find((t) => t.name === selectedTable)?.row_count ?? 0} rows
                </span>
                <span className="text-2xs text-text-muted">|</span>
                <span className="text-2xs text-text-muted">{tableColumns.length} columns</span>
              </div>

              {/* Filters */}
              <FilterBuilder
                columns={tableColumns}
                filters={filters}
                onFiltersChange={setFilters}
              />

              {/* Sort + Limit + Actions */}
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5">
                  <span className="text-2xs text-text-muted">Sort:</span>
                  <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value)}
                    className="bg-bg-primary border border-border-primary rounded px-2 py-1 text-xs text-text-primary w-[140px]"
                  >
                    <option value="">None</option>
                    {tableColumns.map((c) => (
                      <option key={c.name} value={c.name}>{c.name}</option>
                    ))}
                  </select>
                  {sortBy && (
                    <button
                      onClick={() => setSortDesc(!sortDesc)}
                      className="px-1.5 py-0.5 text-2xs border border-border-primary rounded text-text-secondary hover:text-text-primary"
                    >
                      {sortDesc ? 'DESC' : 'ASC'}
                    </button>
                  )}
                </div>

                <div className="flex items-center gap-1.5">
                  <span className="text-2xs text-text-muted">Limit:</span>
                  <select
                    value={limit}
                    onChange={(e) => setLimit(Number(e.target.value))}
                    className="bg-bg-primary border border-border-primary rounded px-2 py-1 text-xs text-text-primary"
                  >
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                    <option value={250}>250</option>
                    <option value={500}>500</option>
                    <option value={1000}>1000</option>
                  </select>
                </div>

                <div className="flex items-center gap-2 ml-auto">
                  <button
                    onClick={handleClear}
                    className="flex items-center gap-1 px-2 py-1 text-xs text-text-secondary hover:text-text-primary border border-border-primary rounded hover:bg-bg-hover"
                  >
                    Clear
                  </button>
                  {result && (
                    <button
                      onClick={handleExport}
                      disabled={csvExport.isPending}
                      className="flex items-center gap-1 px-2 py-1 text-xs text-text-secondary hover:text-text-primary border border-border-primary rounded hover:bg-bg-hover"
                    >
                      <Download size={12} />
                      CSV
                    </button>
                  )}
                  <button
                    onClick={handleRun}
                    disabled={queryLoading}
                    className="flex items-center gap-1 px-3 py-1 text-xs font-medium bg-accent-blue text-white rounded hover:bg-blue-500 transition-colors disabled:opacity-50"
                  >
                    <Play size={12} />
                    Run
                  </button>
                </div>
              </div>
            </div>

            {/* Results */}
            <div className="flex-1 flex flex-col min-h-0">
              {isFetching && !result && (
                <div className="flex justify-center py-12"><Spinner /></div>
              )}
              {result && (
                <>
                  <div className="px-4 py-1.5 text-2xs text-text-muted border-b border-border-secondary bg-bg-primary">
                    {result.total} total rows | showing {result.rows.length} (offset {result.offset})
                    {isFetching && <span className="ml-2 text-accent-blue">refreshing...</span>}
                  </div>
                  <div className="ag-theme-custom flex-1">
                    <AgGridReact
                      rowData={result.rows}
                      columnDefs={columnDefs}
                      defaultColDef={{
                        sortable: true,
                        resizable: true,
                        filter: true,
                        suppressMovable: true,
                      }}
                      headerHeight={28}
                      rowHeight={28}
                      onGridReady={(p) => { gridRef.current = p.api }}
                      animateRows={false}
                      suppressCellFocus
                    />
                  </div>
                </>
              )}
              {!result && !isFetching && (
                <div className="flex-1 flex items-center justify-center">
                  <EmptyState message="Click Run to execute query" />
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
