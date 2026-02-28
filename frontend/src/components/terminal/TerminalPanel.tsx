import { useEffect, useRef } from 'react'
import { clsx } from 'clsx'
import { useTerminal } from '../../hooks/useTerminal'
import type { TerminalBlock, TerminalEntry } from '../../hooks/useTerminal'

// ---------------------------------------------------------------------------
// Block renderers
// ---------------------------------------------------------------------------

function BlockHeader({ block }: { block: TerminalBlock }) {
  return (
    <div className="mt-2 mb-1">
      <span className="text-text-primary font-bold text-[12px]">{block.text}</span>
      <div className="border-b border-border-secondary/50 mt-0.5" />
    </div>
  )
}

function BlockKeyValue({ block }: { block: TerminalBlock }) {
  const items = block.items as Array<{ key: string; value: string; color?: string }> | undefined
  if (!items) return null
  return (
    <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-0 pl-2">
      {items.map((item, i) => (
        <div key={i} className="contents">
          <span className="text-text-muted text-[11px] font-mono">{item.key}:</span>
          <span className={clsx('text-[11px] font-mono',
            item.color ? `text-accent-${item.color}` : 'text-text-primary'
          )}>{item.value}</span>
        </div>
      ))}
    </div>
  )
}

function BlockTable({ block }: { block: TerminalBlock }) {
  if (!block.headers || !block.rows) return null
  return (
    <div className="overflow-x-auto pl-2 my-1">
      <table className="border-collapse font-mono text-[11px]">
        <thead>
          <tr>
            {block.headers.map((h, i) => (
              <th key={i} className="text-left pr-4 pb-0.5 text-text-muted font-semibold text-[10px]">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {block.rows.map((row, ri) => (
            <tr key={ri}>
              {row.map((cell, ci) => (
                <td key={ci} className="pr-4 py-[1px] text-text-primary whitespace-nowrap">{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function BlockText({ block }: { block: TerminalBlock }) {
  return (
    <div className={clsx('text-[11px] font-mono pl-2 whitespace-pre-wrap',
      block.style === 'dim' ? 'text-text-muted' : 'text-text-primary'
    )}>
      {block.text}
    </div>
  )
}

function BlockError({ block }: { block: TerminalBlock }) {
  return (
    <div className="text-accent-red text-[11px] font-mono pl-2">
      ERROR: {block.text}
    </div>
  )
}

function BlockSection({ block }: { block: TerminalBlock }) {
  return (
    <div className="mt-1.5 mb-0.5 pl-2">
      <span className="text-text-secondary text-[11px] font-mono font-semibold underline underline-offset-2">{block.title}</span>
    </div>
  )
}

function BlockStatus({ block }: { block: TerminalBlock }) {
  const colorMap: Record<string, string> = {
    green: 'bg-accent-green/20 text-accent-green',
    red: 'bg-accent-red/20 text-accent-red',
    yellow: 'bg-accent-yellow/20 text-accent-yellow',
    cyan: 'bg-accent-cyan/20 text-accent-cyan',
  }
  return (
    <div className="pl-2 my-0.5">
      <span className={clsx('text-[11px] font-mono font-bold px-2 py-[2px] rounded',
        colorMap[block.color || 'green'] || colorMap.green
      )}>
        {block.label}
      </span>
    </div>
  )
}

function BlockList({ block }: { block: TerminalBlock }) {
  const items = block.items as string[] | undefined
  if (!items) return null
  const isConditions = block.style === 'conditions'
  return (
    <div className="pl-2 space-y-0">
      {items.map((item, i) => {
        if (isConditions) {
          const isPass = item.startsWith('+')
          const isFail = item.startsWith('-')
          return (
            <div key={i} className={clsx('text-[11px] font-mono',
              isPass ? 'text-accent-green' : isFail ? 'text-accent-red' : 'text-text-primary'
            )}>
              {item}
            </div>
          )
        }
        return (
          <div key={i} className="text-[11px] font-mono text-text-primary">{item}</div>
        )
      })}
    </div>
  )
}

function RenderBlock({ block }: { block: TerminalBlock }) {
  switch (block.type) {
    case 'header': return <BlockHeader block={block} />
    case 'keyvalue': return <BlockKeyValue block={block} />
    case 'table': return <BlockTable block={block} />
    case 'text': return <BlockText block={block} />
    case 'error': return <BlockError block={block} />
    case 'section': return <BlockSection block={block} />
    case 'status': return <BlockStatus block={block} />
    case 'list': return <BlockList block={block} />
    default: return null
  }
}

// ---------------------------------------------------------------------------
// Entry (one command + its output)
// ---------------------------------------------------------------------------

function EntryView({ entry }: { entry: TerminalEntry }) {
  return (
    <div className="mb-2">
      <div className="flex items-center gap-1">
        <span className="text-accent-cyan text-[11px] font-mono font-semibold">cotrader&gt;</span>
        <span className="text-text-primary text-[11px] font-mono">{entry.command}</span>
      </div>
      <div className="mt-0.5">
        {entry.blocks.map((block, i) => (
          <RenderBlock key={i} block={block} />
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Terminal Panel
// ---------------------------------------------------------------------------

export function TerminalPanel() {
  const { history, input, setInput, loading, execute, navigateHistory, inputRef } = useTerminal()
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom on new output
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [history, loading])

  // Auto-focus on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [inputRef])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !loading) {
      execute(input)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      navigateHistory('up')
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      navigateHistory('down')
    }
  }

  return (
    <div className="flex flex-col h-full bg-bg-primary border-t border-border-primary">
      {/* Scrollable output area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-2 min-h-0">
        {/* Welcome message */}
        {history.length === 0 && !loading && (
          <div className="text-text-muted text-[11px] font-mono">
            <span className="text-text-secondary font-semibold">cotrader</span> — unified trading terminal. Type <span className="text-accent-cyan">'help'</span> for commands.
          </div>
        )}

        {/* History entries */}
        {history.map((entry, i) => (
          <EntryView key={i} entry={entry} />
        ))}

        {/* Loading indicator */}
        {loading && (
          <div className="flex items-center gap-1 mb-2">
            <span className="text-accent-cyan text-[11px] font-mono font-semibold">cotrader&gt;</span>
            <span className="text-text-muted text-[11px] font-mono animate-pulse">Running...</span>
          </div>
        )}
      </div>

      {/* Input area */}
      <div
        className="flex items-center gap-1 px-3 py-1.5 border-t border-border-secondary bg-bg-secondary/50 flex-shrink-0 cursor-text"
        onClick={() => inputRef.current?.focus()}
      >
        <span className="text-accent-cyan text-[11px] font-mono font-semibold whitespace-nowrap">cotrader&gt;</span>
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          placeholder={loading ? 'Running...' : ''}
          className="flex-1 bg-transparent text-text-primary text-[11px] font-mono outline-none border-none placeholder:text-text-muted/50 caret-accent-cyan disabled:opacity-50"
          autoComplete="off"
          spellCheck={false}
        />
      </div>
    </div>
  )
}
