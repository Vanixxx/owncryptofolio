import { ArrowDownWideNarrow, ArrowUpNarrowWide } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { Sort } from '../lib/sort'

/** Sort field plus direction: a select and one button that flips the order. */
export function SortSelect<K extends string>({ value, onChange, options, id }: {
  value: Sort<K>; onChange: (s: Sort<K>) => void; options: { value: K; label: string }[]; id: string
}) {
  const { t } = useTranslation()
  return (
    <span className="flex items-center gap-1">
      <label htmlFor={id} className="sr-only">{t('common.sortBy')}</label>
      <select id={id} value={value.key} onChange={(e) => onChange({ ...value, key: e.target.value as K })}
        className="rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-fg">
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <button type="button" onClick={() => onChange({ ...value, desc: !value.desc })}
        aria-label={value.desc ? t('common.descending') : t('common.ascending')} title={value.desc ? t('common.descending') : t('common.ascending')}
        className="rounded-ctl border border-line bg-surface-2 p-2 text-muted hover:text-fg">
        {value.desc ? <ArrowDownWideNarrow size={16} aria-hidden="true" /> : <ArrowUpNarrowWide size={16} aria-hidden="true" />}
      </button>
    </span>
  )
}
