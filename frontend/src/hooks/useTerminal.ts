import { useState, useCallback, useRef } from 'react'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface TerminalBlock {
  type: 'header' | 'keyvalue' | 'table' | 'text' | 'error' | 'section' | 'status' | 'list' | 'clear'
  text?: string
  style?: string
  title?: string
  label?: string
  color?: string
  items?: Array<{ key: string; value: string; color?: string }> | string[]
  headers?: string[]
  rows?: string[][]
}

export interface TerminalEntry {
  command: string
  blocks: TerminalBlock[]
  timestamp: number
  success: boolean
}

interface TerminalResponse {
  blocks: TerminalBlock[]
  command: string
  success: boolean
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useTerminal() {
  const [history, setHistory] = useState<TerminalEntry[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [commandHistory, setCommandHistory] = useState<string[]>([])
  const [historyIndex, setHistoryIndex] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)

  const execute = useCallback(async (cmd: string) => {
    const trimmed = cmd.trim()
    if (!trimmed) return

    // Add to command history
    setCommandHistory((prev) => {
      const filtered = prev.filter((c) => c !== trimmed)
      return [trimmed, ...filtered].slice(0, 50)
    })
    setHistoryIndex(-1)
    setInput('')
    setLoading(true)

    try {
      const { data } = await api.post<TerminalResponse>(endpoints.terminalExecute, {
        command: trimmed,
      })

      // Handle clear command
      if (data.blocks.some((b) => b.type === 'clear')) {
        setHistory([])
      } else {
        setHistory((prev) => [
          ...prev,
          {
            command: trimmed,
            blocks: data.blocks,
            timestamp: Date.now(),
            success: data.success,
          },
        ])
      }
    } catch (err) {
      setHistory((prev) => [
        ...prev,
        {
          command: trimmed,
          blocks: [{ type: 'error', text: `Network error: ${err instanceof Error ? err.message : 'Unknown'}` }],
          timestamp: Date.now(),
          success: false,
        },
      ])
    } finally {
      setLoading(false)
    }
  }, [])

  const navigateHistory = useCallback(
    (direction: 'up' | 'down') => {
      if (commandHistory.length === 0) return
      if (direction === 'up') {
        const newIdx = Math.min(historyIndex + 1, commandHistory.length - 1)
        setHistoryIndex(newIdx)
        setInput(commandHistory[newIdx])
      } else {
        const newIdx = historyIndex - 1
        if (newIdx < 0) {
          setHistoryIndex(-1)
          setInput('')
        } else {
          setHistoryIndex(newIdx)
          setInput(commandHistory[newIdx])
        }
      }
    },
    [commandHistory, historyIndex],
  )

  return {
    history,
    input,
    setInput,
    loading,
    execute,
    navigateHistory,
    inputRef,
  }
}
