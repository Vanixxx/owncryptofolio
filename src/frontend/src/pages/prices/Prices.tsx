import { ArrowDown, ArrowUp, ChevronDown, History, Plus, RefreshCw, Trash2 } from 'lucide-react'
import { lazy, Suspense, useCallback, useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'
import { useSettings } from '../../app/settings'
import { CoinIcon } from '../../components/CoinIcon'
import { Button, Card, ErrorText, Field, PageHeader, Segmented, StatusPill } from '../../components/ui'
import { useJobs } from '../../hooks/useJobs'
import {
  api, type Crosscheck, type PriceAssetRow, type PriceChange, type PricePoint, type PriceSourceRow,
  type ChangeSpan,
} from '../../lib/api'
import { locale } from '../../i18n'
import { cx } from '../../lib/cx'
import { date, dateTime, money, priceText } from '../../lib/format'
import { useErrorText, useMessageText } from '../../lib/useErrorText'
import { Sparkline } from './Sparkline'
import { LogoUpload } from '../../components/LogoUpload'
import { SearchField } from '../../components/ui/SearchField'
import { SortSelect } from '../../components/SortSelect'
import { matches } from '../../lib/search'
import { compare } from '../../lib/sort'
import { CurrencySwitch } from '../../components/CurrencySwitch'
import { TopBarActions } from '../../components/layout/TopBar'
import { useStoredSort } from '../../hooks/useStoredSort'

type Filter = 'all' | 'review' | 'missing' | 'ignored'
const SORT_KEYS = ['usage', 'name', 'price', 'change'] as const
type SortKey = (typeof SORT_KEYS)[number]

export const SPANS: ChangeSpan[] = ['d1', 'h24', 'd7', 'd30', 'd90']

/** The change over the chosen span in % (Vanixxx, 2026-10-14): today against the close
 * before, or 7/30/90 days back. */
export function change(a: Pick<PriceAssetRow, 'changes'> | undefined, span: ChangeSpan): number | null {
  const v = a?.changes?.[span]
  return v === undefined || v === null ? null : Number(v)
}

/** What the price change over the span made of today's holding, in the display currency:
 * value now minus the same quantity at the price back then (value / (1 + change)). */
export function valueChange(value: string | null | undefined, c: number | null): number | null {
  if (value === null || value === undefined || value === '' || c === null || c <= -100) return null
  return Number(value) * c / (100 + c)
}

/** The change over the span; with `amount` the same change as money on today's holding
 * instead of in % (holdings, Vanixxx 2026-10-28). */
export function ChangeText({ a, span, amount }: {
  a: Pick<PriceAssetRow, 'changes'> | undefined; span: ChangeSpan
  amount?: { value: string | null; currency: string }
}) {
  const { t } = useTranslation()
  const c = change(a, span)
  if (c === null) return null
  const delta = amount ? valueChange(amount.value, c) : null
  return (
    <span className={cx('num whitespace-nowrap text-[0.7rem]', c > 0 ? 'text-up' : c < 0 ? 'text-down' : 'text-muted')}>
      {/* as money a clock stands for the span (named in the selector above), so the line stays
          short on the phone (Vanixxx, 2026-10-28) */}
      {amount && delta !== null
        ? <span className="inline-flex items-center gap-1">
            <History size={11} aria-hidden="true" className="shrink-0 opacity-80" />
            {money(String(delta), amount.currency, true)}
            <span className="sr-only">{t(`prices.spans.${span}`)}</span>
          </span>
        : <>{c > 0 && '+'}{c.toLocaleString(locale(), { maximumFractionDigits: 1, minimumFractionDigits: 1 })} % · {t(`prices.spans.${span}`)}</>}
    </span>
  )
}
const SOURCES: PriceSourceRow['source'][] = ['yahoo', 'bitget', 'binance', 'coingecko']

const LIVE_MS = 30_000
const pct = (v?: string) => (v === undefined ? '' : Number(v).toLocaleString(locale(), { maximumFractionDigits: 2 }))
const needsReview = (a: PriceAssetRow) => !a.confirmed && !a.ignored
const missing = (a: PriceAssetRow) => !a.ignored && a.days === 0

/** Prices (ADR 0019): every asset with its mapping, last price, a curve without axes in the
 * list, and on opening the chart, sources with their share, gaps, cross-check, confirm,
 * edit with a reason and the history of changes. */
export function Prices() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const messageText = useMessageText()
  const tz = useSettings().settings['general.timezone']
  const [assets, setAssets] = useState<PriceAssetRow[] | null>(null)
  const [filter, setFilter] = useState<Filter>('all')
  // a link may name a coin (statistics: coins without a price): found and opened
  const [params] = useSearchParams()
  const [open, setOpen] = useState<string | null>(() => params.get('asset'))
  const [error, setError] = useState<unknown>(null)
  const load = useCallback(() => api.priceAssets().then((a) => { setAssets(a); setError(null) }, setError), [])
  const { jobs, refresh } = useJobs(load)
  // load() sets state only after awaiting the server.
  // oxlint-disable-next-line react/set-state-in-effect
  useEffect(() => void load(), [load])
  const [flash, setFlash] = useState<Record<string, 'up' | 'down'>>({})
  // While the page is visible: current prices every 30 s, a moved price flashes (design 2026-10-02).
  useEffect(() => {
    const tick = () => {
      if (document.visibilityState !== 'visible') return
      api.livePrices().then((live) => {
        setAssets((old) => {
          if (!old) return old
          const moved: Record<string, 'up' | 'down'> = {}
          const next = old.map((a) => {
            const l = live[a.asset]
            if (!l || l.price === a.price) return a
            if (a.price) moved[a.asset] = Number(l.price) > Number(a.price) ? 'up' : 'down'
            return { ...a, price: l.price, price_at: l.at }
          })
          if (Object.keys(moved).length) {
            setFlash(moved)
            window.setTimeout(() => setFlash({}), 950)
          }
          return next
        })
      }, () => {})
    }
    tick()
    const id = window.setInterval(tick, LIVE_MS)
    return () => window.clearInterval(id)
  }, [])
  const job = jobs.find((j) => j.kind === 'prices')
  const busy = job && (job.status === 'queued' || job.status === 'running')
  const start = () => api.startJob('prices').then(() => { setError(null); refresh() }, setError)

  const list = assets ?? []
  const counts = { review: list.filter(needsReview).length, missing: list.filter(missing).length, ignored: list.filter((a) => a.ignored).length }
  const [query, setQuery] = useState(() => params.get('asset') ?? '')
  const [span, setSpanState] = useState<ChangeSpan>(() => {
    try { const v = localStorage.getItem('prices-span') as ChangeSpan | null; return v && SPANS.includes(v) ? v : 'd90' } catch { return 'd90' }
  })
  const setSpan = (v: ChangeSpan) => { setSpanState(v); try { localStorage.setItem('prices-span', v) } catch { /* private mode */ } }
  // the curves follow the span (Vanixxx, 2026-10-16); the 90 days come with the list
  const [sparks, setSparks] = useState<{ span: ChangeSpan; data: Record<string, string[]> } | null>(null)
  useEffect(() => {
    let alive = true
    api.priceSparks(span).then((data) => { if (alive) setSparks({ span, data }) }, () => {})
    return () => { alive = false }
  }, [span])
  const rising = (a: PriceAssetRow) => { const c = change(a, span); return c === null ? undefined : c >= 0 }
  const spark = (a: PriceAssetRow) => sparks?.span === span ? sparks.data[a.asset] ?? [] : span === 'd90' ? a.spark : []
  const [sort, setSort] = useStoredSort<SortKey>('ocf.sort.prices', { key: 'usage', desc: true }, SORT_KEYS)
  const pick: Record<SortKey, (a: PriceAssetRow) => number | string | null> = {
    usage: (a) => a.rows,
    name: (a) => a.asset,
    price: (a) => (a.price ? Number(a.price) : null),
    change: (a) => change(a, span),
  }
  const shown = list
    .filter((a) => filter === 'all' ? !a.ignored : filter === 'review' ? needsReview(a) : filter === 'missing' ? missing(a) : a.ignored)
    .filter((a) => matches(query, a.asset, a.name, ...a.aliases))
    .sort((x, y) => compare(pick[sort.key](x), pick[sort.key](y), sort.desc))

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader title={t('pages.prices.title')} subtitle={t('prices.subtitle')} />
        {/* fetch, then the currency switch; on the phone both sit in the top bar, the
            button as its icon (Vanixxx, 2026-10-19) */}
        <div className="ml-auto hidden items-center gap-3 md:flex">
          <Button onClick={() => void start()} disabled={!!busy}>
            <RefreshCw size={16} aria-hidden="true" className={busy ? 'animate-spin' : ''} />{t('prices.fetch')}
          </Button>
          <CurrencySwitch />
        </div>
        <TopBarActions>
          <Button onClick={() => void start()} disabled={!!busy} aria-label={t('prices.fetch')} title={t('prices.fetch')}
            className="h-9 w-9 shrink-0 px-0! py-0! md:hidden">
            <RefreshCw size={16} aria-hidden="true" className={busy ? 'animate-spin' : ''} />
          </Button>
        </TopBarActions>
      </div>
      {job && (
        <p className="m-0 text-xs text-muted">
          {busy
            ? (job.progress.total ? t('prices.jobProgress', { done: job.progress.done, total: job.progress.total }) : t('pages.sources.jobRunning'))
            : job.status === 'failed' ? messageText(job.message ?? '') : t('prices.jobDone', { at: dateTime(job.finished_at ?? job.created_at, tz) })}
        </p>
      )}
      <ErrorText>{error ? errorText(error) : null}</ErrorText>

      <Segmented label={t('prices.filter')} value={filter} onChange={setFilter} options={[
        { value: 'all', label: t('prices.filters.all') },
        { value: 'review', label: `${t('prices.filters.review')} ${counts.review}` },
        { value: 'missing', label: `${t('prices.filters.missing')} ${counts.missing}` },
        { value: 'ignored', label: `${t('prices.filters.ignored')} ${counts.ignored}` },
      ]} />
      <div className="flex flex-wrap items-center gap-2">
        <SearchField value={query} onChange={setQuery} placeholder={t('holdings.search')} className="w-full sm:w-64" />
        <SortSelect id="prices-sort" value={sort} onChange={setSort}
          options={(Object.keys(pick) as SortKey[]).map((k) => ({ value: k, label: t(`prices.sort.${k}`) }))} />
        <Segmented label={t('prices.spanLabel')} value={span} onChange={setSpan}
          options={SPANS.map((s) => ({ value: s, label: t(`prices.spans.${s}`) }))} />
      </div>
      {filter === 'review' && <p className="m-0 text-sm leading-relaxed text-muted">{t('prices.reviewHint')}</p>}

      {assets === null ? (
        <p className="text-sm text-muted">{t('common.loading')}</p>
      ) : shown.length === 0 ? (
        <Card><p className="m-0 text-sm text-muted">{t('prices.empty')}</p></Card>
      ) : (
        <ul className="m-0 grid list-none gap-2 p-0">
          {shown.map((a) => (
            <li key={a.asset} className="card grid min-w-0 gap-3 p-3">
              <button type="button" onClick={() => setOpen(open === a.asset ? null : a.asset)} aria-expanded={open === a.asset}
                className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 border-0 bg-transparent p-0 text-left text-fg">
                <CoinIcon asset={a.icon ?? a.asset} />
                <span className="grid min-w-0">
                  <span className="flex min-w-0 items-baseline gap-2">
                    <b className="shrink-0">{a.asset}</b>
                    <span className="truncate text-xs text-muted">{a.name}</span>
                    {a.aliases.length > 0 && <span className="truncate text-xs text-muted">· {a.aliases.join(', ')}</span>}
                  </span>
                  <span className="flex flex-wrap items-center gap-x-2 text-xs text-muted">
                    <Status asset={a} />
                    {a.sources[0] && <span>{t(`prices.sources.${a.sources[0].source}`)}</span>}
                  </span>
                </span>
                <span className="flex items-center gap-2">
                  <span className="hidden sm:inline"><Sparkline values={spark(a)} up={rising(a)} /></span>
                  <span className="grid justify-items-end">
                    <b className={cx('num rounded px-1 text-sm', flash[a.asset] && `flash-${flash[a.asset]}`)}>
                      {a.price ? priceText(Number(a.price), a.currency) : a.ended_on ? t('prices.endedShort', { date: date(a.ended_on, 'UTC') }) : '—'}
                    </b>
                    <ChangeText a={a} span={span} />
                    <span className="sm:hidden"><Sparkline values={spark(a)} width={64} height={18} up={rising(a)} /></span>
                  </span>
                  <ChevronDown size={18} aria-hidden="true" className={cx('text-muted transition-transform', open !== a.asset && '-rotate-90')} />
                </span>
              </button>
              {open === a.asset && <AssetDetail asset={a} tz={tz} onChanged={load} />}
            </li>
          ))}
        </ul>
      )}
    </>
  )
}

function Status({ asset: a }: { asset: PriceAssetRow }) {
  const { t } = useTranslation()
  if (a.ignored) return <span>{t('prices.state.ignored')}</span>
  // declared worthless: no warning, it is meant so (NTGL, 2026-10-12)
  if (a.worthless_since) return <span className="text-muted">{t('prices.state.worthless', { date: a.worthless_since.split('-').reverse().join('.') })}</span>
  if (a.days === 0) return <StatusPill ok={false}>{t('prices.state.missing')}</StatusPill>
  if (!a.confirmed) return <span className="text-warn">{t('prices.state.suggested')}</span>
  return <span className="text-up">{t('prices.state.confirmed')}</span>
}

// ECharts is large: loaded only when a chart is opened, not with the app
const PriceChart = lazy(() => import('./PriceChart').then((m) => ({ default: m.PriceChart })))

const RANGES = [90, 365, 10000] as const

function AssetDetail({ asset: a, tz, onChanged }: { asset: PriceAssetRow; tz: string; onChanged: () => void }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  // a coin whose prices ended over a year ago opens on all of them, not on an empty year
  const [range, setRange] = useState<(typeof RANGES)[number]>(() =>
    a.last_day && Date.now() - new Date(a.last_day).getTime() > 365 * 86_400_000 ? 10000 : 365)
  const [points, setPoints] = useState<PricePoint[] | null>(null)
  const [check, setCheck] = useState<Crosscheck | 'busy' | null>(null)
  const [mode, setMode] = useState<'idle' | 'edit' | 'ignore' | 'changes' | 'alias' | 'worthless' | 'until'>('idle')
  const [since, setSince] = useState(() => new Date().toISOString().slice(0, 10))
  const [changes, setChanges] = useState<PriceChange[] | null>(null)
  const [reason, setReason] = useState('')
  const [error, setError] = useState<unknown>(null)
  // this coin alone, not the whole run (Vanixxx, 2026-10-10)
  const [fetching, setFetching] = useState<'busy' | { prices: number; failed: boolean } | null>(null)
  const fetchOne = () => {
    setFetching('busy'); setError(null)
    api.fetchPrice(a.asset).then((r) => { setFetching({ prices: r.prices, failed: r.with_errors.length > 0 }); onChanged() },
      (e) => { setFetching(null); setError(e) })
  }

  useEffect(() => {
    let live = true
    api.priceHistory(a.asset, range).then((p) => live && setPoints(p), setError)
    return () => { live = false }
  }, [a.asset, range, a.days])

  const done = () => { setMode('idle'); setError(null); setReason(''); onChanged() }
  const showChanges = () => { setMode('changes'); api.priceChanges(a.asset).then(setChanges, setError) }

  return (
    <div className="grid min-w-0 gap-3 border-t border-line pt-3">
      {a.days > 0 && (
        <>
          <Segmented label={t('prices.rangeLabel')} value={String(range)} onChange={(v) => setRange(Number(v) as typeof range)}
            options={RANGES.map((r) => ({ value: String(r), label: t(`prices.ranges.${r}`) }))} />
          {points && points.length > 0
            ? <Suspense fallback={<div className="h-64 md:h-72" />}><PriceChart points={points} currency={a.currency} /></Suspense>
            : <p className="m-0 text-sm text-muted">{points ? t('prices.noPointsInRange') : t('common.loading')}</p>}
        </>
      )}
      <dl className="m-0 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-sm">
        <dt className="text-muted">{t('prices.mapping')}</dt>
        <dd className="m-0 grid gap-0.5">
          {a.sources.length === 0 && <span className="text-muted">{t('prices.noSource')}</span>}
          {a.sources.map((s) => (
            <span key={s.rank} className="[overflow-wrap:anywhere]">
              {s.rank}. {t(`prices.sources.${s.source}`)} · <code className="text-xs">{s.ticker}</code>
              {a.contributions[s.source] ? <span className="text-muted"> · {t('prices.daysCount', { count: a.contributions[s.source], n: a.contributions[s.source].toLocaleString(locale()) })}</span> : null}
            </span>
          ))}
        </dd>
        {a.aliases.length > 0 && (
          <>
            <dt className="text-muted">{t('prices.aliases')}</dt>
            <dd className="m-0 flex flex-wrap items-center gap-2">
              {a.aliases.map((x) => (
                <span key={x} className="inline-flex items-center gap-1 rounded-full border border-line px-2 py-0.5 text-xs">
                  {x}
                  <button type="button" aria-label={t('prices.removeAlias', { alias: x })} className="text-muted"
                    onClick={() => void api.removePriceAlias(x).then(done, setError)}>×</button>
                </span>
              ))}
            </dd>
          </>
        )}
        {a.first_day && <><dt className="text-muted">{t('prices.covered')}</dt><dd className="m-0 num">{date(a.first_day, 'UTC')} – {date(a.last_day, 'UTC')}</dd></>}
        {a.needed_from && <><dt className="text-muted">{t('prices.neededFrom')}</dt><dd className="m-0 num">{date(a.needed_from, 'UTC')} · {t('prices.usedIn', { count: a.rows })}</dd></>}
        {a.ended_on && <><dt className="text-muted">{t('prices.latest')}</dt><dd className="m-0">{t('prices.ended', { date: date(a.ended_on, 'UTC') })}</dd></>}
        {a.price_at && a.price && <><dt className="text-muted">{t('prices.latest')}</dt><dd className="m-0 num">{priceText(Number(a.price), a.currency)} · {dateTime(a.price_at, tz)}</dd></>}
      </dl>
      {a.gap && !a.ignored && (
        <p className="m-0 rounded-ctl bg-surface-2 p-3 text-sm text-warn">
          {t('prices.gap', { from: date(a.gap.from, 'UTC'), to: date(a.gap.to, 'UTC') })}
        </p>
      )}
      {Object.keys(a.contributions).length > 1 && <p className="m-0 text-xs text-muted">{t('prices.seamHint')}</p>}

      {check && (
        <p className={cx('m-0 text-sm', check !== 'busy' && check.verdict === 'deviates' ? 'text-down' : 'text-muted')}>
          {check === 'busy' ? t('common.loading') : t(`prices.check.${check.verdict}`, { days: check.days, mean: pct(check.mean_pct), max: pct(check.max_pct) })}
        </p>
      )}

      {fetching && fetching !== 'busy' && (
        <p className={cx('m-0 text-sm', fetching.failed ? 'text-warn' : 'text-muted')}>
          {t(fetching.failed ? 'prices.fetchOneFailed' : 'prices.fetchOneDone', { count: fetching.prices })}
        </p>
      )}
      {a.worthless_since && <p className="m-0 rounded-ctl bg-down/10 px-3 py-2 text-sm text-down">{t('prices.worthlessFrom', { date: a.worthless_since.split('-').reverse().join('.') })}</p>}
      {a.prices_until && <p className="m-0 rounded-ctl bg-surface-2 px-3 py-2 text-sm text-muted">{t('prices.untilFrom', { date: date(a.prices_until, 'UTC') })}</p>}
      {mode === 'edit' ? (
        <MappingForm asset={a} onDone={done} onCancel={() => setMode('idle')} />
      ) : mode === 'alias' ? (
        <AliasForm asset={a} onDone={done} onCancel={() => setMode('idle')} />
      ) : mode === 'worthless' ? (
        // a dead token: worth 0 from a day on, so its loss shows (Vanixxx, 2026-10-08)
        <form onSubmit={(e) => { e.preventDefault(); api.setWorthless(a.asset, since, reason).then(done, setError) }} className="grid gap-2">
          <p className="m-0 text-xs leading-relaxed text-muted">{t('prices.worthlessHint')}</p>
          <Field id={`worthless-since-${a.asset}`} label={t('prices.worthlessSince')} type="date" value={since} onChange={(e) => setSince(e.target.value)} required />
          <Field id={`worthless-reason-${a.asset}`} label={t('prices.reason')} value={reason} onChange={(e) => setReason(e.target.value)} required
            placeholder={t('prices.worthlessPlaceholder')} />
          <div className="flex flex-wrap gap-2">
            <Button type="submit">{t('prices.worthless')}</Button>
            <Button type="button" variant="ghost" onClick={() => setMode('idle')}>{t('common.cancel')}</Button>
          </div>
        </form>
      ) : mode === 'until' ? (
        // a coin merged into another: its prices end, nothing is fetched after (Vanixxx, 2026-10-17)
        <form onSubmit={(e) => { e.preventDefault(); api.setPricesUntil(a.asset, since, reason).then(done, setError) }} className="grid gap-2">
          <p className="m-0 text-xs leading-relaxed text-muted">{t('prices.untilHint')}</p>
          <Field id={`until-${a.asset}`} label={t('prices.untilDay')} type="date" value={since} onChange={(e) => setSince(e.target.value)} required />
          <Field id={`until-reason-${a.asset}`} label={t('prices.reason')} value={reason} onChange={(e) => setReason(e.target.value)} required
            placeholder={t('prices.untilPlaceholder')} />
          <div className="flex flex-wrap gap-2">
            <Button type="submit">{t('prices.until')}</Button>
            <Button type="button" variant="ghost" onClick={() => setMode('idle')}>{t('common.cancel')}</Button>
          </div>
        </form>
      ) : mode === 'ignore' ? (
        <form onSubmit={(e) => { e.preventDefault(); api.ignorePrice(a.asset, !a.ignored, reason).then(done, setError) }} className="grid gap-2">
          <Field id={`ignore-${a.asset}`} label={t('prices.reasonOptional')} value={reason} onChange={(e) => setReason(e.target.value)}
            placeholder={t('prices.ignorePlaceholder')} />
          <div className="flex flex-wrap gap-2">
            <Button type="submit">{a.ignored ? t('prices.unignore') : t('prices.ignore')}</Button>
            <Button type="button" variant="ghost" onClick={() => setMode('idle')}>{t('common.cancel')}</Button>
          </div>
        </form>
      ) : (
        <div className="flex flex-wrap gap-2">
          {needsReview(a) && <Button onClick={() => void api.confirmPrice(a.asset).then(done, setError)}>{t('prices.confirm')}</Button>}
          {!a.ignored && (
            <Button variant="ghost" disabled={fetching === 'busy'} onClick={fetchOne}>
              <RefreshCw size={14} aria-hidden="true" className={fetching === 'busy' ? 'animate-spin' : ''} />{t('prices.fetchOne')}
            </Button>
          )}
          <Button variant="ghost" onClick={() => setMode('edit')}>{t('prices.edit')}</Button>
          {!a.ignored && a.asset !== 'USDT' ? (
            <Button variant="ghost" disabled={check === 'busy'} onClick={() => { setCheck('busy'); api.priceCrosscheck(a.asset).then(setCheck, (e) => { setCheck(null); setError(e) }) }}>
              {t('prices.crosscheck')}
            </Button>
          ) : null}
          <Button variant="ghost" onClick={() => setMode('ignore')}>{a.ignored ? t('prices.unignore') : t('prices.ignore')}</Button>
          <Button variant="ghost" onClick={() => setMode('alias')}>{t('prices.sameCoin')}</Button>
          {a.worthless_since
            ? <Button variant="ghost" onClick={() => void api.setWorthless(a.asset, null).then(done, setError)}>{t('prices.notWorthless')}</Button>
            : !a.ignored && <Button variant="ghost" onClick={() => setMode('worthless')}>{t('prices.worthless')}</Button>}
          {a.prices_until
            ? <Button variant="ghost" onClick={() => void api.setPricesUntil(a.asset, null).then(done, setError)}>{t('prices.untilUndo')}</Button>
            : !a.ignored && !a.worthless_since && <Button variant="ghost" onClick={() => setMode('until')}>{t('prices.until')}</Button>}
          <LogoUpload kind="coin" id={a.asset} />
          <Button variant="ghost" onClick={showChanges}>{t('prices.changes')}</Button>
        </div>
      )}
      {mode === 'changes' && changes && (
        <ul className="m-0 grid gap-1.5 rounded-ctl bg-surface-2 p-3 pl-6 text-xs">
          {changes.length === 0 && <li className="list-none text-muted">{t('prices.noChanges')}</li>}
          {changes.map((c, i) => (
            <li key={i}>
              <span className="text-muted">{dateTime(c.at, tz)} · {t(`prices.fields.${c.field}`, { defaultValue: c.field })}:</span>{' '}
              <span className="[overflow-wrap:anywhere]">{c.before ?? '—'} → {c.after ?? '—'}</span>
              {c.reason && <span className="block text-muted [overflow-wrap:anywhere]">{t('prices.reason')}: {c.reason}</span>}
            </li>
          ))}
        </ul>
      )}
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
    </div>
  )
}

function MappingForm({ asset: a, onDone, onCancel }: { asset: PriceAssetRow; onDone: () => void; onCancel: () => void }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [name, setName] = useState(a.name ?? '')
  const [icon, setIcon] = useState(a.icon ?? '')
  const [rows, setRows] = useState(a.sources.map((s) => ({ source: s.source as string, ticker: s.ticker })))
  const [reason, setReason] = useState('')
  const [error, setError] = useState<unknown>(null)
  const changed = JSON.stringify(rows) !== JSON.stringify(a.sources.map((s) => ({ source: s.source, ticker: s.ticker })))
  const move = (i: number, d: number) => setRows((r) => { const n = [...r]; [n[i], n[i + d]] = [n[i + d], n[i]]; return n })

  function submit(e: FormEvent) {
    e.preventDefault()
    api.updatePriceMapping(a.asset, { name: name || null, sources: rows.filter((r) => r.ticker.trim()), reason, icon }).then(onDone, setError)
  }
  return (
    <form onSubmit={submit} className="grid gap-3 rounded-ctl bg-surface-2 p-3">
      <Field id={`name-${a.asset}`} label={t('prices.name')} value={name} onChange={(e) => setName(e.target.value)} placeholder="The Graph" />
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-end gap-3">
        <Field id={`icon-${a.asset}`} label={t('prices.icon')} value={icon} onChange={(e) => setIcon(e.target.value.toUpperCase())}
          placeholder={a.asset} autoCapitalize="characters" />
        <CoinIcon key={icon || a.asset} asset={icon || a.asset} size={40} className="mb-1" />
      </div>
      <span className="-mt-2 text-xs text-muted">{t('prices.iconHint')}</span>
      <span className="label">{t('prices.sourcesLabel')}</span>
      {rows.map((r, i) => (
        // source and arrows on one line, the ticker below at full width: on a phone
        // three columns cut both (seen 2026-10-04)
        <div key={i} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 rounded-ctl border border-line p-2">
          <select aria-label={t('prices.source')} value={r.source} onChange={(e) => setRows(rows.map((x, j) => j === i ? { ...x, source: e.target.value } : x))}
            className="min-w-0 rounded-ctl border border-line bg-surface px-2 py-2.5 text-sm text-fg">
            {SOURCES.map((s) => <option key={s} value={s}>{i + 1}. {t(`prices.sources.${s}`)}</option>)}
          </select>
          <span className="flex">
            <button type="button" aria-label={t('prices.up')} disabled={i === 0} onClick={() => move(i, -1)} className="p-1.5 text-muted disabled:opacity-30"><ArrowUp size={16} /></button>
            <button type="button" aria-label={t('prices.down')} disabled={i === rows.length - 1} onClick={() => move(i, 1)} className="p-1.5 text-muted disabled:opacity-30"><ArrowDown size={16} /></button>
            <button type="button" aria-label={t('prices.remove')} onClick={() => setRows(rows.filter((_, j) => j !== i))} className="p-1.5 text-muted"><Trash2 size={16} /></button>
          </span>
          <input aria-label={t('prices.ticker')} value={r.ticker} placeholder={t(`prices.tickerExample.${r.source}`)} spellCheck={false}
            onChange={(e) => setRows(rows.map((x, j) => j === i ? { ...x, ticker: e.target.value } : x))}
            className="col-span-2 min-w-0 rounded-ctl border border-line bg-surface px-3 py-2.5 font-mono text-sm text-fg" />
        </div>
      ))}
      <Button type="button" variant="ghost" className="justify-self-start" onClick={() => setRows([...rows, { source: 'yahoo', ticker: '' }])}>
        <Plus size={16} aria-hidden="true" />{t('prices.addSource')}
      </Button>
      <p className="m-0 text-xs leading-relaxed text-muted">{t('prices.tickerHint')}</p>
      {changed && (
        <label htmlFor={`reason-${a.asset}`} className="grid gap-1.5">
          <span className="label">{t('prices.reasonRequired')}</span>
          <textarea id={`reason-${a.asset}`} rows={2} value={reason} onChange={(e) => setReason(e.target.value)} required
            placeholder={t('prices.reasonPlaceholder')}
            className="w-full rounded-ctl border border-line bg-surface px-3 py-2.5 text-sm text-fg outline-none focus:border-accent" />
        </label>
      )}
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
      <div className="flex flex-wrap gap-2">
        <Button type="submit">{t('common.save')}</Button>
        <Button type="button" variant="ghost" onClick={onCancel}>{t('common.cancel')}</Button>
      </div>
    </form>
  )
}

function AliasForm({ asset: a, onDone, onCancel }: { asset: PriceAssetRow; onDone: () => void; onCancel: () => void }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [target, setTarget] = useState('')
  const [name, setName] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<unknown>(null)
  function submit(e: FormEvent) {
    e.preventDefault()
    api.setPriceAlias(a.asset, target, name, reason).then(onDone, setError)
  }
  return (
    <form onSubmit={submit} className="grid gap-3 rounded-ctl bg-surface-2 p-3">
      <p className="m-0 text-sm leading-relaxed text-muted">{t('prices.sameCoinHint', { asset: a.asset })}</p>
      <Field id={`alias-target-${a.asset}`} label={t('prices.sameCoinTarget')} value={target} required autoCapitalize="characters"
        onChange={(e) => setTarget(e.target.value.toUpperCase())} placeholder="NGL" />
      <Field id={`alias-name-${a.asset}`} label={t('prices.name')} value={name} onChange={(e) => setName(e.target.value)} placeholder="Entangle" />
      <Field id={`alias-reason-${a.asset}`} label={t('prices.reasonRequired')} value={reason} required
        onChange={(e) => setReason(e.target.value)} placeholder={t('prices.sameCoinReason')} />
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
      <div className="flex flex-wrap gap-2">
        <Button type="submit">{t('prices.sameCoinSave')}</Button>
        <Button type="button" variant="ghost" onClick={onCancel}>{t('common.cancel')}</Button>
      </div>
    </form>
  )
}
