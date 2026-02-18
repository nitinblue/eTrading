import type { GridOptions } from 'ag-grid-community'

export const defaultGridOptions: GridOptions = {
  headerHeight: 32,
  rowHeight: 28,
  animateRows: true,
  suppressCellFocus: true,
  enableCellTextSelection: true,
  defaultColDef: {
    sortable: true,
    resizable: true,
    suppressMovable: false,
    cellStyle: {
      fontSize: '12px',
      fontFamily: "'JetBrains Mono', monospace",
      display: 'flex',
      alignItems: 'center',
    },
  },
}

export const numericColDef = {
  cellStyle: {
    fontSize: '12px',
    fontFamily: "'JetBrains Mono', monospace",
    textAlign: 'right' as const,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'flex-end',
  },
}

export const pnlColDef = {
  ...numericColDef,
  cellStyle: (params: { value: number }) => ({
    ...numericColDef.cellStyle,
    color: params.value > 0 ? '#22c55e' : params.value < 0 ? '#ef4444' : '#555568',
    fontWeight: 500,
  }),
}
