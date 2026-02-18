import { clsx } from 'clsx'
import { Save, RotateCcw, Loader2 } from 'lucide-react'

interface SaveBarProps {
  onSave: () => void
  onReset: () => void
  dirty: boolean
  saving?: boolean
}

export function SaveBar({ onSave, onReset, dirty, saving = false }: SaveBarProps) {
  if (!dirty && !saving) return null

  return (
    <div className="sticky bottom-0 left-0 right-0 z-30 bg-bg-primary/95 backdrop-blur border-t border-border-primary px-4 py-2.5 flex items-center justify-between">
      <span className="text-2xs text-text-muted">
        {saving ? 'Saving changes...' : 'You have unsaved changes'}
      </span>
      <div className="flex items-center gap-2">
        <button
          onClick={onReset}
          disabled={saving}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs text-text-secondary border border-border-primary hover:bg-bg-hover disabled:opacity-40"
        >
          <RotateCcw size={12} />
          Reset
        </button>
        <button
          onClick={onSave}
          disabled={saving}
          className={clsx(
            'flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium',
            'bg-accent-blue/20 text-accent-blue border border-accent-blue/40 hover:bg-accent-blue/30',
            'disabled:opacity-40',
          )}
        >
          {saving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
          Save
        </button>
      </div>
    </div>
  )
}
