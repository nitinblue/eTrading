import { useState } from 'react'
import { clsx } from 'clsx'
import { ChevronDown, ChevronRight } from 'lucide-react'

interface FormSectionProps {
  title: string
  description?: string
  defaultOpen?: boolean
  children: React.ReactNode
}

export function FormSection({ title, description, defaultOpen = true, children }: FormSectionProps) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className="border border-border-primary rounded-lg bg-bg-secondary mb-3">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 w-full px-4 py-3 text-left hover:bg-bg-hover rounded-t-lg transition-colors"
      >
        {open ? <ChevronDown size={14} className="text-text-muted" /> : <ChevronRight size={14} className="text-text-muted" />}
        <span className="text-xs font-semibold text-text-primary uppercase tracking-wide">{title}</span>
        {description && <span className="text-2xs text-text-muted ml-2">{description}</span>}
      </button>
      {open && <div className="px-4 pb-4 pt-1">{children}</div>}
    </div>
  )
}
