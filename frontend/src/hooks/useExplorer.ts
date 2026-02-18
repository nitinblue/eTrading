import { useQuery, useMutation } from '@tanstack/react-query'
import { api } from '../api/client'
import { explorerEndpoints } from '../api/endpoints'
import type { TableInfo, ExplorerQuery, ExplorerResult } from '../api/types'

export function useExplorerTables() {
  return useQuery<TableInfo[]>({
    queryKey: ['explorer', 'tables'],
    queryFn: async () => {
      const { data } = await api.get(explorerEndpoints.tables)
      return data
    },
  })
}

export function useExplorerTableDetail(tableName: string) {
  return useQuery<TableInfo>({
    queryKey: ['explorer', 'table', tableName],
    queryFn: async () => {
      const { data } = await api.get(explorerEndpoints.table(tableName))
      return data
    },
    enabled: !!tableName,
  })
}

export function useExplorerQuery(query: ExplorerQuery | null) {
  return useQuery<ExplorerResult>({
    queryKey: ['explorer', 'query', query],
    queryFn: async () => {
      const { data } = await api.post(explorerEndpoints.query, query)
      return data
    },
    enabled: !!query,
  })
}

export function useExplorerCsvExport() {
  return useMutation({
    mutationFn: async (query: ExplorerQuery) => {
      const response = await api.post(explorerEndpoints.queryCsv, query, {
        responseType: 'blob',
      })
      const blob = new Blob([response.data], { type: 'text/csv' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${query.table}_export.csv`
      a.click()
      window.URL.revokeObjectURL(url)
    },
  })
}
