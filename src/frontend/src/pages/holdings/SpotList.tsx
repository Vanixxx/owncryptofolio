import { ArrowLeftRight, ChevronDown, History, LineChart } from 'lucide-react'
import { Link } from 'react-router'
import { lazy, Suspense, useEffect, useState, type MouseEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { CoinIcon } from '../../components/CoinIcon'
import { SourceAvatar } from '../../components/SourceLogo'
import { SortSelect } from '../../components/SortSelect'
import { ExportMenu } from '../../components/ExportMenu'
import { SearchField } from '../../components/ui/SearchField'
import { matches } from '../../lib/search'
import { compare } from '../../lib/sort'
import { useStoredSort } from '../../hooks/useStoredSort'
import { Card, ErrorText, Row, Segmented } from '../../components/ui'
import { Tabs } from '../transactions/parts'
import { MergedList } from '../transactions/MergedList'
import { TxViewSwitch, useTxView } from '../transactions/TxView'
import { useErrorText } from '../../lib/useErrorText'
import { Toggle } from '../../components/ui/Toggle'
import { api, type ChangeSpan, type Holding, type PortfolioSummary, type PriceAssetRow, type PricePoint, type TaxHolding } from '../../lib/api'
import { cx } from '../../lib/cx'
import type { SourceRef } from '../../lib/txFilter'
import { date, money, percent, priceText, quantity, trend } from '../../lib/format'
import { Kpi } from './Kpi'
import { Sparkline } from '../prices/Sparkline'
import { ChangeText, SPANS, change, valueChange } from '../prices/Prices'

const SORT_KEYS = ['value', 'unrealized', 'unrealized_pct', 'realized', 'change', 'change_value', 'days', 'name'] as const
type SortKey = (typeof SORT_KEYS)[number]

export function SpotList({ summary: s, items, name, lookup, tz }: {
  summary: PortfolioSummary; items: Holding[]; name: (id: number) => string; lookup: (id: number) => SourceRef; tz: string
}) {
  const { t } = useTranslation()
  const [open, setOpen] = useState<string | null>(null)
  const [showClosed, setShowClosed] = useState(false)
  const held = items.filter((i) => !i.fiat && Number(i.qty) > 0)
  const closed = items.filter((i) => !i.fiat && Number(i.qty) <= 0)
  const cash = items.filter((i) => i.fiat && Number(i.qty) > 0)
  const [sort, setSort] = useStoredSort<SortKey>('ocf.sort.holdings', { key: 'value', desc: true }, SORT_KEYS)
  const pick: Record<SortKey, (h: Holding) => number | string | null> = {
    value: (h) => (h.value === null ? null : Number(h.value)),
    unrealized: (h) => (h.unrealized === null ? null : Number(h.unrealized)),
    unrealized_pct: (h) => (h.unrealized_pct === null ? null : Number(h.unrealized_pct)),
    realized: (h) => Number(h.realized),
    change: (h) => change(prices[h.asset], span),
    change_value: (h) => valueChange(h.value, change(prices[h.asset], span)),
    days: (h) => h.days_held,
    name: (h) => h.asset,
  }
  const [query, setQuery] = useState('')
  // holding periods from the tax lots (ADR 0042): what is past one year, and when the rest is
  const [tax, setTax] = useState<Record<string, TaxHolding>>({})
  // the curve and its change over a chosen span, as on the prices page (Vanixxx, 2026-10-21)
  const [span, setSpanState] = useState<ChangeSpan>(() => {
    try { const v = localStorage.getItem('holdings-span') as ChangeSpan | null; return v && SPANS.includes(v) ? v : 'd90' } catch { return 'd90' }
  })
  const setSpan = (v: ChangeSpan) => { setSpanState(v); try { localStorage.setItem('holdings-span', v) } catch { /* private mode */ } }
  // the change in % or as money on today's holding; a click on it switches every row
  // (Vanixxx, 2026-10-28)
  const [amount, setAmountState] = useState(() => {
    try { return localStorage.getItem('holdings-change-amount') === '1' } catch { return false }
  })
  const flip = (e: MouseEvent) => {
    e.stopPropagation() // the row button would open the details
    setAmountState((v) => { try { localStorage.setItem('holdings-change-amount', v ? '0' : '1') } catch { /* private mode */ } return !v })
  }
  const [prices, setPrices] = useState<Record<string, PriceAssetRow>>({})
  const [spark, setSpark] = useState<{ span: ChangeSpan; data: Record<string, string[]> } | null>(null)
  useEffect(() => {
    api.priceAssets().then((rows) => setPrices(Object.fromEntries(rows.map((r) => [r.asset, r]))), () => {})
  }, [])
  useEffect(() => {
    if (!window.matchMedia('(min-width: 1024px)').matches) return
    let alive = true
    api.priceSparks(span).then((data) => { if (alive) setSpark({ span, data }) }, () => {})
    return () => { alive = false }
  }, [span])
  const curve = (asset: string) => spark?.span === span ? spark.data[asset] ?? [] : span === 'd90' ? prices[asset]?.spark ?? [] : []
  const rising = (asset: string) => { const c = change(prices[asset], span); return c === null ? undefined : c >= 0 }
  useEffect(() => { api.taxHoldings().then(setTax, () => setTax({})) }, [])
  const shown = (showClosed ? [...held, ...closed] : held).filter((h) => matches(query, h.asset, h.name)).sort((a, b) => compare(pick[sort.key](a), pick[sort.key](b), sort.desc))
  const total = Number(s.crypto) || 1

  return (
    <>
      <Card>
        <div className="grid grid-cols-2 gap-x-4 gap-y-3 md:grid-cols-4">
          <Kpi label={t('holdings.value')} value={s.crypto} currency={s.currency} />
          <Kpi label={t('holdings.cost')} value={s.cost} currency={s.currency} />
          <Kpi label={t('holdings.unrealized')} value={s.unrealized} pct={s.unrealized_pct} currency={s.currency} pl />
          <Kpi label={t('holdings.realized')} value={s.realized} pct={s.realized_pct} currency={s.currency} pl />
        </div>
        {cash.length > 0 && (
          <p className="m-0 text-xs text-muted">
            {t('holdings.cash')}: {cash.map((c) => money(c.qty, c.asset)).join(' · ')}
          </p>
        )}
      </Card>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex flex-wrap items-center gap-3">
          <SearchField value={query} onChange={setQuery} placeholder={t('holdings.search')} className="w-full sm:w-56" />
          <SortSelect id="holdings-sort" value={sort} onChange={setSort}
            options={(Object.keys(pick) as SortKey[]).map((k) => ({ value: k, label: t(`holdings.sort.${k}`) }))} />
          <Segmented label={t('prices.spanLabel')} value={span} onChange={setSpan} dense
            options={SPANS.map((x) => ({
              value: x,
              // the clock of the amounts marks the chosen span here as well
              label: amount && x === span
                ? <span className="inline-flex items-center gap-1"><History size={12} aria-hidden="true" />{t(`prices.spans.${x}`)}</span>
                : t(`prices.spans.${x}`),
            }))} />
          <span className="text-sm text-muted">{t('holdings.count', { count: held.length })}</span>
        </span>
        <ExportMenu path="/api/export/holdings" />
        {closed.length > 0 && (
          <Toggle id="show-closed" label={t('holdings.showClosed', { count: closed.length })} checked={showClosed} onChange={setShowClosed} />
        )}
      </div>
      <div className="label hidden grid-cols-[auto_minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.1fr)_auto] lg:grid-cols-[auto_minmax(0,1.3fr)_7.5rem_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.1fr)_auto] gap-3 px-3 md:grid" aria-hidden="true">
        <span className="w-8" /><span>{t('holdings.cols.coin')}</span><span className="hidden lg:block">{t(`prices.spans.${span}`)}</span><span className="text-right">{t('holdings.cols.qty')}</span>
        <span className="text-right">{t('holdings.cols.price')}</span><span className="text-right">{t('holdings.cols.value')}</span><span className="w-[18px]" />
      </div>
      <ul className="m-0 grid list-none gap-2 p-0">
        {shown.map((h) => {
          const dir = trend(h.unrealized)
          const share = h.value ? (Number(h.value) / total) * 100 : 0
          return (
            <li key={h.asset} className={cx('card grid min-w-0 gap-3 p-3', Number(h.qty) <= 0 && 'opacity-70')}>
              {/* phone: icon · name · value; wider: quantity and prices get their own columns */}
              <button type="button" onClick={() => setOpen(open === h.asset ? null : h.asset)} aria-expanded={open === h.asset}
                className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 border-0 bg-transparent p-0 text-left text-fg md:grid-cols-[auto_minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.1fr)_auto] lg:grid-cols-[auto_minmax(0,1.3fr)_7.5rem_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.1fr)_auto]">
                <CoinIcon asset={h.icon} size={32} />
                <span className="grid min-w-0 gap-0.5">
                  <span className="flex min-w-0 items-baseline gap-2">
                    <b className="shrink-0">{h.asset}</b>
                    <span className="truncate text-xs text-muted">{h.name}</span>
                  </span>
                  <span className="num truncate text-xs text-muted md:hidden">{quantity(h.qty)} {h.asset}</span>
                  {/* without the curve (phone, tablet) the change over the span stands here */}
                  <span className="lg:hidden" onClick={flip} title={t('holdings.changeFlip')}><ChangeText a={prices[h.asset]} span={span} amount={amount ? { value: h.value, currency: s.currency } : undefined} /></span>
                  {/* the share of the portfolio as a thin bar: the big positions stand out */}
                  <span className="mt-0.5 h-1 w-full max-w-40 overflow-hidden rounded-full bg-surface-2" aria-hidden="true">
                    <span className="accent-fill block h-full rounded-full" style={{ width: `${Math.min(100, share)}%` }} />
                  </span>
                </span>
                {/* the price over the chosen span with its change, as on the prices page — on the
                    PC only (Vanixxx, 2026-10-14/21) */}
                <span className="hidden justify-items-start gap-0.5 lg:grid">
                  <Sparkline values={curve(h.asset)} up={rising(h.asset)} />
                  <span onClick={flip} title={t('holdings.changeFlip')}><ChangeText a={prices[h.asset]} span={span} amount={amount ? { value: h.value, currency: s.currency } : undefined} /></span>
                </span>
                <span className="hidden justify-items-end md:grid">
                  <span className="num text-sm">{quantity(h.qty)}</span>
                  <span className="text-xs text-muted">{h.asset}</span>
                </span>
                <span className="hidden justify-items-end md:grid">
                  <span className="num text-sm">{h.price ? priceText(Number(h.price), s.currency) : '—'}</span>
                  <span className="num text-xs text-muted">{t('holdings.dcaShort')} {h.avg_price ? priceText(Number(h.avg_price), s.currency) : '—'}</span>
                </span>
                <span className="flex items-center justify-end gap-2">
                  <span className="grid justify-items-end">
                    <b className="num text-sm">{money(h.value, s.currency)}</b>
                    {h.unrealized !== null ? (
                      <span className={cx('num text-xs', dir === 'up' && 'text-up', dir === 'down' && 'text-down')}>
                        {money(h.unrealized, s.currency, true)} {percent(h.unrealized_pct)}
                      </span>
                    ) : (
                      <span className="num text-xs text-muted">{t('holdings.realizedShort')} {money(h.realized, s.currency, true)}</span>
                    )}
                  </span>
                  <ChevronDown size={18} aria-hidden="true" className={cx('text-muted transition-transform', open !== h.asset && '-rotate-90')} />
                </span>
              </button>
              {open === h.asset && <Detail h={h} tax={tax[h.asset]} currency={s.currency} name={name} lookup={lookup} tz={tz} />}
            </li>
          )
        })}
      </ul>
      {s.unvalued.length > 0 && <p className="m-0 text-xs text-muted">{t('holdings.unvalued', { assets: s.unvalued.join(', ') })}</p>}
    </>
  )
}

const PriceChart = lazy(() => import('../prices/PriceChart').then((m) => ({ default: m.PriceChart })))
const RANGES = [90, 365, 10000] as const

/** Tabs like on the transactions page (Vanixxx, 2026-10-08): the facts, and the price with
 * the average buying price as a dashed line — above it the coin is in profit. */
function Detail({ h, tax, currency, name, lookup, tz }: {
  h: Holding; tax?: TaxHolding; currency: string; name: (id: number) => string; lookup: (id: number) => SourceRef; tz: string
}) {
  const { t } = useTranslation()
  const [tab, setTab] = useState<'details' | 'chart' | 'transactions'>('details')
  return (
    <div className="grid gap-3 border-t border-line pt-2">
      <Tabs value={tab} onChange={setTab} tabs={[
        { value: 'details', label: t('merged.tabs.details') },
        { value: 'chart', label: <><LineChart size={14} aria-hidden="true" />{t('holdings.chart')}</> },
        { value: 'transactions', label: <><ArrowLeftRight size={14} aria-hidden="true" />{t('holdings.transactions')}</> },
      ]} />
      {tab === 'details' ? <Facts h={h} tax={tax} currency={currency} name={name} lookup={lookup} tz={tz} />
        : tab === 'chart' ? <CoinChart h={h} currency={currency} />
        : <CoinTransactions h={h} name={name} lookup={lookup} tz={tz} />}
    </div>
  )
}

/** The coin's transactions right here, newest first (Vanixxx, 2026-10-22); the full page is a
 * click away with the coin as its filter. */
function CoinTransactions({ h, name, lookup, tz }: {
  h: Holding; name: (id: number) => string; lookup: (id: number) => SourceRef; tz: string
}) {
  const { t } = useTranslation()
  const [total, setTotal] = useState<number | null>(null)
  const [view, setView] = useTxView('holdings-tx-view')
  return (
    <div className="grid min-w-0 gap-3">
      <span className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs text-muted">{total !== null && t('holdings.transactionCount', { count: total, asset: h.asset })}</span>
        <TxViewSwitch value={view} onChange={setView} />
      </span>
      <MergedList params={{ asset: h.asset }} pageSize={view === 'compact' ? 50 : 25} embedded compact={view === 'compact'} focus={h.asset}
        picking={false} setPicking={() => undefined} name={name} lookup={lookup} tz={tz} reloadKey={0} onTotal={setTotal} />
      <Link to={`/transactions?asset=${encodeURIComponent(h.asset)}`} className="justify-self-start text-sm text-accent no-underline">
        {t('holdings.allTransactions', { asset: h.asset })}
      </Link>
    </div>
  )
}

function CoinChart({ h, currency }: { h: Holding; currency: string }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [range, setRange] = useState<(typeof RANGES)[number]>(365)
  const [points, setPoints] = useState<PricePoint[] | null>(null)
  const [dca, setDca] = useState<{ day: string; value: string | null }[] | null>(null)
  const [error, setError] = useState<unknown>(null)
  useEffect(() => {
    let live = true
    api.priceHistory(h.asset, range).then((p) => { if (live) setPoints(p) }, setError)
    return () => { live = false }
  }, [h.asset, range])
  // the DCA as it was on each day: every buy moves it (Vanixxx, 2026-10-08)
  useEffect(() => {
    let live = true
    api.portfolioDca(h.asset).then((d) => { if (live) setDca(d) }, setError)
    return () => { live = false }
  }, [h.asset])
  return (
    <div className="grid min-w-0 gap-3">
      <Segmented label={t('prices.rangeLabel')} value={String(range)} onChange={(v) => setRange(Number(v) as typeof range)}
        options={RANGES.map((r) => ({ value: String(r), label: t(`prices.ranges.${r}`) }))} />
      {error ? <ErrorText>{errorText(error)}</ErrorText>
        : points === null ? <p className="m-0 text-sm text-muted">{t('common.loading')}</p>
        : points.length === 0 ? <p className="m-0 text-sm text-muted">{t('holdings.noPrices')}</p>
        : (
          <Suspense fallback={<div className="h-64 md:h-72" />}>
            <PriceChart points={points} currency={currency as 'EUR' | 'USD'} steps={dca?.length ? { label: t('holdings.dcaShort'), points: dca } : undefined} />
          </Suspense>
        )}
    </div>
  )
}

function Facts({ h, tax, currency, name, lookup, tz }: {
  h: Holding; tax?: TaxHolding; currency: string; name: (id: number) => string; lookup: (id: number) => SourceRef; tz: string
}) {
  const { t } = useTranslation()
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <div className="grid content-start gap-1.5 text-sm">
        <Row label={t('holdings.avgPrice')}><span className="num">{h.avg_price ? priceText(Number(h.avg_price), currency) : '—'}</span></Row>
        <Row label={t('holdings.price')}><span className="num">{h.price ? priceText(Number(h.price), currency) : '—'}</span></Row>
        <Row label={t('holdings.cost')}><span className="num">{money(h.cost, currency)}</span></Row>
        <Row label={t('holdings.realized')}>
          <span className={cx('num', trend(h.realized) === 'up' && 'text-up', trend(h.realized) === 'down' && 'text-down')}>
            {money(h.realized, currency, true)} {percent(h.realized_pct)}
          </span>
        </Row>
        {Number(h.income) > 0 && <Row label={t('holdings.income')}><span className="num">{money(h.income, currency)}</span></Row>}
        {h.since && <Row label={t('holdings.held')}>{t('holdings.heldSince', { date: date(h.since, tz), count: h.days_held ?? 0 })}</Row>}
        {tax && <Row label={t('holdings.taxFree')}><TaxFree tax={tax} /></Row>}
      </div>
      <div className="grid content-start gap-1.5 text-sm">
        <span className="label">{t('holdings.places')}</span>
        {h.places.length === 0 && <span className="text-muted">—</span>}
        {h.places.map((p) => (
          <div key={`${p.source_id}${p.market}`} className="flex items-center justify-between gap-2">
            <span className="flex min-w-0 items-center gap-2">
              {/* the wallet's logo with the network pinned to it, as on the transactions page */}
              {p.outside ? <span className="w-[22px] shrink-0" aria-hidden="true" /> : <SourceAvatar {...lookup(p.source_id ?? 0)} size={22} />}
              <span className="truncate text-muted">
                {p.outside ? t('holdings.outside') : name(p.source_id ?? 0)}{p.market === 'futures' && ' · Futures'}
              </span>
            </span>
            <span className={cx('num', Number(p.qty) < 0 && 'text-down')}>{quantity(p.qty)}</span>
          </div>
        ))}
        {h.unclear_qty && <p className="m-0 text-xs text-warn">{t('holdings.unclear', { qty: quantity(h.unclear_qty), value: money(h.unclear_value, currency) })}</p>}
        {h.open_qty && <p className="m-0 text-xs text-muted">{t('holdings.openSent', { qty: quantity(h.open_qty) })}</p>}
      </div>
    </div>
  )
}

/** Share past the one-year holding period, and when the next lot gets there (ADR 0042). */
function TaxFree({ tax }: { tax: TaxHolding }) {
  const { t } = useTranslation()
  const share = Number(tax.qty) > 0 ? Math.round((Number(tax.free) / Number(tax.qty)) * 100) : 0
  return (
    <span className="grid justify-items-end text-right">
      <span className={cx('num', share === 100 && 'text-up')}>{t('holdings.taxFreeShare', { share })}</span>
      {tax.next_free && <span className="text-xs text-muted">{t('holdings.taxFreeNext', { date: date(tax.next_free) })}</span>}
    </span>
  )
}
