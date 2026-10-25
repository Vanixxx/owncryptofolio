import type { ReactNode } from 'react'
import { cx } from '../../lib/cx'
import { money, percent, trend } from '../../lib/format'

/** One figure with its label; a P/L is coloured and signed, a percent can follow. */
export function Kpi({ label, value, currency, pl = false, pct, hint, big = false, className }: {
  label: ReactNode; value: string | null | undefined; currency: string; pl?: boolean; pct?: string | null
  hint?: ReactNode; big?: boolean; className?: string
}) {
  const dir = pl ? trend(value) : 'flat'
  return (
    <div className={cx('grid content-start gap-0.5', className)}>
      <span className="label">{label}</span>
      <span className={cx('num font-semibold tracking-tight', big ? 'text-3xl md:text-4xl' : 'text-lg',
        dir === 'up' && 'text-up', dir === 'down' && 'text-down')}>
        {money(value, currency, pl)}
      </span>
      {pct && <span className={cx('num -mt-0.5 text-xs font-medium', dir === 'up' && 'text-up', dir === 'down' && 'text-down')}>{percent(pct)}</span>}
      {hint && <span className="text-xs text-muted">{hint}</span>}
    </div>
  )
}
