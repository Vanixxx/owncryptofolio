import { ArrowRight } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { Card, ErrorText } from '../../components/ui'
import { api, type FuturesPosition, type PortfolioSummary } from '../../lib/api'
import { cx } from '../../lib/cx'
import { dateTime, money, quantity, trend } from '../../lib/format'
import { useErrorText } from '../../lib/useErrorText'
import { Kpi } from './Kpi'

/** Futures on the holdings page (ADR 0029, 0040): the result apart from spot and the
 * positions still open. Closed ones are grouped in the transactions. */
export function FuturesList({ summary: s, name, tz }: { summary: PortfolioSummary; name: (id: number) => string; tz: string }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [positions, setPositions] = useState<FuturesPosition[] | null>(null)
  const [error, setError] = useState<unknown>(null)
  useEffect(() => void api.futuresPositions().then(setPositions, setError), [])
  // only what is still running belongs to the holdings; closed positions are transactions
  const open = (positions ?? []).filter((p) => p.open)

  return (
    <>
      <Card>
        <div className="grid grid-cols-2 gap-x-4 gap-y-3 md:grid-cols-4">
          <Kpi label={t('holdings.futures.result')} value={s.futures.result} currency={s.currency} pl />
          <Kpi label={t('holdings.futures.pnl')} value={s.futures.pnl} currency={s.currency} pl />
          <Kpi label={t('holdings.futures.funding')} value={s.futures.funding} currency={s.currency} pl />
          <Kpi label={t('holdings.futures.fees')} value={s.futures.fees} currency={s.currency} />
        </div>
        <p className="m-0 text-xs leading-relaxed text-muted">{t('holdings.futures.hint')}</p>
      </Card>
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
      {positions === null ? (
        <p className="text-sm text-muted">{t('common.loading')}</p>
      ) : open.length === 0 ? (
        <Card>
          <p className="m-0 text-sm text-muted">{t('holdings.futures.noneOpen')}</p>
          {positions.length > 0 && (
            <Link to="/transactions?kind=futures_position" className="inline-flex items-center gap-1 justify-self-start text-sm text-accent no-underline">
              {t('holdings.futures.toClosed', { count: positions.length })}<ArrowRight size={14} aria-hidden="true" />
            </Link>
          )}
        </Card>
      ) : (
        <>
          <p className="m-0 text-xs leading-relaxed text-muted">{t('holdings.futures.openHint')}</p>
          <ul className="m-0 grid list-none gap-2 p-0">
            {open.map((p) => <Position key={`${p.source_id}${p.instrument}${p.closed}`} p={p} currency={s.currency} name={name} tz={tz} />)}
          </ul>
        </>
      )}
    </>
  )
}

function Position({ p, currency, name, tz, inner = false }: {
  p: FuturesPosition; currency: string; name: (id: number) => string; tz: string; inner?: boolean
}) {
  const { t } = useTranslation()
  const dir = trend(p.result)
  return (
    <li className={cx('grid gap-1.5', inner ? 'rounded-ctl bg-surface-2 p-2.5' : 'card p-3')}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="flex min-w-0 items-baseline gap-2">
          <b className="truncate">{p.instrument}</b>
          {p.side && (
            <span className={cx('rounded-full px-2 py-0.5 text-[0.7rem] font-semibold uppercase',
              p.side === 'long' ? 'bg-up/15 text-up' : 'bg-down/15 text-down')}>{t(`holdings.futures.${p.side}`)}</span>
          )}
        </span>
        <span className={cx('num text-sm font-semibold', dir === 'up' && 'text-up', dir === 'down' && 'text-down')}>
          {dir === 'up' && '+'}{quantity(p.result)} {p.coin}
        </span>
      </div>
      <div className="flex flex-wrap justify-between gap-x-3 gap-y-0.5 text-xs text-muted">
        <span>{name(p.source_id)} · {dateTime(p.opened, tz)} → {dateTime(p.closed, tz)}</span>
        <span className="num">{money(p.result_value, currency, true)}</span>
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted">
        {p.entry && <span className="num">{t('holdings.futures.entryExit', { entry: quantity(p.entry), exit: quantity(p.exit) })}</span>}
        <span className="num">{t('holdings.futures.parts', { pnl: quantity(p.pnl), funding: quantity(p.funding), fees: quantity(p.fees) })}</span>
        {!p.known && <span>{t('holdings.futures.unknown', { count: p.flows })}</span>}
      </div>
    </li>
  )
}
