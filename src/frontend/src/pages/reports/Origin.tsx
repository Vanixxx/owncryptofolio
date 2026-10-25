import { ChevronRight, Download } from 'lucide-react'
import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { locale } from '../../i18n'
import { useSearchParams } from 'react-router'
import { useSettings } from '../../app/settings'
import { Button, Card, ErrorText, Segmented } from '../../components/ui'
import { api, type OriginData, type OriginNode, type OriginStep, type PlannedOption } from '../../lib/api'
import { cx } from '../../lib/cx'
import { date, dateTime, money, quantity } from '../../lib/format'
import { matches } from '../../lib/search'
import { useErrorText } from '../../lib/useErrorText'

// ECharts is large: loaded with the first diagram shown
const OriginFlow = lazy(() => import('./OriginFlow').then((m) => ({ default: m.OriginFlow })))
const PAGE = 40
type Kind = 'all' | 'sale' | 'transfer' | 'withdrawal' | 'payment'
const COLORS: Record<string, string> = {
  bank: 'bg-accent', card: 'bg-[#8b7cf6]', gain: 'bg-up', income: 'bg-[#e0a33a]', futures: 'bg-[#3aa7e0]',
  unknown: 'bg-warn', money_unknown: 'bg-down', loss: 'bg-down',
}

/** The bar shows what came in; a loss (negative) is listed below it, not drawn. */
function Bar({ parts, total, thin = false }: { parts: [string, string][]; total?: string; thin?: boolean }) {
  const plus = parts.filter(([, v]) => Number(v) > 0)
  const sum = plus.reduce((n, [, v]) => n + Number(v), 0) || Number(total) || 1
  return (
    <span className={cx('flex w-full overflow-hidden rounded-full bg-surface-2', thin ? 'h-1.5' : 'h-3')} aria-hidden="true">
      {plus.map(([k, v]) => <span key={k} className={COLORS[k]} style={{ width: `${Number(v) / sum * 100}%` }} />)}
    </span>
  )
}

const CHANNELS = ['api', 'chain', 'file', 'manual'] as const

/** A few sentences from a fixed pattern, as in the PDF (Blockpit lets an AI write them). */
function summaryText(t: (k: string, o?: Record<string, unknown>) => string, d: OriginData, tz: string): string {
  const x = d.target
  const qty = `${quantity(x.qty)} ${x.asset}`
  const day = x.at.length === 10 ? date(x.at, 'UTC') : date(x.at, tz)
  const mix = Object.fromEntries(d.mix.map((m) => [m.kind, m.value]))
  const out = [t(`origin.summary.${x.kind}`, {
    day, qty, place: x.place ?? t('holdings.outside'), to: x.to ?? t('holdings.outside'),
    into: x.into_asset ? `${quantity(x.into_qty)} ${x.into_asset}` : '', amount: money(x.amount),
  })]
  const own = (['bank', 'card'] as const).filter((k) => mix[k]).map((k) => t(`origin.summary.own_${k}`, { amount: money(mix[k]) }))
  if (own.length) out.push(t('origin.summary.own', { list: own.join(t('origin.summary.and')) }))
  const more = (['gain', 'income', 'futures', 'loss', 'unknown', 'money_unknown'] as const).filter((k) => mix[k])
    .map((k) => `${t(`origin.leaf.${k}`)} ${money(mix[k])}`)
  if (more.length) out.push(t('origin.summary.more', { list: more.join(', ') }))
  const ov = d.overview
  if (ov?.transactions && ov.from && ov.to) {
    out.push(t('origin.summary.chain', { count: ov.transactions, sources: ov.sources.length, from: date(ov.from, tz), to: date(ov.to, tz) }))
  }
  return out.join(' ')
}

/** Source of funds (ADR 0046): where the money of a sale, a transfer (own wallets too) or a
 * withdrawal came from — split by origin and as a chain back to the deposits, as PDF. */
export function Origin() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const of = params.get('of') === 'holdings' ? 'holdings' : params.get('of') === 'planned' ? 'planned' : 'steps'
  const pickOf = (v: 'steps' | 'holdings' | 'planned') => {
    const next = new URLSearchParams(params)
    next.delete('row')
    next.delete('asset')
    if (v !== 'steps') next.set('of', v)
    else next.delete('of')
    setParams(next, { replace: true })
  }
  return (
    <div className="grid gap-4">
      <Segmented label={t('origin.ofLabel')} value={of} onChange={pickOf}
        options={[{ value: 'steps', label: t('origin.of.steps') }, { value: 'holdings', label: t('origin.of.holdings') }, { value: 'planned', label: t('origin.of.planned') }]} />
      {of === 'holdings' ? <Holdings /> : of === 'planned' ? <Planned /> : <Steps />}
    </div>
  )
}

/** A step not done yet, as Blockpit offers it (Vanixxx, 2026-10-17): which holdings it would
 * take now in the tax order and where their money came from. Nothing is booked. */
function Planned() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const tz = useSettings().settings['general.timezone']
  const [options, setOptions] = useState<PlannedOption[] | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [day, setDay] = useState(() => new Date().toISOString().slice(0, 10))
  const [source, setSource] = useState('')
  const [asset, setAsset] = useState('')
  const [qty, setQty] = useState('')
  const [made, setMade] = useState<{ source: number; asset: string; qty: string; day: string } | null>(null)
  useEffect(() => { api.originPlannedOptions().then(setOptions, setError) }, [])
  const sources = useMemo(() => [...new Map((options ?? []).map((o) => [o.source, o.place ?? t('holdings.outside')])).entries()], [options, t])
  const coins = (options ?? []).filter((o) => String(o.source) === source)
  const held = coins.find((o) => o.asset === asset)
  const tooMuch = !!held && Number(qty.replace(',', '.')) > Number(held.qty)
  const field = 'rounded-ctl border border-line bg-surface-2 px-3 py-2 text-base text-fg'
  return (
    <div className="grid gap-4">
      <p className="m-0 text-sm leading-relaxed text-muted">{t('origin.plannedIntro')}</p>
      <form className="card grid gap-3 p-4 sm:grid-cols-2" onSubmit={(e) => {
        e.preventDefault()
        setMade({ source: Number(source), asset, qty: qty.trim().replace(',', '.'), day })
      }}>
        <label className="grid gap-1.5 text-sm"><span className="label">{t('origin.plannedDay')}</span>
          <input type="date" value={day} onChange={(e) => setDay(e.target.value)} required className={field} /></label>
        <label className="grid gap-1.5 text-sm"><span className="label">{t('origin.plannedSource')}</span>
          <select value={source} onChange={(e) => { setSource(e.target.value); setAsset(''); setQty('') }} required className={field}>
            <option value="" disabled>{t('origin.choose')}</option>
            {sources.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </select></label>
        <label className="grid gap-1.5 text-sm"><span className="label">{t('origin.plannedAsset')}</span>
          <select value={asset} onChange={(e) => { setAsset(e.target.value); setQty('') }} required disabled={!source} className={field}>
            <option value="" disabled>{t('origin.choose')}</option>
            {coins.map((o) => <option key={o.asset} value={o.asset}>{o.asset} · {quantity(o.qty)}</option>)}
          </select></label>
        <label className="grid gap-1.5 text-sm"><span className="label">{t('origin.plannedQty')}</span>
          <span className="flex gap-2">
            <input inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value)} required disabled={!asset} className={cx(field, 'num min-w-0 flex-1')} />
            {held && <Button type="button" variant="ghost" onClick={() => setQty(held.qty)}>{t('origin.all')}</Button>}
          </span>
          {held && <span className={cx('text-xs', tooMuch ? 'text-warn' : 'text-muted')}>{t('origin.held', { qty: quantity(held.qty), asset })}</span>}</label>
        <div className="sm:col-span-2"><Button type="submit" disabled={!asset || !qty || tooMuch}>{t('origin.plannedMake')}</Button></div>
      </form>
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
      {made && (
        <Detail id={`planned-${made.source}-${made.asset}-${made.qty}-${made.day}`}
          load={() => api.originPlanned(made.source, made.asset, made.qty, made.day)}
          file={(k) => api.originPlannedFile(k, made.source, made.asset, made.qty, made.day)} tz={tz} onClose={() => setMade(null)} />
      )}
    </div>
  )
}

/** Where today's holdings came from: all, and per coin with its chain (Vanixxx, 2026-10-17). */
function Holdings() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const tz = useSettings().settings['general.timezone']
  const [params, setParams] = useSearchParams()
  const asset = params.get('asset')
  const [all, setAll] = useState<OriginData | null>(null)
  const [error, setError] = useState<unknown>(null)
  useEffect(() => { api.originHoldings().then(setAll, setError) }, [])
  const pick = (a: string | null) => {
    const next = new URLSearchParams(params)
    if (a === null) next.delete('asset')
    else next.set('asset', a)
    setParams(next, { replace: true })
  }
  return (
    <div className="grid gap-4">
      <p className="m-0 text-sm leading-relaxed text-muted">{t('origin.holdingsIntro')}</p>
      {asset && <Detail id={`asset-${asset}`} load={() => api.originHoldings(asset)} file={(k) => api.originHoldingsFile(k, asset)} tz={tz} onClose={() => pick(null)} />}
      {!asset && <Detail id="all" load={() => api.originHoldings()} file={(k) => api.originHoldingsFile(k)} tz={tz} />}
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
      {all && (
        <ul className="m-0 grid list-none gap-1.5 p-0">
          {(all.coins ?? []).map((c) => (
            <li key={c.asset}>
              <button type="button" onClick={() => { pick(c.asset); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
                className={cx('card grid w-full gap-1.5 p-3 text-left text-sm hover:bg-surface-2', asset === c.asset && 'ring-1 ring-accent')}>
                <span className="flex items-center justify-between gap-3">
                  <b className="num truncate">{quantity(c.qty)} {c.asset}</b>
                  <span className="flex shrink-0 items-center gap-1.5"><span className="num">{money(c.value)}</span><ChevronRight size={15} aria-hidden="true" className="text-muted" /></span>
                </span>
                <Bar parts={Object.entries(c.mix)} total={c.value} thin />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Steps() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const tz = useSettings().settings['general.timezone']
  const [params, setParams] = useSearchParams()
  const picked = Number(params.get('row')) || null
  const [list, setList] = useState<OriginStep[] | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [kind, setKind] = useState<Kind>('all')
  const [query, setQuery] = useState('')
  const [shown, setShown] = useState(PAGE)
  useEffect(() => { api.originList().then(setList, setError) }, [])
  const pick = (row: number | null) => {
    const next = new URLSearchParams(params)
    if (row === null) next.delete('row')
    else next.set('row', String(row))
    setParams(next, { replace: true })
  }
  const items = useMemo(() => (list ?? [])
    .filter((x) => kind === 'all' || x.kind === kind || (kind === 'sale' && x.kind === 'swap'))
    .filter((x) => matches(query, x.asset, x.place ?? '', x.to ?? '', x.at.slice(0, 4))), [list, kind, query])

  return (
    <div className="grid gap-4">
      <p className="m-0 text-sm leading-relaxed text-muted">{t('origin.intro')}</p>
      {picked !== null && (
        <Detail id={`row-${picked}`} load={() => api.origin(picked)} file={(k) => api.originFile(picked, k)} tz={tz} onClose={() => pick(null)} />
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Segmented label={t('origin.kindLabel')} value={kind} onChange={(v) => { setKind(v); setShown(PAGE) }}
          options={(['all', 'sale', 'transfer', 'withdrawal', 'payment'] as const).map((k) => ({ value: k, label: t(`origin.kinds.${k}`) }))} />
        <input type="search" value={query} onChange={(e) => { setQuery(e.target.value); setShown(PAGE) }} placeholder={t('origin.search')}
          aria-label={t('origin.search')} className="min-w-0 flex-1 rounded-ctl border border-line bg-surface-2 px-3 py-2 text-base text-fg" />
      </div>
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
      {list === null ? <p className="m-0 text-sm text-muted">{t('common.loading')}</p> : items.length === 0 ? (
        <p className="m-0 text-sm text-muted">{t('origin.empty')}</p>
      ) : (
        <ul className="m-0 grid list-none gap-1.5 p-0">
          {items.slice(0, shown).map((x) => (
            <li key={x.row}>
              <button type="button" onClick={() => { pick(x.row); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
                className={cx('card flex w-full items-center justify-between gap-3 p-3 text-left text-sm hover:bg-surface-2', picked === x.row && 'ring-1 ring-accent')}>
                <span className="grid min-w-0 gap-0.5">
                  <b className="num truncate">{t(`origin.kinds.${x.kind}`)} · {quantity(x.qty)} {x.asset}{x.into_asset ? ` → ${quantity(x.into_qty)} ${x.into_asset}` : ''}</b>
                  <span className="truncate text-xs text-muted">{dateTime(x.at, tz)} · {x.place ?? t('holdings.outside')}{x.to ? ` → ${x.to}` : ''}</span>
                </span>
                <span className="flex shrink-0 items-center gap-1.5"><span className="num">{money(x.value)}</span><ChevronRight size={15} aria-hidden="true" className="text-muted" /></span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {items.length > shown && (
        <Button variant="ghost" className="justify-self-start" onClick={() => setShown((n) => n + PAGE * 4)}>
          {t('tax.more', { count: items.length - shown })}
        </Button>
      )}
    </div>
  )
}

function Detail({ id, load, file, tz, onClose }: {
  id: string; load: () => Promise<OriginData>; file: (kind: 'pdf' | 'xlsx') => string; tz: string; onClose?: () => void
}) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [data, setData] = useState<{ id: string; d: OriginData } | null>(null)
  const [error, setError] = useState<unknown>(null)
  useEffect(() => {
    let live = true
    load().then((d) => { if (live) { setData({ id, d }); setError(null) } }, (e) => { if (live) setError(e) })
    return () => { live = false }
    // the id names what is loaded
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [id])
  const d = data?.id === id ? data.d : null
  const today = d && (d.target.kind === 'holding' || d.target.kind === 'holdings')
  const [flow, setFlow] = useState<'simple' | 'full' | 'off'>('simple')
  const when = d && (d.target.at.length === 10 ? date(d.target.at, 'UTC') : dateTime(d.target.at, tz))
  return (
    <Card title={t('origin.title')} action={onClose && <Button variant="ghost" onClick={onClose}>{t('common.close')}</Button>}>
      {error ? <ErrorText>{errorText(error)}</ErrorText> : !d ? <p className="m-0 text-sm text-muted">{t('common.loading')}</p> : (
        <>
          <div className="grid gap-0.5">
            <span className="label">{t(`origin.kinds.${d.target.kind}`)} · {when}</span>
            <b className="num text-lg">{d.target.kind !== 'holdings' && <>{quantity(d.target.qty)} {d.target.asset}{d.target.into_asset ? ` → ${quantity(d.target.into_qty)} ${d.target.into_asset}` : ''} · </>}{money(d.target.amount)}</b>
            {!today && <span className="text-xs text-muted">{d.target.place ?? t('holdings.outside')}{d.target.to ? ` → ${d.target.to}` : ''}</span>}
          </div>
          <p className="m-0 text-sm leading-relaxed">{summaryText(t, d, tz)}</p>
          {d.overview && d.overview.transactions > 0 && (
            <dl className="m-0 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
              {[
                [t('origin.ov.span'), `${date(d.overview.from, tz)} – ${date(d.overview.to, tz)}`],
                [t('origin.ov.transactions'), String(d.overview.transactions)],
                [t('origin.ov.sources'), String(d.overview.sources.length)],
                [t('origin.ov.channels'), CHANNELS.filter((c) => d.overview?.channels[c]).map((c) => `${t(`origin.channel.${c}`)} ${d.overview?.channels[c]}`).join(', ')],
              ].map(([k, v]) => (
                <div key={k} className="grid gap-0.5 rounded-ctl bg-surface-2 px-2.5 py-1.5">
                  <dt className="label">{k}</dt><dd className="num m-0">{v}</dd>
                </div>
              ))}
            </dl>
          )}
          <div className="grid gap-2">
            <Bar parts={d.mix.map((m) => [m.kind, m.value])} />
            <ul className="m-0 grid list-none gap-1 p-0 text-sm">
              {d.mix.map((m) => (
                <li key={m.kind} className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-2"><span className={cx('h-2.5 w-2.5 shrink-0 rounded-full', COLORS[m.kind])} />{t(`origin.leaf.${m.kind}`)}</span>
                  <span className={cx('num shrink-0', Number(m.value) < 0 && 'text-down')}>{money(m.value)} <span className="text-xs text-muted">{Number(m.share).toLocaleString(locale(), { maximumFractionDigits: 1 })} %</span></span>
                </li>
              ))}
            </ul>
          </div>
          {d.diagram && (
            <div className="grid gap-2">
              <Segmented label={t('origin.flow.label')} value={flow} onChange={setFlow}
                options={[{ value: 'simple', label: t('origin.flow.simple') }, { value: 'full', label: t('origin.flow.full', { count: d.diagram.full.nodes.length }) }, { value: 'off', label: t('origin.flow.off') }]} />
              {flow === 'full' && d.diagram.full.nodes.length > 40 && <p className="m-0 text-xs text-muted">{t('origin.flow.big', { count: d.diagram.full.nodes.length })}</p>}
              {flow !== 'off' && (
                <Suspense fallback={<div className="h-80" />}>
                  <OriginFlow data={d.diagram[flow]} full={flow === 'full'} tz={tz} />
                </Suspense>
              )}
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            {(['pdf', 'xlsx'] as const).map((k) => (
              <a key={k} href={file(k)} download
                className="inline-flex items-center gap-1.5 rounded-ctl border border-line px-3 py-2 text-sm text-fg no-underline hover:bg-surface-2">
                <Download size={15} aria-hidden="true" />{t(`tax.file.${k}`)}
              </a>
            ))}
          </div>
          {d.deposits && d.deposits.length > 0 && (
            <details className="grid gap-1.5">
              <summary className="label cursor-pointer">{t('origin.deposits', { count: d.deposits.length })}</summary>
              <ul className="m-0 mt-1.5 grid list-none gap-1 p-0 text-sm">
                {[...d.deposits].sort((a, b) => a.at.localeCompare(b.at)).map((x, i) => (
                  <li key={i} className="grid gap-0.5 rounded-ctl bg-surface-2 px-2.5 py-1.5">
                    <span className="flex items-baseline justify-between gap-3">
                      <span>{date(x.at, tz)} · {x.place ?? t('holdings.outside')} · {t(`origin.paid.${x.kind}${x.detail === 'direct' ? 'Direct' : ''}`)}</span>
                      <span className="num shrink-0">{money(x.share)}</span>
                    </span>
                    <span className="flex flex-wrap gap-x-2 text-xs text-muted">
                      <span>{t('origin.ofAmount', { amount: money(x.value) })}</span>
                      {x.channel && <span>{t(`origin.channel.${x.channel}`)}</span>}
                      {x.tx && <span className="truncate font-mono">Tx {x.tx}</span>}
                    </span>
                  </li>
                ))}
              </ul>
            </details>
          )}
          {d.overview && d.overview.sources.length > 0 && (
            <details className="grid gap-1.5">
              <summary className="label cursor-pointer">{t('origin.sourcesTitle', { count: d.overview.sources.length })}</summary>
              <ul className="m-0 mt-1.5 grid list-none gap-1 p-0 text-sm">
                {d.overview.sources.map((x, i) => (
                  <li key={i} className="grid gap-0.5 rounded-ctl bg-surface-2 px-2.5 py-1.5">
                    <span className="flex items-baseline justify-between gap-3">
                      <span>{x.place ?? t('holdings.outside')} · {t(`origin.sourceKind.${x.kind}`)}</span>
                      <span className="num shrink-0 text-xs text-muted">{t('origin.steps', { count: x.count })}</span>
                    </span>
                    <span className="flex flex-wrap gap-x-2 text-xs text-muted">
                      {CHANNELS.filter((c) => x.channels[c]).map((c) => <span key={c}>{t(`origin.channel.${c}`)} {x.channels[c]}</span>)}
                      {x.address && <span className="truncate font-mono">{x.address}</span>}
                    </span>
                  </li>
                ))}
              </ul>
            </details>
          )}
          <div className="grid gap-1.5">
            <span className="label">{t('origin.chain')}</span>
            <ul className="m-0 grid list-none gap-1 p-0"><Branch n={d.tree} tz={tz} depth={0} /></ul>
          </div>
          <p className="m-0 text-xs leading-relaxed text-muted">
            {t('origin.hint', { method: d.method.toUpperCase() })}
            {d.lost.count > 0 && <> {t('origin.lost', { assets: d.lost.assets.join(', ') })}</>}
          </p>
        </>
      )}
    </Card>
  )
}

function Branch({ n, tz, depth }: { n: OriginNode; tz: string; depth: number }) {
  const { t } = useTranslation()
  // the first levels open, deeper ones on request: chains through many swaps get long
  // a coin under all holdings starts closed: the whole list would be pages long
  const [open, setOpen] = useState(depth < 3 && !(n.kind === 'holding' && depth > 0))
  const kids = n.children ?? []
  const label = n.kind === 'small' || n.kind === 'more'
    ? t(`origin.${n.kind}`, { count: n.count, mix: Object.keys(n.mix ?? {}).map((k) => t(`origin.leaf.${k}`)).join(', ') })
    : n.kind === 'gain' && n.detail === 'until_transfer' ? t('origin.gainUntilTransfer')
    : n.kind === 'gain' && n.detail === 'unrealized' ? t('origin.gainUnrealized')
    : n.kind === 'loss' && n.detail === 'unrealized' ? t('origin.lossUnrealized')
    : n.kind === 'loss' && n.detail === 'until_transfer' ? t('origin.lossUntilTransfer')
      : [
          n.detail === 'direct' ? t(`origin.direct.${n.kind}`)
            : t(`origin.leaf.${n.kind}`, { defaultValue: t(`origin.kinds.${n.kind}`, { defaultValue: n.kind }) }) + (n.kind === 'income' && n.detail ? ` (${n.detail})` : ''),
          n.qty && n.kind !== 'gain' && n.kind !== 'holdings' ? `${quantity(n.qty)} ${n.asset}${n.into_asset ? ` → ${quantity(n.into_qty)} ${n.into_asset}` : ''}` : null,
          n.place !== undefined && n.kind !== 'gain' ? (n.place ?? t('holdings.outside')) + (n.to ? ` → ${n.to}` : '') : null,
          n.at ? date(n.at, tz) : null,
        ].filter(Boolean).join(' · ')
  return (
    <li className="grid gap-1" style={{ marginLeft: depth ? `${Math.min(depth, 6) * 0.9}rem` : undefined }}>
      <div className={cx('flex items-start justify-between gap-3 rounded-ctl px-2.5 py-1.5 text-sm', depth === 0 ? 'bg-surface-2 font-semibold' : 'bg-surface-2/60')}>
        <span className="flex min-w-0 items-start gap-1.5">
          {kids.length > 0 ? (
            <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="mt-0.5 shrink-0 text-muted" aria-label={t('origin.toggle')}>
              <ChevronRight size={14} className={cx('transition-transform', open && 'rotate-90')} />
            </button>
          ) : <span className="w-3.5 shrink-0" />}
          <span className="grid min-w-0 gap-0.5">
            <span className="num [overflow-wrap:anywhere]">{label}</span>
            {n.tx && <span className="truncate font-mono text-[0.68rem] text-muted" title={n.tx}>Tx {n.tx}</span>}
          </span>
        </span>
        <span className={cx('num shrink-0', Number(n.share) < 0 && 'text-down')}>{money(n.share)}</span>
      </div>
      {open && kids.length > 0 && <ul className="m-0 grid list-none gap-1 p-0">{kids.map((k, i) => <Branch key={i} n={k} tz={tz} depth={depth + 1} />)}</ul>}
    </li>
  )
}
