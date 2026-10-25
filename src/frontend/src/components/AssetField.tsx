import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { api, type CoinOption } from '../lib/api'
import { matches } from '../lib/search'
import { cx } from '../lib/cx'
import { CoinIcon } from './CoinIcon'

let known: Promise<CoinOption[]> | null = null
/** Every coin of the data once per page load; the form opens often. */
function coins() {
  known ??= api.mergedAssets().catch(() => [])
  return known
}

/** A coin field (Vanixxx, 2026-10-08): pick from the known coins with a search, or type any
 * symbol — a coin not in the data yet is fine. The coin's icon stands in front. */
export function AssetField({ id, label, value, onChange, required, placeholder, extra = [] }: {
  id: string; label: string; value: string; onChange: (v: string) => void; required?: boolean; placeholder?: string
  /** offered first, e.g. EUR and USD for fiat */
  extra?: string[]
}) {
  const [list, setList] = useState<CoinOption[]>([])
  const [open, setOpen] = useState(false)
  // the list filters by what is typed now, not by a value already there (a copy, an edit)
  const [typed, setTyped] = useState(false)
  const [active, setActive] = useState(0)
  const box = useRef<HTMLDivElement>(null)
  const listId = useId()
  useEffect(() => { void coins().then(setList) }, [])
  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const options = useMemo(() => {
    const all: CoinOption[] = [
      ...extra.map((a) => ({ asset: a, name: null, icon: a })),
      ...list.filter((c) => !extra.includes(c.asset)),
    ]
    const q = typed ? value.trim() : ''
    return (q ? all.filter((c) => matches(q, c.asset, c.name)) : all).slice(0, 50)
  }, [list, extra, value, typed])
  const icon = list.find((c) => c.asset === value.toUpperCase())?.icon ?? value.toUpperCase()

  const choose = (a: string) => { onChange(a); setOpen(false) }
  const key = (e: KeyboardEvent) => {
    if (!open && e.key === 'ArrowDown') { setOpen(true); return }
    if (!open) return
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, options.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
    else if (e.key === 'Enter' && options[active]) { e.preventDefault(); choose(options[active].asset) }
    else if (e.key === 'Escape') setOpen(false)
  }

  return (
    <div ref={box} className="relative grid gap-1.5">
      <label htmlFor={id} className="label">{label}</label>
      <span className="flex items-center gap-2 rounded-ctl border border-line bg-surface-2 px-3 focus-within:border-accent">
        {value.trim() ? <CoinIcon asset={icon} size={20} /> : <span className="h-5 w-5 shrink-0 rounded-full border border-dashed border-line" aria-hidden="true" />}
        <input id={id} value={value} required={required} placeholder={placeholder} autoCapitalize="characters" autoComplete="off" spellCheck={false}
          role="combobox" aria-expanded={open} aria-controls={listId} aria-autocomplete="list"
          onChange={(e) => { onChange(e.target.value.toUpperCase()); setTyped(true); setOpen(true); setActive(0) }}
          onFocus={() => { setTyped(false); setOpen(true) }} onKeyDown={key}
          className="w-full min-w-0 border-0 bg-transparent py-2.5 text-base text-fg outline-none" />
      </span>
      {open && options.length > 0 && (
        <ul id={listId} role="listbox" aria-label={label}
          className="absolute inset-x-0 top-full z-30 m-0 mt-1 max-h-64 list-none overflow-y-auto rounded-ctl border border-line bg-surface p-1.5 shadow-xl">
          {options.map((c, i) => (
            <li key={c.asset} role="presentation">
              <button type="button" role="option" aria-selected={c.asset === value} onMouseEnter={() => setActive(i)}
                onMouseDown={(e) => e.preventDefault()} onClick={() => choose(c.asset)}
                className={cx('flex w-full items-center gap-2 rounded-ctl border-0 px-2.5 py-1.5 text-left text-sm text-fg', i === active ? 'bg-surface-2' : 'bg-transparent')}>
                <CoinIcon asset={c.icon} size={18} />
                <span className="font-semibold">{c.asset}</span>
                {c.name && <span className="min-w-0 truncate text-xs text-muted">{c.name}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
