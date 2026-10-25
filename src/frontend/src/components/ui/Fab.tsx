import { ArrowUp } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { cx } from '../../lib/cx'

/** A round button floating over the page (Vanixxx, 2026-10-08). */
export function Fab({ label, onClick, className, children }: { label: string; onClick: () => void; className?: string; children: ReactNode }) {
  return (
    <button type="button" aria-label={label} title={label} onClick={onClick}
      className={cx('fixed z-40 grid h-12 w-12 place-items-center rounded-full shadow-xl transition-transform hover:scale-105 active:scale-95', className)}>
      {children}
    </button>
  )
}

/** Back to the top, once the page has been scrolled down a good way; above the tab bar on
 * a phone. */
export function ToTop() {
  const { t } = useTranslation()
  const [shown, setShown] = useState(false)
  useEffect(() => {
    const check = () => setShown(window.scrollY > 600)
    check()
    window.addEventListener('scroll', check, { passive: true })
    return () => window.removeEventListener('scroll', check)
  }, [])
  if (!shown) return null
  return (
    <Fab label={t('common.toTop')} onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
      className="bottom-24 right-4 border border-line bg-surface text-fg md:bottom-6 md:right-6">
      <ArrowUp size={20} aria-hidden="true" />
    </Fab>
  )
}
