import { ChevronRight, LogOut } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { NAV } from '../components/layout/nav'
import { PageHeader } from '../components/ui'

/** Phone only: everything that does not fit into the tab bar. */
export function More({ onLogout }: { onLogout: () => void }) {
  const { t } = useTranslation()
  const row = 'flex items-center gap-3 border-t border-line px-1 py-3.5 text-fg no-underline first:border-t-0'
  return (
    <>
      <PageHeader title={t('pages.more.title')} />
      <div className="card grid gap-0 py-1">
        {NAV.filter((n) => !n.tab).map((item) => (
          <Link key={item.to} to={item.to} className={row}>
            <item.icon size={20} strokeWidth={1.8} className="text-muted" aria-hidden="true" />
            <span className="flex-1">{t(`nav.${item.key}`)}</span>
            <ChevronRight size={18} className="text-muted" aria-hidden="true" />
          </Link>
        ))}
        <button type="button" onClick={onLogout} className={`${row} border-x-0 border-b-0 bg-transparent text-left`}>
          <LogOut size={20} strokeWidth={1.8} className="text-muted" aria-hidden="true" />
          <span className="flex-1">{t('common.logout')}</span>
        </button>
      </div>
    </>
  )
}
