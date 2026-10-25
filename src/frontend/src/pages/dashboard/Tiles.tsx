import { ArrowRight } from 'lucide-react'
import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { CoinIcon } from '../../components/CoinIcon'
import { Card, Segmented } from '../../components/ui'
import { api, type Holding, type Source, type Wallet } from '../../lib/api'
import { cx } from '../../lib/cx'
import { date, money, percent, quantity, trend } from '../../lib/format'

const Allocation = lazy(() => import('./Charts').then((m) => ({ default: m.Allocation })))
const SLICES = 7

/** Where the money sits (ADR 0043): per coin, or per exchange and wallet — a wallet's
 * networks together, coins outside apart. */
export function AllocationCard({ items, currency }: { items: Holding[]; currency: string }) {
  const { t } = useTranslation()
  const [by, setBy] = useState<'coin' | 'place'>(() => {
    try { return localStorage.getItem('dash-allocation') === 'place' ? 'place' : 'coin' } catch { return 'coin' }
  })
  const pick = (v: 'coin' | 'place') => { setBy(v); try { localStorage.setItem('dash-allocation', v) } catch { /* private mode */ } }
  const [places, setPlaces] = useState<{ sources: Source[]; wallets: Wallet[] } | null>(null)
  useEffect(() => {
    if (by !== 'place' || places) return
    Promise.all([api.sources(), api.wallets()]).then(([sources, wallets]) => setPlaces({ sources, wallets }), () => {})
  }, [by, places])
  const slices = useMemo(() => {
    const sum = new Map<string, number>()
    if (by === 'coin') {
      for (const i of items) if (!i.fiat && Number(i.value) > 0) sum.set(i.asset, Number(i.value))
    } else if (places) {
      const nameOf = (id: number | null, outside: boolean) => {
        if (outside || id === null) return t('holdings.outside')
        const s = places.sources.find((x) => x.id === id)
        const w = places.wallets.find((x) => x.id === s?.wallet_id)
        return w?.name ?? s?.label ?? `#${id}`
      }
      for (const i of items) {
        const value = Number(i.value), qty = Number(i.qty)
        if (!(value > 0) || !(qty > 0)) continue
        for (const p of i.places) {
          const share = Number(p.qty) / qty
          if (share <= 0) continue
          const k = nameOf(p.source_id, p.outside)
          sum.set(k, (sum.get(k) ?? 0) + value * share)
        }
      }
    }
    const all = [...sum].map(([asset, value]) => ({ asset, value })).sort((a, b) => b.value - a.value)
    const rest = all.slice(SLICES).reduce((n, c) => n + c.value, 0)
    return rest > 0 ? [...all.slice(0, SLICES), { asset: t('dashboard.rest'), value: rest }] : all.slice(0, SLICES)
  }, [items, by, places, t])
  return (
    <Card title={t('dashboard.allocation')} action={
      <Link to="/holdings" className="inline-flex items-center gap-1 text-xs text-accent no-underline">{t('dashboard.toHoldings')}<ArrowRight size={13} aria-hidden="true" /></Link>
    }>
      <Segmented label={t('dashboard.allocation')} value={by} onChange={pick}
        options={[{ value: 'coin', label: t('dashboard.byCoin') }, { value: 'place', label: t('dashboard.byPlace') }]} />
      {slices.length > 0 ? (
        <Suspense fallback={<div className="h-40" />}>
          <Allocation slices={slices} currency={currency} />
        </Suspense>
      ) : <div className="h-40" />}
    </Card>
  )
}

/** The five coins furthest up and down against what they cost (unrealized). */
export function MoversCard({ items, currency }: { items: Holding[]; currency: string }) {
  const { t } = useTranslation()
  const held = items.filter((i) => !i.fiat && i.unrealized !== null && Number(i.qty) > 0)
    .sort((a, b) => Number(b.unrealized) - Number(a.unrealized))
  const up = held.filter((i) => Number(i.unrealized) > 0).slice(0, 5)
  const down = held.filter((i) => Number(i.unrealized) < 0).slice(-5).reverse()
  const row = (i: Holding) => {
    const dir = trend(i.unrealized)
    return (
      <li key={i.asset} className="flex items-center justify-between gap-2 text-sm">
        <span className="flex min-w-0 items-center gap-2"><CoinIcon asset={i.icon} size={20} /><b className="truncate">{i.asset}</b></span>
        <span className={cx('num shrink-0 text-right', dir === 'up' && 'text-up', dir === 'down' && 'text-down')}>
          {money(i.unrealized, currency, true)} <span className="text-xs">{percent(i.unrealized_pct)}</span>
        </span>
      </li>
    )
  }
  return (
    <Card title={t('dashboard.movers.title')}>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="grid content-start gap-2">
          <span className="label">{t('dashboard.movers.up')}</span>
          {up.length ? <ul className="m-0 grid list-none gap-1.5 p-0">{up.map(row)}</ul> : <span className="text-sm text-muted">—</span>}
        </div>
        <div className="grid content-start gap-2">
          <span className="label">{t('dashboard.movers.down')}</span>
          {down.length ? <ul className="m-0 grid list-none gap-1.5 p-0">{down.map(row)}</ul> : <span className="text-sm text-muted">—</span>}
        </div>
      </div>
      <p className="m-0 text-xs text-muted">{t('dashboard.movers.hint')}</p>
    </Card>
  )
}

/** What turns tax-free in the next 30 days (ADR 0043): worth waiting for before a sale. */
export function TaxSoonCard({ currency }: { currency: string }) {
  const { t } = useTranslation()
  const [soon, setSoon] = useState<{ asset: string; free_on: string; qty: string; value: string | null; gain: string | null }[] | null>(null)
  useEffect(() => { api.taxUpcoming(30).then(setSoon, () => setSoon([])) }, [])
  const value = (soon ?? []).reduce((n, s) => n + Number(s.value ?? 0), 0)
  const gain = (soon ?? []).reduce((n, s) => n + Number(s.gain ?? 0), 0)
  return (
    <Card title={t('dashboard.taxSoon.title')} action={
      <Link to="/reports" className="inline-flex items-center gap-1 text-xs text-accent no-underline">{t('dashboard.taxSoon.toReports')}<ArrowRight size={13} aria-hidden="true" /></Link>
    }>
      {soon === null ? <div className="h-16" /> : soon.length === 0 ? (
        <p className="m-0 text-sm text-muted">{t('dashboard.taxSoon.none')}</p>
      ) : (
        <>
          <p className="m-0 text-sm">
            {t('dashboard.taxSoon.sum', { value: money(String(value), currency) })}{' '}
            <span className={cx('num', trend(String(gain)) === 'up' ? 'text-up' : trend(String(gain)) === 'down' ? 'text-down' : '')}>
              ({t('dashboard.taxSoon.gain', { gain: money(String(gain), currency, true) })})
            </span>
          </p>
          <ul className="m-0 grid list-none gap-1.5 p-0">
            {soon.slice(0, 6).map((s) => (
              <li key={`${s.asset}${s.free_on}`} className="flex items-center justify-between gap-2 text-sm">
                <span className="flex min-w-0 items-center gap-2">
                  <span className="num w-20 shrink-0 text-xs text-muted">{date(s.free_on)}</span>
                  <b className="truncate">{quantity(s.qty)} {s.asset}</b>
                </span>
                <span className="num shrink-0">{money(s.value, currency)}</span>
              </li>
            ))}
          </ul>
          {soon.length > 6 && <span className="text-xs text-muted">{t('dashboard.taxSoon.more', { count: soon.length - 6 })}</span>}
        </>
      )}
    </Card>
  )
}
