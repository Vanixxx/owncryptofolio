import { ArrowRight, CircleAlert } from 'lucide-react'
import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { useSettings } from '../app/settings'
import { Card, ErrorText, PageHeader, Segmented } from '../components/ui'
import { api, type HistoryPoint, type Holding, type PortfolioSummary } from '../lib/api'
import type { ChartPoint } from './dashboard/Charts'
import { cx } from '../lib/cx'
import { date, dateTime, money, percent, trend } from '../lib/format'
import { useErrorText, useMessageText } from '../lib/useErrorText'
import { alertText } from '../lib/alerts'
import { sourceName } from '../lib/txFilter'
import { Kpi } from './holdings/Kpi'
import { CurrencySwitch } from '../components/CurrencySwitch'
import { AllocationCard, MoversCard, TaxSoonCard } from './dashboard/Tiles'

const ValueChart = lazy(() => import('./dashboard/Charts').then((m) => ({ default: m.ValueChart })))

// days of the daily history; the short ranges read the fine values (ADR 0043)
const RANGES = { '24h': 0, '7d': 0, '1m': 31, '6m': 183, '1y': 366, all: 0 } as const
type Range = keyof typeof RANGES
/** The fine ranges (5 minutes for 7 days, then hourly up to 90 days): the slider starts on
 * the range, the next longer stretch is loaded to scroll back to — 24 h in 3 days, 7 days
 * in a month, a month in 3 months (Vanixxx, 2026-10-14). */
const DAY = 86_400_000
const FINE: Partial<Record<Range, number>> = { '24h': DAY, '7d': 7 * DAY, '1m': 31 * DAY }
const LOADED: Partial<Record<Range, number>> = { '24h': 3 * DAY, '7d': 31 * DAY, '1m': 92 * DAY }
const FINE_HOURS = 24 * 90
const REFRESH_MS = 60_000

/** Dashboard (ADR 0013, 0040): the value now, the result, the course since the start, and
 * where the money sits. The value refreshes every minute while the page is open. */
export function Dashboard() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const tz = useSettings().settings['general.timezone']
  const [data, setData] = useState<{ summary: PortfolioSummary; items: Holding[] } | null>(null)
  const [history, setHistory] = useState<HistoryPoint[] | null>(null)
  const [win, setWin] = useState<[number, number] | null>(null)
  const pickRange = (r: Range) => { setWin(null); setRange(r) }
  const [ticks, setTicks] = useState<{ at: string; value: string }[] | null>(null)
  const [range, setRange] = useState<Range>('1y')
  const [at, setAt] = useState<Date | null>(null)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    const load = () => {
      if (document.visibilityState !== 'visible') return
      // a refresh that works again clears an old error (a restart during an update)
      api.portfolio().then((d) => { setData(d); setAt(new Date()); setError(null) }, setError)
    }
    load()
    api.portfolioHistory().then(setHistory, setError)
    const id = window.setInterval(load, REFRESH_MS)
    return () => window.clearInterval(id)
  }, [])

  const fine = FINE[range]
  // the fine values feed the short ranges and the day's low/high band of the long ones:
  // loaded once, refreshed every minute while a short range is shown
  useEffect(() => {
    let alive = true
    const load = () => api.portfolioTicks(FINE_HOURS).then((d) => { if (alive) setTicks(d) }, (e) => { if (alive) setError(e) })
    void load()
    if (!fine) return () => { alive = false }
    const id = window.setInterval(load, REFRESH_MS)
    return () => { alive = false; window.clearInterval(id) }
  }, [fine])
  // per day the lowest and highest fine value
  const band = useMemo(() => {
    const m = new Map<string, [number, number]>()
    for (const p of ticks ?? []) {
      const d = p.at.slice(0, 10), v = Number(p.value), e = m.get(d)
      m.set(d, e ? [Math.min(e[0], v), Math.max(e[1], v)] : [v, v])
    }
    return m
  }, [ticks])
  const shown: ChartPoint[] = useMemo(() => {
    if (!history) return []
    const byDay = new Map(history.map((h) => [h.day, Number(h.deposited)]))
    const lastDep = history.length ? Number(history[history.length - 1].deposited) : undefined
    const daily = (h: HistoryPoint): ChartPoint => {
      const b = band.get(h.day)
      return { t: new Date(`${h.day}T00:00:00Z`).getTime(), value: Number(h.value), deposited: Number(h.deposited), low: b?.[0], high: b?.[1] }
    }
    if (fine) {
      // the loaded stretch: daily values until the fine ones begin, then every fine value
      const firstTick = ticks?.length ? new Date(ticks[0].at).getTime() : Infinity
      const from = Date.now() - (LOADED[range] ?? fine)
      const before = history.map(daily).filter((p) => p.t >= from && p.t < firstTick)
        .map(({ t: tt, value, deposited }) => ({ t: tt, value, deposited }))
      return [...before, ...(ticks ?? []).filter((p) => new Date(p.at).getTime() >= from).map((p) => ({
        t: new Date(p.at).getTime(), value: Number(p.value), deposited: byDay.get(p.at.slice(0, 10)) ?? lastDep,
      }))]
    }
    const days = RANGES[range]
    return (days ? history.slice(-days) : history).map(daily)
  }, [history, ticks, range, fine, band])
  // the window a short range starts on: its own length up to now
  const startWindow = useMemo<[number, number] | undefined>(() => {
    if (!fine || !shown.length) return undefined
    const end = shown[shown.length - 1].t
    return [Math.max(shown[0].t, end - fine), end]
    // set once per range, not on every refresh
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [fine, shown.length > 0])
  // the dashed "net deposited" line can be switched off from its legend (Vanixxx, 2026-10-12),
  // then the axis fits the value alone; a per-browser choice
  const [withDeposited, setWithDeposited] = useState(() => {
    try { return localStorage.getItem('dash-deposited') !== '0' } catch { return true }
  })
  const toggleDeposited = () => {
    setWithDeposited(!withDeposited)
    try { localStorage.setItem('dash-deposited', withDeposited ? '0' : '1') } catch { /* private mode */ }
  }
  const drawn = useMemo(() => (withDeposited ? shown : shown.map(({ t: tt, value, low, high }) => ({ t: tt, value, low, high }))), [shown, withDeposited])

  if (data && !data.summary.first) {
    return (
      <>
        <PageHeader title={t('pages.dashboard.title')} subtitle={t('pages.dashboard.subtitle')} aside={<CurrencySwitch />} />
        <Card title={t('pages.dashboard.start')}>
          <p className="m-0 text-sm leading-relaxed text-muted">{t('pages.dashboard.startText')}</p>
          <Link to="/sources" className="accent-fill justify-self-start rounded-ctl px-4 py-2.5 text-sm font-semibold no-underline">
            {t('pages.dashboard.toSources')}
          </Link>
        </Card>
      </>
    )
  }

  const s = data?.summary
  const cur = s?.currency ?? 'EUR'
  // the change over the shown range, or over the stretch zoomed to in the chart
  const lastT = shown.length ? shown[shown.length - 1].t : 0
  const span = win ?? (fine && shown.length ? [Math.max(shown[0].t, lastT - fine), lastT] : undefined)
  const inWin = span ? shown.filter((p) => p.t >= span[0] && p.t <= span[1]) : shown
  const first = inWin[0], last = inWin[inWin.length - 1]
  // the gain in the range, not the growth: money paid in or out is no gain (with "All" the
  // first value is the first 0.01 € deposit, and every later deposit looked like +39,000 %)
  const paidIn = first && last && first.deposited !== undefined && last.deposited !== undefined ? last.deposited - first.deposited : 0
  const stamp = (ms: number) => (fine ? dateTime(new Date(ms).toISOString(), tz) : date(new Date(ms).toISOString(), 'UTC'))
  const change = first && last && inWin.length > 1 ? last.value - first.value - paidIn : null
  const base = first ? first.value + Math.max(0, paidIn) : 0
  const changePct = change !== null && base > 0 ? (change / base) * 100 : null

  return (
    <>
      <PageHeader title={t('pages.dashboard.title')} subtitle={t('pages.dashboard.subtitle')} aside={<CurrencySwitch />} />
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
      {!s ? (
        <p className="text-sm text-muted">{t('common.loading')}</p>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)] md:gap-5">
            <Card>
              <div className="flex flex-wrap items-end justify-between gap-3">
                <Kpi label={t('dashboard.value')} value={s.value} currency={cur} big
                  hint={at ? t('dashboard.asOf', { at: dateTime(at.toISOString(), tz) }) : undefined} />
                {change !== null && (
                  <span className={cx('num grid justify-items-start text-sm font-semibold sm:justify-items-end sm:text-right', trend(String(change)) === 'up' ? 'text-up' : trend(String(change)) === 'down' ? 'text-down' : 'text-muted')}>
                    <span>{money(String(change), cur, true)} {changePct !== null && percent(changePct.toFixed(2))}</span>
                    {/* the stretch the change is about, on its own line (Vanixxx, 2026-10-06) */}
                    <span className="text-xs font-normal text-muted">
                      {!win && `${t(`dashboard.ranges.${range}`)} · `}{stamp(first.t)} – {stamp(last.t)}
                    </span>
                  </span>
                )}
              </div>
              <Segmented label={t('dashboard.range')} value={range} onChange={pickRange}
                options={(Object.keys(RANGES) as Range[]).map((r) => ({ value: r, label: t(`dashboard.ranges.${r}`) }))} />
              {fine && ticks !== null && ticks.length < 3 ? (
                // the 5-minute values start with the day this was built; until then: say so
                <p className="m-0 grid h-56 place-items-center text-center text-sm leading-relaxed text-muted md:h-72">{t('dashboard.ticksFilling')}</p>
              ) : (fine ? ticks === null || history === null : history === null) ? (
                <div className="h-64 md:h-80" />
              ) : (
                <Suspense fallback={<div className="h-64 md:h-80" />}>
                  <ValueChart points={drawn} currency={cur} intraday={!!fine} drawKey={range} window={startWindow}
                    onWindow={(a, b) => setWin(a <= (shown[0]?.t ?? 0) && b >= (shown[shown.length - 1]?.t ?? 0) ? null : [a, b])} />
                </Suspense>
              )}
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-accent" aria-hidden="true" />{t('dashboard.value')}</span>
                <button type="button" onClick={toggleDeposited} aria-pressed={withDeposited} title={t(withDeposited ? 'dashboard.hideDeposited' : 'dashboard.showDeposited')}
                  className={cx('flex items-center gap-1.5 border-0 bg-transparent p-0 text-xs text-muted hover:text-fg', !withDeposited && 'line-through opacity-60')}>
                  <span className="w-4 border-t border-dashed border-muted" aria-hidden="true" />{t('dashboard.deposited')}
                </button>
                {s.high && <span>{t('dashboard.high', { value: money(s.high.value, cur), date: date(s.high.day, 'UTC') })}</span>}
              </div>
            </Card>
            <div className="grid content-start gap-4 md:gap-5">
              <Card>
                <Kpi label={t('dashboard.result')} value={s.result} currency={cur} pl
                  hint={t('dashboard.resultHint')} />
                <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                  <Kpi label={t('holdings.unrealized')} value={s.unrealized} pct={s.unrealized_pct} currency={cur} pl />
                  <Kpi label={t('holdings.realized')} value={s.realized} pct={s.realized_pct} currency={cur} pl />
                  <Kpi label={t('holdings.futures.result')} value={s.futures.result} currency={cur} pl />
                  <Kpi label={t('dashboard.income')} value={s.income} currency={cur} />
                </div>
              </Card>
              <Card>
                <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                  <Kpi label={t('dashboard.deposited')} value={s.net_deposited} currency={cur}
                    hint={Number(s.card_deposits) > 0 ? t('dashboard.cardHint', { value: money(s.card_deposits, cur) }) : undefined} />
                  <Kpi label={t('holdings.cost')} value={s.cost} currency={cur} />
                  {s.high && Number(s.high.value) > 0 && (
                    // how far below the best day the value is now (ADR 0043)
                    <Kpi label={t('dashboard.fromHigh')} value={String(Number(s.value) - Number(s.high.value))} currency={cur} pl
                      pct={String((Number(s.value) / Number(s.high.value) - 1) * 100)}
                      hint={t('dashboard.fromHighHint', { value: money(s.high.value, cur), date: date(s.high.day, 'UTC') })} className="col-span-2" />
                  )}
                </div>
              </Card>
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-2 md:gap-5">
            <AllocationCard items={data?.items ?? []} currency={cur} />
            <MoversCard items={data?.items ?? []} currency={cur} />
            <TaxSoonCard currency={cur} />
            <Notes s={s} />
          </div>
        </>
      )}
    </>
  )
}

/** What makes the numbers less certain, each with the way to fix it. */
function Notes({ s }: { s: PortfolioSummary }) {
  const { t } = useTranslation()
  const messageText = useMessageText()
  // keys and fetches first: a dead key loses data, the rest only makes numbers uncertain
  const [alerts, setAlerts] = useState<{ text: string }[]>([])
  // the tax-free limits of this year: a note from 80 % on (ADR 0044)
  const [limits, setLimits] = useState<{ text: string }[]>([])
  useEffect(() => {
    api.taxLimits().then((l) => setLimits((['s23', 's22'] as const).filter((k) => l[k].level !== 'ok').map((k) => ({
      text: t(`dashboard.notes.limit_${l[k].level}`, {
        pot: t(`dashboard.notes.pot_${k}`), year: l.year, share: Math.round(Number(l[k].share)),
        value: money(l[k].value, s.currency), limit: money(l[k].limit, s.currency),
      }),
    }))), () => {})
  }, [t, s.currency])
  useEffect(() => {
    Promise.all([api.sourceAlerts(), api.sources(), api.wallets()]).then(([a, src, w]) => {
      const name = sourceName(src, w)
      setAlerts(a.map((x) => ({ text: alertText(t, x, name(x.source_id), x.message ? messageText(x.message) : '') })))
    }, () => {})
  }, [t, messageText])
  const cur = s.currency
  const notes = [
    ...alerts.map((a, i) => ({ text: a.text, to: `/sources#${i}`, link: t('dashboard.notes.toSources') })),
    ...limits.map((l, i) => ({ text: l.text, to: `/reports#limit${i}`, link: t('dashboard.notes.toReports') })),
    Number(s.unclear) > 0 && { text: t('dashboard.notes.unclear', { value: money(s.unclear, cur) }), to: '/holdings?tab=gaps', link: t('dashboard.notes.toGaps') },
    Number(s.open) > 0 && { text: t('dashboard.notes.open', { value: money(s.open, cur) }), to: '/transactions', link: t('dashboard.notes.toTransactions') },
    s.unvalued.length > 0 && { text: t('dashboard.notes.unvalued', { assets: s.unvalued.join(', ') }), to: s.unvalued.length === 1 ? `/prices?asset=${encodeURIComponent(s.unvalued[0])}` : '/prices', link: t('dashboard.notes.toPrices') },
  ].filter(Boolean) as { text: string; to: string; link: string }[]
  return (
    <Card title={t('dashboard.notes.title')}>
      {notes.length === 0 ? (
        <p className="m-0 text-sm text-up">{t('dashboard.notes.none')}</p>
      ) : (
        <ul className="m-0 grid list-none gap-3 p-0">
          {notes.map((n) => (
            <li key={n.to} className="grid grid-cols-[auto_minmax(0,1fr)] gap-2 text-sm">
              <CircleAlert size={16} aria-hidden="true" className="mt-0.5 text-warn" />
              <span className="grid gap-1">
                <span className="leading-relaxed">{n.text}</span>
                <Link to={n.to} className="inline-flex items-center gap-1 justify-self-start text-xs text-accent no-underline">{n.link}<ArrowRight size={13} aria-hidden="true" /></Link>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
