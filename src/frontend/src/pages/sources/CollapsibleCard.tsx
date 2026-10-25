import { ChevronDown } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { cx } from '../../lib/cx'

function remembered(key: string, fallback = false): boolean {
  try {
    const v = localStorage.getItem(key)
    return v === null ? fallback : v === '1'
  } catch { return fallback }
}

function useRemembered(key: string, fallback = false): [boolean, () => void] {
  const [open, setOpen] = useState(() => remembered(key, fallback))
  const toggle = () => {
    setOpen(!open)
    try { localStorage.setItem(key, open ? '0' : '1') } catch { /* private mode: fine */ }
  }
  return [open, toggle]
}

/** A part inside a card that folds to its heading line, e.g. one network's balance in a
 * wallet (Vanixxx, 2026-10-10). Closed by default, remembered like the card. */
export function Fold({ storageKey, title, side, children, defaultOpen = false, line = true, className }: {
  storageKey: string; title: ReactNode; side?: ReactNode; children: ReactNode; defaultOpen?: boolean
  /** a line above, between parts of the same list */
  line?: boolean; className?: string
}) {
  const [open, toggle] = useRemembered(storageKey, defaultOpen)
  return (
    <div className={cx('grid gap-2', line && 'border-t border-line pt-2', className)}>
      <button type="button" onClick={toggle} aria-expanded={open}
        className="flex w-full flex-wrap items-center justify-between gap-2 border-0 bg-transparent p-0 text-left text-fg">
        <span className="flex min-w-0 items-center gap-2">
          <ChevronDown size={16} aria-hidden="true" className={cx('shrink-0 text-muted transition-transform', !open && '-rotate-90')} />
          {title}
        </span>
        {side}
      </button>
      {open && children}
    </div>
  )
}

/** A source card that folds to one summary line. Closed by default; the choice is a
 * per-browser convenience in localStorage, never needed for anything else. */
export function CollapsibleCard({ storageKey, title, meta, summary, children }: {
  storageKey: string; title: ReactNode; meta: ReactNode; summary: ReactNode; children: ReactNode
}) {
  const [open, toggle] = useRemembered(storageKey)
  return (
    <section className="card grid gap-3">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <button type="button" onClick={toggle} aria-expanded={open}
          className="flex min-w-0 items-center gap-2 border-0 bg-transparent p-0 text-left text-fg">
          <ChevronDown size={18} aria-hidden="true" className={cx('shrink-0 text-muted transition-transform', !open && '-rotate-90')} />
          <h2 className="m-0 min-w-0 text-base font-semibold">{title}</h2>
        </button>
        <span className="num text-sm text-muted">{meta}</span>
      </div>
      {summary}
      {open && <div className="grid gap-3">{children}</div>}
    </section>
  )
}
