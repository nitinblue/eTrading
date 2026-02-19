import { useState, useRef, useEffect } from 'react'
import { MessageSquare, X, Send, Trash2 } from 'lucide-react'
import { clsx } from 'clsx'
import { ChatMessage } from './ChatMessage'
import { useChat } from '../../hooks/useChat'

const QUICK_ACTIONS = [
  'Agent Status',
  'Portfolio Summary',
  'Pending Recs',
  'Capital',
  'Workflow Status',
]

export function ChatPanel() {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const { messages, sendMessage, clearMessages, isProcessing } = useChat()
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const handleSend = () => {
    if (!input.trim() || isProcessing) return
    sendMessage(input)
    setInput('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <>
      {/* Toggle button */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-10 right-4 z-40 flex items-center gap-2 px-3 py-2 rounded-lg bg-accent-blue text-white text-xs font-medium shadow-lg hover:bg-blue-500 transition-colors"
        >
          <MessageSquare size={14} />
          Chat
        </button>
      )}

      {/* Panel */}
      <div
        className={clsx(
          'fixed top-0 right-0 z-50 h-full bg-bg-primary border-l border-border-primary shadow-xl flex flex-col transition-transform duration-200',
          open ? 'translate-x-0' : 'translate-x-full',
          'w-[340px]',
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-border-secondary">
          <div className="flex items-center gap-2">
            <MessageSquare size={14} className="text-accent-blue" />
            <span className="text-xs font-semibold text-text-primary">CoTrader Chat</span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={clearMessages}
              className="p-1 rounded text-text-muted hover:text-text-primary hover:bg-bg-hover"
              title="Clear chat"
            >
              <Trash2 size={12} />
            </button>
            <button
              onClick={() => setOpen(false)}
              className="p-1 rounded text-text-muted hover:text-text-primary hover:bg-bg-hover"
            >
              <X size={14} />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-2">
          {messages.map((msg) => (
            <ChatMessage
              key={msg.id}
              role={msg.role}
              text={msg.text}
              timestamp={msg.timestamp}
            />
          ))}
          {isProcessing && (
            <div className="flex justify-start">
              <div className="bg-bg-tertiary border border-border-secondary rounded-lg px-3 py-2 text-xs text-text-muted">
                Thinking...
              </div>
            </div>
          )}
        </div>

        {/* Quick actions */}
        <div className="px-3 py-1.5 border-t border-border-secondary/50">
          <div className="flex flex-wrap gap-1">
            {QUICK_ACTIONS.map((action) => (
              <button
                key={action}
                onClick={() => sendMessage(action)}
                disabled={isProcessing}
                className="px-2 py-0.5 rounded text-2xs bg-bg-tertiary text-text-secondary border border-border-secondary hover:bg-bg-hover hover:text-text-primary disabled:opacity-40"
              >
                {action}
              </button>
            ))}
          </div>
        </div>

        {/* Input */}
        <div className="px-3 py-2 border-t border-border-secondary">
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about portfolio, agents, capital..."
              disabled={isProcessing}
              className="flex-1 px-2 py-1.5 rounded text-xs bg-bg-secondary border border-border-primary text-text-primary placeholder:text-text-muted focus:border-accent-blue focus:outline-none"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isProcessing}
              className="p-1.5 rounded bg-accent-blue text-white hover:bg-blue-500 disabled:opacity-40"
            >
              <Send size={12} />
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
