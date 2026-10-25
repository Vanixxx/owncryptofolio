import { Check, ChevronDown, Search } from 'lucide-react'
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { cx } from '../../lib/cx'
import { matches } from '../../lib/search'

export type ComboOption = { value: string; label: string; hint?: string; icon?: ReactNode; group?: string
  /** nothing of it under the other filters: shown dimmed, still choosable */
  dim?: boolean }

/** A select with a search field: for long lists (coins, sources). Type to narrow, arrows and
 * Enter to choose, Esc to close. The empty value is the "all" entry on top. With `multiple`
 * the value holds several, comma-separated: choosing toggles and the list stays open
 * (Vanixxx, 2026-10-07). */
export function Combobox({ value, onChange, options, allLabel, label, className, multiple = false, noAll = false }: {
  value: string; onChange: (v: string) => void; options: ComboOption[]; allLabel: string; label: string; className?: string
  multiple?: boolean
  /** a choice is required: no "all" entry, `allLabel` is the prompt */
  noAll?: boolean
}) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const box = useRef<HTMLDivElement>(null)
  const listId = useId()
  const chosen = useMemo(() => new Set(value ? (multiple ? value.split(',') : [value]) : []), [value, multiple])
  const picked = options.filter((o) => chosen.has(o.value))
  const selected = picked[0]

  const shown = useMemo(() => {
    const found = options.filter((o) => matches(query, o.label, o.hint, o.group))
    // without groups, what fits the other filters comes first, the dimmed rest after it
    const hits = found.some((o) => o.group) ? found : [...found.filter((o) => !o.dim), ...found.filter((o) => o.dim)]
    return noAll ? hits : [{ value: '', label: allLabel } as ComboOption, ...hits]
  }, [options, query, allLabel, noAll])

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const choose = (v: string) => {
    if (!multiple || v === '') { onChange(v); setOpen(false); setQuery(''); return }
    const next = new Set(chosen)
    if (next.has(v)) next.delete(v)
    else next.add(v)
    // keep the order of the list, not of the clicks
    onChange(options.filter((o) => next.has(o.value)).map((o) => o.value).join(','))
  }
  const key = (e: KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, shown.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
    else if (e.key === 'Enter') { e.preventDefault(); if (shown[active]) choose(shown[active].value) }
    else if (e.key === 'Escape') { setOpen(false) }
  }

  return (
    <div ref={box} className={cx('min-w-0 md:relative', className)}>
      <button type="button" aria-label={label} aria-haspopup="listbox" aria-expanded={open}
        onClick={() => { setOpen(!open); setActive(0) }}
        className="flex w-full min-w-0 items-center gap-2 rounded-ctl border border-line bg-surface-2 px-3 py-2 text-left text-sm text-fg">
        {selected?.icon}
        <span className="min-w-0 flex-1 truncate">{selected ? selected.label : allLabel}</span>
        {picked.length > 1 && <span className="shrink-0 rounded-full bg-accent/20 px-1.5 text-xs font-semibold text-accent">+{picked.length - 1}</span>}
        <ChevronDown size={16} aria-hidden="true" className="shrink-0 text-muted" />
      </button>
      {open && (
        <div className="absolute inset-x-0 z-30 mt-1 grid gap-1 rounded-ctl border border-line bg-surface p-1.5 shadow-xl md:right-auto md:min-w-64">
          <label className="flex items-center gap-2 rounded-ctl bg-surface-2 px-2.5">
            <Search size={14} aria-hidden="true" className="text-muted" />
            <input autoFocus value={query} onChange={(e) => { setQuery(e.target.value); setActive(0) }} onKeyDown={key}
              placeholder={t('common.search')} aria-label={t('common.search')} aria-controls={listId} spellCheck={false}
              className="w-full border-0 bg-transparent py-2 text-base text-fg outline-none md:text-sm" />
          </label>
          <ul id={listId} role="listbox" aria-label={label} aria-multiselectable={multiple || undefined} className="m-0 max-h-72 list-none overflow-y-auto p-0">
            {shown.length === (noAll ? 0 : 1) && query && <li className="px-2.5 py-2 text-sm text-muted">{t('common.noMatch')}</li>}
            {shown.map((o, i) => {
              const head = o.group && !query && o.group !== shown[i - 1]?.group ? o.group : null
              return (
                <li key={o.value || '__all'} role="presentation">
                  {head && <div className="label px-2.5 pb-1 pt-2">{head}</div>}
                  <button type="button" role="option" aria-selected={o.value === '' ? chosen.size === 0 : chosen.has(o.value)} onMouseEnter={() => setActive(i)} onClick={() => choose(o.value)}
                    className={cx('flex w-full items-center gap-2 rounded-ctl border-0 px-2.5 py-1.5 text-left text-sm text-fg',
                      i === active ? 'bg-surface-2' : 'bg-transparent', o.dim && 'opacity-40')}>
                    {o.icon}
                    <span className="min-w-0 flex-1 truncate">{o.label}</span>
                    {o.hint && <span className="truncate text-xs text-muted">{o.hint}</span>}
                    {(o.value === '' ? chosen.size === 0 : chosen.has(o.value)) && <Check size={14} aria-hidden="true" className="text-accent" />}
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </div>
  )
}
