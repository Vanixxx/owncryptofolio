import { useTranslation } from 'react-i18next'
import { useSettings } from '../app/settings'
import { cx } from '../lib/cx'

/** EUR or USD right where the money is shown (Vanixxx, 2026-10-19): a toggle switch between
 * the two, the same setting as in the settings; the page reloads its numbers. */
export function CurrencySwitch({ className }: { className?: string }) {
  const { t } = useTranslation()
  const { settings, update } = useSettings()
  const usd = settings['general.currency'] === 'USD'
  const set = (v: boolean) => void update({ 'general.currency': v ? 'USD' : 'EUR' })
  const side = (on: boolean) => cx('text-xs font-semibold', on ? 'text-fg' : 'text-muted')
  return (
    <span className={cx('inline-flex shrink-0 items-center gap-1.5', className)}>
      <button type="button" onClick={() => set(false)} className={cx('border-0 bg-transparent p-0', side(!usd))}>EUR</button>
      <button type="button" role="switch" aria-checked={usd} aria-label={t('settings.regional.currency')}
        onClick={() => set(!usd)}
        className="relative h-6 w-10 shrink-0 rounded-full border-0 accent-fill">
        {/* the knob in the accent's text colour: solid on every style (Vanixxx, 2026-10-21: on Neon
            the glassy knob was hard to see) */}
        <span className={cx('absolute top-0.5 h-5 w-5 rounded-full bg-[var(--accent-fg)] shadow transition-all', usd ? 'left-[18px]' : 'left-0.5')} />
      </button>
      <button type="button" onClick={() => set(true)} className={cx('border-0 bg-transparent p-0', side(usd))}>USD</button>
    </span>
  )
}
