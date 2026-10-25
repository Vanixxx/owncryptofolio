import { Search, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'

/** A small search box for lists that filter as you type. */
export function SearchField({ value, onChange, placeholder, className }: {
  value: string; onChange: (v: string) => void; placeholder?: string; className?: string
}) {
  const { t } = useTranslation()
  return (
    <label className={`flex items-center gap-2 rounded-ctl border border-line bg-surface-2 px-3 ${className ?? ''}`}>
      <Search size={15} aria-hidden="true" className="shrink-0 text-muted" />
      <input type="search" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder ?? t('common.search')}
        aria-label={placeholder ?? t('common.search')} spellCheck={false}
        className="w-full min-w-0 border-0 bg-transparent py-2 text-base text-fg outline-none md:text-sm [&::-webkit-search-cancel-button]:hidden" />
      {value && (
        <button type="button" onClick={() => onChange('')} aria-label={t('common.clear')} className="rounded p-0.5 text-muted hover:text-fg">
          <X size={14} aria-hidden="true" />
        </button>
      )}
    </label>
  )
}
