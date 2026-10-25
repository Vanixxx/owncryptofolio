import { Fragment, lazy, Suspense, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { Card, ErrorText, PageHeader, Segmented } from '../../components/ui'
import { api, type HistoryPoint, type StatsData } from '../../lib/api'
import { cx } from '../../lib/cx'
import { money, percent } from '../../lib/format'
import { locale } from '../../i18n'
import { useErrorText } from '../../lib/useErrorText'
import { CurrencySwitch } from '../../components/CurrencySwitch'
import { Kpi } from '../holdings/Kpi'

const Bars = lazy(() => import('./StatsCharts').then((m) => ({ default: m.Bars })))
const Lines = lazy(() => import('./StatsCharts').then((m) => ({ default: m.Lines })))
const Ring = lazy(() => import('./StatsCharts').then((m) => ({ default: m.Ring })))

/** Statistics (ADR 0043): returns per month and year, everything-in-BTC, fees, income,
 * futures and activity. */
export function Stats() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [data, setData] = useState<StatsData | null>(null)
  const [history, setHistory] = useState<HistoryPoint[] | null>(null)
  const [error, setError] = useState<unknown>(null)
  useEffect(() => {
    api.stats().then(setData, setError)
    api.portfolioHistory().then(setHistory, setError)
  }, [])
  const cur = data?.currency ?? 'EUR'
  return (
    <>
      <PageHeader title={t('pages.stats.title')} subtitle={t('pages.stats.subtitle')} aside={<CurrencySwitch />} />
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
      {!data || !history ? <p className="text-sm text-muted">{t('common.loading')}</p> : (
        <div className="grid gap-4 md:gap-5">
          <Health data={data} />
          <Returns history={history} currency={cur} />
          <Benchmark history={history} data={data} currency={cur} />
          <div className="grid gap-4 md:grid-cols-2 md:gap-5">
            <Spot data={data} currency={cur} />
            <Futures data={data} currency={cur} />
            <Fees data={data} currency={cur} />
            <Incomes data={data} currency={cur} />
            <Activity data={data} currency={cur} />
          </div>
        </div>
      )}
    </>
  )
}

const Chart = ({ children }: { children: ReactNode }) => <Suspense fallback={<div className="h-56 md:h-64" />}>{children}</Suspense>

function monthLabel(m: string) {
  return new Intl.DateTimeFormat(locale(), { month: 'short', year: '2-digit', timeZone: 'UTC' }).format(new Date(`${m}-01T00:00:00Z`))
}

/** Every month from the first to the last, so gaps show as gaps. */
function monthsBetween(first: string, last: string): string[] {
  const out: string[] = []
  let [y, m] = first.split('-').map(Number)
  const [ly, lm] = last.split('-').map(Number)
  while (y < ly || (y === ly && m <= lm)) {
    out.push(`${y}-${String(m).padStart(2, '0')}`)
    m += 1
    if (m > 12) { m = 1; y += 1 }
  }
  return out
}

type Period = { gain: number; pct: number | null }

/** Gain of a stretch without money paid in or out: end − start − deposits, against what
 * was at stake (start plus what was paid in). */
function period(start: HistoryPoint, end: HistoryPoint): Period {
  const v0 = Number(start.value), v1 = Number(end.value)
  const d = Number(end.deposited) - Number(start.deposited)
  const gain = v1 - v0 - d
  const stake = v0 + Math.max(d, 0)
  return { gain, pct: stake > 0 ? (gain / stake) * 100 : null }
}

function Returns({ history, currency }: { history: HistoryPoint[]; currency: string }) {
  const { t } = useTranslation()
  const [show, setShow] = useState<'pct' | 'eur'>('pct')
  const { years, cells } = useMemo(() => {
    const lastOf = new Map<string, HistoryPoint>()
    for (const h of history) { lastOf.set(h.day.slice(0, 7), h); lastOf.set(h.day.slice(0, 4), h) }
    const first = history[0]
    const cells = new Map<string, Period>()
    const years = [...new Set(history.map((h) => h.day.slice(0, 4)))]
    for (const y of years) {
      for (let m = 1; m <= 12; m++) {
        const key = `${y}-${String(m).padStart(2, '0')}`
        const end = lastOf.get(key)
        if (!end) continue
        const prevKey = m === 1 ? `${Number(y) - 1}-12` : `${y}-${String(m - 1).padStart(2, '0')}`
        cells.set(key, period(lastOf.get(prevKey) ?? first, end))
      }
      const end = lastOf.get(y)
      if (end) cells.set(y, period(lastOf.get(String(Number(y) - 1)) ?? first, end))
    }
    return { years: years.reverse(), cells }
  }, [history])
  const monthNames = Array.from({ length: 12 }, (_, i) => new Intl.DateTimeFormat(locale(), { month: 'short', timeZone: 'UTC' }).format(new Date(Date.UTC(2024, i, 1))))
  const cell = (p: Period | undefined, bold = false) => {
    if (!p) return <td className="px-1.5 py-1.5" />
    const v = show === 'pct' ? p.pct : p.gain
    const strength = p.pct === null ? 0 : Math.min(1, Math.abs(p.pct) / 30)
    const bg = p.pct === null || p.pct === 0 ? undefined : `color-mix(in srgb, var(${p.pct > 0 ? '--up' : '--down'}) ${Math.round(12 + strength * 50)}%, transparent)`
    return (
      <td className={cx('num whitespace-nowrap rounded px-1.5 py-1.5 text-right text-xs', bold && 'font-semibold')} style={{ background: bg }}>
        {v === null ? '—' : show === 'pct' ? percent(v.toFixed(1)) : money(String(Math.round(v)), currency, true).replace(/,00(?=\s|$)/, '')}
      </td>
    )
  }
  return (
    <Card title={t('stats.returns.title')} action={
      <Segmented label={t('stats.returns.title')} value={show} onChange={setShow}
        options={[{ value: 'pct', label: '%' }, { value: 'eur', label: currency === 'USD' ? '$' : '€' }]} />
    }>
      <div className="-mx-1 overflow-x-auto">
        <table className="w-full border-separate border-spacing-0.5 text-sm">
          <thead>
            <tr className="label">
              <th className="px-1.5 py-1 text-left font-normal" />
              {/* the year right after its name: on the phone it is seen without scrolling */}
              <th className="px-1.5 py-1 text-right font-normal">{t('stats.returns.year')}</th>
              {monthNames.map((m) => <th key={m} className="px-1.5 py-1 text-right font-normal">{m}</th>)}
            </tr>
          </thead>
          <tbody>
            {years.map((y) => (
              <tr key={y}>
                <th className="num px-1.5 py-1 text-left text-xs font-semibold">{y}</th>
                {cell(cells.get(y), true)}
                {monthNames.map((_, i) => <Fragment key={i}>{cell(cells.get(`${y}-${String(i + 1).padStart(2, '0')}`))}</Fragment>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="m-0 text-xs text-muted">{t('stats.returns.hint')}</p>
    </Card>
  )
}

function Benchmark({ history, data, currency }: { history: HistoryPoint[]; data: StatsData; currency: string }) {
  const { t } = useTranslation()
  const bench = data.benchmark
  if (!bench.length) return null
  const from = new Date(`${bench[0].day}T00:00:00Z`).getTime()
  const ms = (d: string) => new Date(`${d}T00:00:00Z`).getTime()
  const mine = history.filter((h) => ms(h.day) >= from)
  const now = Number(mine[mine.length - 1]?.value ?? 0), btc = Number(bench[bench.length - 1].value ?? 0)
  return (
    <Card title={t('stats.benchmark.title')}>
      <div className="grid grid-cols-2 gap-x-4 gap-y-3 md:grid-cols-3">
        <Kpi label={t('stats.benchmark.mine')} value={String(now)} currency={currency} />
        <Kpi label={t('stats.benchmark.btc')} value={String(btc)} currency={currency} />
        <Kpi label={t('stats.benchmark.diff')} value={String(now - btc)} currency={currency} pl />
      </div>
      <Chart>
        <Lines currency={currency} label={t('stats.benchmark.title')} series={[
          { name: t('stats.benchmark.mine'), points: mine.map((h) => [ms(h.day), Number(h.value)]) },
          { name: t('stats.benchmark.btc'), points: bench.map((b) => [ms(b.day), Number(b.value)]), color: '#f5a524' },
          { name: t('dashboard.deposited'), points: mine.map((h) => [ms(h.day), Number(h.deposited)]), dashed: true, color: 'var(--muted)' },
        ]} />
      </Chart>
      <p className="m-0 text-xs text-muted">{t('stats.benchmark.hint')}</p>
    </Card>
  )
}

const HEALTH_COLORS: Record<string, string> = {
  gaps: '#f31260', balances: '#f5a524', open: '#a855f7', short: '#ef4444', other: '#3b82f6', unvalued: '#94a3b8', card: '#eab308', changed: '#f97316', fetch: '#17c964',
}

/** How sound the data is (ADR 0043): every open point by kind, each linking to where it is
 * fixed. A green ring when nothing is open. Phone: a small ring beside the verdict, a row per open
 * point and chips for the clean ones; PC: the total inside the ring and a tile per point (Vanixxx, 2026-10-24). */
function Health({ data }: { data: StatsData }) {
  const { t } = useTranslation()
  const total = data.health.reduce((n, h) => n + h.count, 0)
  const open = data.health.filter((h) => h.count)
  const clean = data.health.filter((h) => !h.count)
  const tile = 'md:rounded-lg md:border md:border-line md:bg-surface-2 md:px-3 md:py-2'
  // phone: the clean points and the hint only after a tap on the card (Vanixxx, 2026-10-24)
  const [more, setMore] = useState(false)
  return (
    <Card title={t('stats.health.title')}>
      <div className="grid gap-3 md:contents" onClick={() => setMore((m) => !m)}>
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:gap-6">
        <div className="flex items-center gap-3 md:contents">
          <div className="relative grid shrink-0 place-items-center">
            <Suspense fallback={<div className="h-12 w-12 md:h-32 md:w-32" />}>
              <Ring className="h-12 w-12 md:h-32 md:w-32" label={t('stats.health.title')} slices={data.health.map((h) => ({ name: t(`stats.health.${h.key}`), value: h.count, color: HEALTH_COLORS[h.key] }))} />
            </Suspense>
            <span className={cx('num pointer-events-none absolute hidden text-3xl font-semibold md:block', total ? 'text-warn' : 'text-up')}>{total || '✓'}</span>
          </div>
          <b className={cx('text-sm md:hidden', total ? 'text-warn' : 'text-up')}>{total ? t('stats.health.someOpen', { count: total }) : t('stats.health.allGood')}</b>
        </div>
        <div className="grid min-w-0 flex-1 gap-2 text-sm">
          <b className={cx('hidden md:block', total ? 'text-warn' : 'text-up')}>{total ? t('stats.health.someOpen', { count: total }) : t('stats.health.allGood')}</b>
          {open.length > 0 && (
            <ul className="m-0 grid list-none divide-y divide-line p-0 md:grid-cols-3 md:gap-2 md:divide-y-0">
              {open.map((h) => (
                <li key={h.key} className={cx('grid gap-0.5 py-1.5', tile)}>
                  <span className="flex items-center gap-2">
                    <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: HEALTH_COLORS[h.key] }} aria-hidden="true" />
                    <Link to={h.to} className="min-w-0 flex-1 truncate text-fg no-underline hover:text-accent">{t(`stats.health.${h.key}`)}</Link>
                    <span className="num font-semibold">{h.count}</span>
                  </span>
                  {/* the coins without a price, each straight to its price (Vanixxx, 2026-10-22) */}
                  {h.assets && (
                    <span className="flex flex-wrap gap-x-2 pl-4 text-xs">
                      {h.assets.map((a) => <Link key={a} to={`/prices?asset=${encodeURIComponent(a)}`} className="text-accent no-underline">{a}</Link>)}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
          {/* clean points: small chips on the phone, quiet tiles on the PC */}
          <button type="button" aria-expanded={more} className={cx('cursor-pointer self-start border-0 bg-transparent p-0 text-left text-xs text-muted md:hidden', more && 'hidden')}>
            {t('stats.health.cleanMore', { count: clean.length })} ▾
          </button>
          <ul className={cx('m-0 list-none flex-wrap gap-1.5 p-0 md:grid md:grid-cols-3 md:gap-2', more ? 'flex' : 'hidden')}>
            {clean.map((h) => (
              <li key={h.key} className={cx('flex items-center gap-1.5 rounded-full bg-surface-2 px-2 py-0.5 text-xs text-muted md:gap-2 md:text-sm', tile)}>
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-up md:h-2 md:w-2" aria-hidden="true" />
                <span className="min-w-0 flex-1 truncate">{t(`stats.health.${h.key}`)}</span>
                <span className="num hidden opacity-60 md:inline">0</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <p className={cx('m-0 text-xs text-muted md:block', !more && 'hidden')}>{t('stats.health.hint')}</p>
      </div>
    </Card>
  )
}

function Spot({ data, currency }: { data: StatsData; currency: string }) {
  const { t } = useTranslation()
  const s = data.spot
  const months = s.months.length ? monthsBetween(s.months[0].month, s.months[s.months.length - 1].month) : []
  return (
    <Card title={t('stats.spot.title')}>
      <div className="grid grid-cols-2 gap-x-4 gap-y-3">
        <Kpi label={t('holdings.realized')} value={s.realized} currency={currency} pl />
        <Kpi label={t('holdings.unrealized')} value={s.unrealized} currency={currency} pl />
        <div className="grid content-start gap-0.5">
          <span className="label">{t('stats.spot.winRate')}</span>
          <span className="num text-lg font-semibold">{s.sales ? `${Math.round((s.wins / s.sales) * 100)} %` : '—'}</span>
          <span className="text-xs text-muted">{t('stats.spot.of', { wins: s.wins, count: s.sales })}</span>
        </div>
        <Kpi label={t('dashboard.income')} value={s.income} currency={currency} />
        <Kpi label={t('stats.spot.best')} value={s.best} currency={currency} pl />
        <Kpi label={t('stats.spot.worst')} value={s.worst} currency={currency} pl />
      </div>
      {months.length > 0 && (
        <Chart>
          <Bars currency={currency} label={t('stats.spot.title')} categories={months.map(monthLabel)} series={[{
            name: t('stats.spot.gain'), data: months.map((m) => Number(s.months.find((x) => x.month === m)?.gain ?? 0) || null),
          }]} />
        </Chart>
      )}
      <p className="m-0 text-xs text-muted">{t('stats.spot.hint')}</p>
    </Card>
  )
}

function Fees({ data, currency }: { data: StatsData; currency: string }) {
  const { t } = useTranslation()
  const years = [...new Set(data.fees.map((f) => String(f.year)))]
  const places = [...new Set(data.fees.map((f) => f.place ?? t('holdings.outside')))]
  const total = data.fees.reduce((n, f) => n + Number(f.value), 0)
  return (
    <Card title={t('stats.fees.title')}>
      <Kpi label={t('stats.fees.total')} value={String(total)} currency={currency} />
      <Chart>
        <Bars currency={currency} label={t('stats.fees.title')} categories={years} series={places.map((p) => ({
          name: p, stack: 'f',
          data: years.map((y) => data.fees.filter((f) => String(f.year) === y && (f.place ?? t('holdings.outside')) === p).reduce((n, f) => n + Number(f.value), 0) || null),
        }))} />
      </Chart>
      <p className="m-0 text-xs text-muted">{t('stats.fees.hint')}</p>
    </Card>
  )
}

function Incomes({ data, currency }: { data: StatsData; currency: string }) {
  const { t } = useTranslation()
  if (!data.incomes.length) return <Card title={t('stats.incomes.title')}><p className="m-0 text-sm text-muted">{t('stats.none')}</p></Card>
  const months = monthsBetween(data.incomes[0].month, data.incomes[data.incomes.length - 1].month)
  const kinds = [...new Set(data.incomes.map((i) => i.kind))]
  const total = data.incomes.reduce((n, i) => n + Number(i.value), 0)
  return (
    <Card title={t('stats.incomes.title')}>
      <Kpi label={t('stats.incomes.total')} value={String(total)} currency={currency} />
      <Chart>
        <Bars currency={currency} label={t('stats.incomes.title')} categories={months.map(monthLabel)} series={kinds.map((k) => ({
          name: t(`tax.income.${k}`, { defaultValue: k }), stack: 'i',
          data: months.map((m) => data.incomes.filter((i) => i.month === m && i.kind === k).reduce((n, i) => n + Number(i.value), 0) || null),
        }))} />
      </Chart>
    </Card>
  )
}

function Futures({ data, currency }: { data: StatsData; currency: string }) {
  const { t } = useTranslation()
  const f = data.futures
  if (!f.months.length) return <Card title={t('stats.futures.title')}><p className="m-0 text-sm text-muted">{t('stats.none')}</p></Card>
  const months = monthsBetween(f.months[0].month, f.months[f.months.length - 1].month)
  const at = (m: string) => f.months.find((x) => x.month === m)
  const net = f.months.reduce((n, x) => n + Number(x.net), 0)
  const series = (['pnl', 'funding', 'fees', 'bonus'] as const).map((k) => ({
    name: t(`stats.futures.${k}`), stack: 'x', data: months.map((m) => Number(at(m)?.[k] ?? 0) || null),
  }))
  return (
    <Card title={t('stats.futures.title')}>
      <div className="grid grid-cols-2 gap-x-4 gap-y-3">
        <Kpi label={t('stats.futures.net')} value={String(net)} currency={currency} pl />
        <div className="grid content-start gap-0.5">
          <span className="label">{t('stats.futures.winRate')}</span>
          <span className="num text-lg font-semibold">{f.positions ? `${Math.round((f.wins / f.positions) * 100)} %` : '—'}</span>
          <span className="text-xs text-muted">{t('stats.futures.of', { wins: f.wins, count: f.positions })}</span>
        </div>
        <Kpi label={t('stats.futures.best')} value={f.best} currency={currency} pl />
        <Kpi label={t('stats.futures.worst')} value={f.worst} currency={currency} pl />
      </div>
      <Chart><Bars currency={currency} label={t('stats.futures.title')} categories={months.map(monthLabel)} series={series} /></Chart>
    </Card>
  )
}

function Activity({ data, currency }: { data: StatsData; currency: string }) {
  const { t } = useTranslation()
  const [show, setShow] = useState<'count' | 'money'>('count')
  if (!data.activity.length) return null
  const months = monthsBetween(data.activity[0].month, data.activity[data.activity.length - 1].month)
  const at = (m: string) => data.activity.find((x) => x.month === m)
  return (
    <Card title={t('stats.activity.title')} action={
      <Segmented label={t('stats.activity.title')} value={show} onChange={setShow}
        options={[{ value: 'count', label: t('stats.activity.count') }, { value: 'money', label: t('stats.activity.money') }]} />
    }>
      <Chart>
        {show === 'count' ? (
          <Bars currency={null} label={t('stats.activity.title')} categories={months.map(monthLabel)} series={[
            { name: t('stats.activity.trades'), stack: 'a', data: months.map((m) => at(m)?.trades || null) },
            { name: t('stats.activity.transfers'), stack: 'a', data: months.map((m) => at(m)?.transfers || null) },
          ]} />
        ) : (
          <Bars currency={currency} label={t('stats.activity.title')} categories={months.map(monthLabel)} series={[
            { name: t('stats.activity.deposits'), data: months.map((m) => Number(at(m)?.deposits ?? 0) || null), color: 'var(--up)' },
            { name: t('stats.activity.withdrawals'), data: months.map((m) => -Number(at(m)?.withdrawals ?? 0) || null), color: 'var(--down)' },
          ]} />
        )}
      </Chart>
    </Card>
  )
}

