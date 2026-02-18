import { useEffect, useState } from 'react'
import { clsx } from 'clsx'
import { CheckCircle, XCircle, X } from 'lucide-react'

export interface ToastMessage {
  id: string
  type: 'success' | 'error'
  message: string
}

let _addToast: ((msg: Omit<ToastMessage, 'id'>) => void) | null = null

/** Show a toast from anywhere (call after ToastContainer is mounted). */
export function showToast(type: 'success' | 'error', message: string) {
  _addToast?.({ type, message })
}

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastMessage[]>([])

  useEffect(() => {
    _addToast = (msg) => {
      const id = crypto.randomUUID()
      setToasts((prev) => [...prev, { ...msg, id }])
      setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000)
    }
    return () => { _addToast = null }
  }, [])

  if (toasts.length === 0) return null

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={clsx(
            'flex items-center gap-2 px-4 py-2.5 rounded-lg shadow-lg text-xs font-medium border',
            'animate-[slideIn_0.2s_ease-out]',
            t.type === 'success'
              ? 'bg-green-900/80 text-green-300 border-green-700'
              : 'bg-red-900/80 text-red-300 border-red-700',
          )}
        >
          {t.type === 'success' ? <CheckCircle size={14} /> : <XCircle size={14} />}
          <span>{t.message}</span>
          <button
            onClick={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))}
            className="ml-2 opacity-60 hover:opacity-100"
          >
            <X size={12} />
          </button>
        </div>
      ))}
    </div>
  )
}
