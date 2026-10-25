import { LogOut, MoreHorizontal } from 'lucide-react'
import { ToTop } from '../ui/Fab'
import { useTranslation } from 'react-i18next'
import { NavLink, Outlet, useLocation } from 'react-router'
import { cx } from '../../lib/cx'
import { Brand } from '../ui'
import { CurrencySwitch } from '../CurrencySwitch'
import { useSettings } from '../../app/settings'
import { NAV } from './nav'

// Desktop: sidebar. Phone: bottom tab bar with the four main pages plus "More" (ADR 0031).
export function AppShell({ onLogout }: { onLogout: () => void }) {
  const { t } = useTranslation()
  const { pathname } = useLocation()
  const here = pathname === '/more' ? 'more'
    : NAV.find((n) => (n.to === '/' ? pathname === '/' : pathname.startsWith(n.to)))?.key
  // reload only once the server has the new currency: asked earlier, it still answers in the
  // old one (Vanixxx, 2026-10-19: switch on EUR, numbers in USD)
  const currency = useSettings().saved['general.currency']
  // pages that show money get the EUR/USD switch top right (Vanixxx, 2026-10-19)
  const money = ['dashboard', 'holdings', 'transactions', 'prices', 'stats', 'reports'].includes(here ?? '')
  // the transactions page has its round "+" button up there
  const beside = here === 'transactions'
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    cx(
      'flex items-center gap-3 rounded-ctl px-2.5 py-2.5 text-[0.92rem] no-underline',
      isActive ? 'bg-surface-2 text-fg' : 'text-muted hover:text-fg',
    )
  return (
    <div className="min-h-dvh md:grid md:grid-cols-[232px_minmax(0,1fr)]">
      <nav aria-label={t('nav.main')} className="sticky top-0 hidden h-dvh flex-col gap-1 border-r border-line px-3.5 py-5 md:flex">
        <div className="mx-2 mb-5"><Brand /></div>
        {NAV.map((item, i) => (
          <div key={item.to} className="contents">
            {i > 0 && NAV[i - 1].group !== item.group && <div className="mx-2 my-2.5 h-px bg-line" />}
            <NavLink to={item.to} end={item.to === '/'} className={linkClass}>
              <item.icon size={20} strokeWidth={1.8} aria-hidden="true" />
              {t(`nav.${item.key}`)}
              {item.soon && (
                <span className="ml-auto rounded-full border border-line px-2 text-[0.66rem] text-muted">
                  {t('nav.soon')}
                </span>
              )}
            </NavLink>
          </div>
        ))}
        <button type="button" onClick={onLogout} className={cx(linkClass({ isActive: false }), 'mt-auto border-0 bg-transparent text-left')}>
          <LogOut size={20} strokeWidth={1.8} aria-hidden="true" />
          {t('common.logout')}
        </button>
      </nav>

      <div className="min-w-0">
        <header className="flex items-center justify-between px-4 pt-4 md:hidden">
          <Brand label={here ? t(`nav.${here}`) : undefined} />
          <span className={cx('flex items-center gap-3', beside && 'mr-14')}>
            {/* a page's own buttons land here (TopBarActions) */}
            <span id="topbar-actions" className="flex items-center gap-2 empty:hidden" />
            {money && <CurrencySwitch />}
          </span>
        </header>
        <main className="mx-auto grid max-w-[1180px] content-start gap-4 px-4 pb-28 pt-4 md:gap-5 md:px-7 md:pb-10 md:pt-7">
          {/* a new currency: the page loads its numbers again */}
          <Outlet key={currency} />
        </main>
        <ToTop />
      </div>

      <nav
        aria-label={t('nav.main')}
        className="fixed inset-x-0 bottom-0 z-10 grid grid-cols-5 border-t border-line bg-[color-mix(in_srgb,var(--bg)_88%,transparent)] px-1 pt-2 backdrop-blur-md md:hidden"
        style={{ paddingBottom: 'calc(8px + env(safe-area-inset-bottom, 0px))' }}
      >
        {NAV.filter((n) => n.tab).map((item) => (
          <NavLink key={item.to} to={item.to} end={item.to === '/'} className={({ isActive }) => tabClass(isActive)}>
            <item.icon size={22} strokeWidth={1.8} aria-hidden="true" />
            {t(`nav.${item.short ?? item.key}`)}
          </NavLink>
        ))}
        <NavLink to="/more" className={({ isActive }) => tabClass(isActive)}>
          <MoreHorizontal size={22} strokeWidth={1.8} aria-hidden="true" />
          {t('nav.more')}
        </NavLink>
      </nav>
    </div>
  )
}

const tabClass = (active: boolean) =>
  cx('grid justify-items-center gap-0.5 py-1 text-[0.68rem] no-underline', active ? 'text-accent' : 'text-muted')
