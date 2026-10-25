import { MoreHorizontal } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { cx } from '../../lib/cx'
import { useTranslation } from 'react-i18next'
import type { RawRow } from '../../lib/api'
import { CoinIcon } from '../../components/CoinIcon'
import { side } from '../../lib/rows'

export function ActionsButton({ id, open, setOpen }: { id: number; open: number | null; setOpen: (v: number | null) => void }) {
  const { t } = useTranslation()
  return (
    <button type="button" aria-label={t('manual.actions')} aria-expanded={open === id} onClick={() => setOpen(open === id ? null : id)}
      className="rounded-ctl p-1.5 text-muted hover:bg-surface-2 hover:text-fg">
      <MoreHorizontal size={18} aria-hidden="true" />
    </button>
  )
}

export function Sides({ r }: { r: RawRow }) {
  const { t } = useTranslation()
  const feeLabel = t('pages.transactions.fee')
  const parts = [
    r.incoming[0] && <Amount key="i" asset={r.incoming[0]} text={side(r.incoming, '+')} className="text-up" />,
    r.outgoing[0] && <Amount key="o" asset={r.outgoing[0]} text={side(r.outgoing, '−')} className="text-down" />,
    r.fee[0] && <span key="f" className="num self-center text-xs text-muted">{feeLabel} {side(r.fee, '')}</span>,
  ].filter(Boolean)
  return <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">{parts}</div>
}

/** An amount with its coin's symbol in front. */
export function Amount({ asset, text, className }: { asset: string; text: string; className?: string }) {
  return (
    <span className={`num inline-flex items-center gap-2 ${className ?? ''}`}>
      <CoinIcon asset={asset} size={24} />{text}
    </span>
  )
}

/** Tabs like a spreadsheet's sheets (Vanixxx, 2026-10-06): one panel at a time, "Details"
 * first. Scrolls sideways on a phone instead of wrapping. */
export function Tabs<T extends string>({ value, onChange, tabs }: {
  value: T; onChange: (v: T) => void; tabs: { value: T; label: React.ReactNode }[]
}) {
  // more tabs to the right on a phone: the edge fades out, so a swipe is expected (M8)
  const [more, setMore] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const measure = () => { const el = box.current; if (el) setMore(el.scrollLeft + el.clientWidth < el.scrollWidth - 4) }
  useEffect(() => {
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [tabs.length])
  return (
    <div ref={box} role="tablist" onScroll={measure}
      className={`-mx-1 flex gap-1 overflow-x-auto overflow-y-hidden overscroll-x-contain border-b border-line px-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden ${more ? '[mask-image:linear-gradient(to_right,black_80%,transparent)]' : ''}`}>
      {tabs.map((tab) => (
        <button key={tab.value} type="button" role="tab" aria-selected={value === tab.value} onClick={() => onChange(tab.value)}
          className={value === tab.value
            ? '-mb-px inline-flex shrink-0 items-center gap-1.5 rounded-t-ctl border border-line border-b-surface bg-surface px-3 py-1.5 text-sm font-semibold text-fg'
            : 'inline-flex shrink-0 items-center gap-1.5 rounded-t-ctl border border-transparent px-3 py-1.5 text-sm text-muted hover:text-fg'}>
          {tab.label}
        </button>
      ))}
    </div>
  )
}

export type MenuItem = {
  label: string; icon?: ReactNode; onSelect: () => void
  /** asked first, inside the menu: "Really split?" */
  confirm?: string; danger?: boolean
}

/** The "⋯" of a line as a menu of what can be done with it (Vanixxx, 2026-10-08): opening the
 * line is a click on it, so the dots hold the actions. Asks inside the menu before anything
 * that cannot simply be taken back. */
export function ActionMenu({ items }: { items: (MenuItem | false | null | undefined)[] }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [asking, setAsking] = useState<MenuItem | null>(null)
  const box = useRef<HTMLSpanElement>(null)
  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) { setOpen(false); setAsking(null) } }
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') { setOpen(false); setAsking(null) } }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', key)
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', key) }
  }, [open])
  const shown = items.filter((i): i is MenuItem => !!i)
  const pick = (i: MenuItem) => {
    if (i.confirm && asking !== i) { setAsking(i); return }
    setOpen(false); setAsking(null); i.onSelect()
  }
  return (
    <span ref={box} data-menu className="relative inline-block">
      <button type="button" aria-label={t('manual.actions')} aria-haspopup="menu" aria-expanded={open} onClick={() => { setOpen(!open); setAsking(null) }}
        className="rounded-ctl p-1.5 text-muted hover:bg-surface-2 hover:text-fg">
        <MoreHorizontal size={18} aria-hidden="true" />
      </button>
      {open && (
        <span role="menu" className="absolute right-0 top-full z-30 mt-1 grid w-64 gap-0.5 rounded-ctl border border-line bg-surface p-1.5 text-left shadow-xl">
          {asking ? (
            <span className="grid gap-2 p-2 text-sm text-fg">
              {asking.confirm}
              <span className="flex gap-2">
                <button type="button" onClick={() => pick(asking)}
                  className={cx('rounded-ctl px-3 py-1.5 text-sm font-semibold', asking.danger ? 'bg-down/15 text-down' : 'accent-fill')}>{asking.label}</button>
                <button type="button" onClick={() => setAsking(null)} className="rounded-ctl px-3 py-1.5 text-sm text-muted hover:text-fg">{t('common.cancel')}</button>
              </span>
            </span>
          ) : shown.map((i) => (
            <button key={i.label} type="button" role="menuitem" onClick={() => pick(i)}
              className={cx('flex w-full items-center gap-2.5 rounded-ctl px-2.5 py-2 text-left text-sm hover:bg-surface-2', i.danger ? 'text-down' : 'text-fg')}>
              <span className="grid w-4 place-items-center text-muted">{i.icon}</span>{i.label}
            </button>
          ))}
        </span>
      )}
    </span>
  )
}
