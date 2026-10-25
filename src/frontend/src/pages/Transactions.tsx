import { ArrowDownWideNarrow, ArrowUpNarrowWide, Link2, Plus } from 'lucide-react'
import { Fragment, useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'
import { useSettings } from '../app/settings'
import { Button, Card, ErrorText, PageHeader } from '../components/ui'
import { api, type ManualEntry, type MergedSummary, type RawRow, type Source, type Wallet } from '../lib/api'
import { entryOf } from '../lib/entry'
import { cx } from '../lib/cx'
import { dateTime } from '../lib/format'
import { iconKind, kindLabel, side } from '../lib/rows'
import { Filters, type Facets } from './transactions/Filters'
import { expandQuery, filterParams, NO_FILTER, sourceLookup, sourceName, type TxFilter } from '../lib/txFilter'
import { KindIcon } from './transactions/KindIcon'
import { MergedList } from './transactions/MergedList'
import { TxViewSwitch, useTxView } from './transactions/TxView'
import { ActionsButton, Sides } from './transactions/parts'
import { useErrorText } from '../lib/useErrorText'
import { Toggle } from '../components/ui/Toggle'
import { ExportMenu } from '../components/ExportMenu'
import { CurrencySwitch } from '../components/CurrencySwitch'
import { RowActions } from './RowActions'
import { EntryForm, type SourceChoice } from './sources/EntryForm'
import { TemplateImport } from './sources/TemplateImport'
import { Modal } from '../components/ui/Modal'
import { Fab } from '../components/ui/Fab'

const PAGE = 100
const FILTER_KEY = 'ocf.tx.filter'
const SIZE_KEY = 'ocf.tx.pageSize'
const PAGE_SIZES = [25, 50, 100, 250, 500] as const

/** M2: the raw rows as the sources deliver them. The merged view replaces this in M5. */
export function Transactions() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const tz = useSettings().settings['general.timezone']
  const [sources, setSources] = useState<Source[]>([])
  // a link may bring a filter along (the gap search: this coin at this source up to that day)
  const [params] = useSearchParams()
  // a link may bring a filter along; without one, the last filter comes back (Vanixxx, 2026-10-08)
  const [filter, setFilterState] = useState<TxFilter>(() => {
    const keys = ['source', 'asset', 'from', 'to', 'kind', 'q', 'show', 'origin'] as const
    if (keys.some((k) => params.get(k))) {
      return { ...NO_FILTER, ...Object.fromEntries(keys.filter((k) => params.get(k)).map((k) => [k, params.get(k)])) }
    }
    try { return { ...NO_FILTER, ...JSON.parse(localStorage.getItem(FILTER_KEY) ?? '{}') } } catch { return NO_FILTER }
  })
  const setFilter = (f: TxFilter) => {
    setFilterState(f)
    try { localStorage.setItem(FILTER_KEY, JSON.stringify(f)) } catch { /* private mode */ }
  }
  const [pageSize, setPageSizeState] = useState<number>(() => {
    try { return PAGE_SIZES.find((n) => n === Number(localStorage.getItem(SIZE_KEY))) ?? 100 } catch { return 100 }
  })
  const setPageSize = (n: number) => {
    setPageSizeState(n)
    try { localStorage.setItem(SIZE_KEY, String(n)) } catch { /* private mode */ }
  }
  const [mergedTotal, setMergedTotal] = useState<number | null>(null)
  const [rows, setRows] = useState<RawRow[]>([])
  const [total, setTotal] = useState<number | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [wallets, setWallets] = useState<Wallet[]>([])
  const [adding, setAdding] = useState<'one' | 'template' | null>(null)
  // a copied transaction opens the form with its values (Vanixxx, 2026-10-08)
  const [copy, setCopy] = useState<{ entry: ManualEntry; sourceId: number; to?: number; n: number } | null>(null)
  // a transfer is copied as "transfer to own wallet/exchange": out, fee, from where to where
  const copyRow = (r: RawRow, to?: number) => {
    const entry = entryOf(r, tz)
    setCopy((old) => ({ entry: to ? { ...entry, kind: 'transfer' as ManualEntry['kind'] } : entry, sourceId: r.source_id, to, n: (old?.n ?? 0) + 1 }))
    setAdding('one'); setSaved(false)
  }
  const closeAdding = useCallback(() => { setAdding(null); setCopy(null) }, [])
  const [saved, setSaved] = useState(false)
  useEffect(() => {
    if (!saved) return
    const id = window.setTimeout(() => setSaved(false), 5000)
    return () => window.clearTimeout(id)
  }, [saved])
  const [showHidden, setShowHidden] = useState(false)
  const [open, setOpen] = useState<number | null>(null)
  const [raw, setRaw] = useState(false)
  const [summary, setSummary] = useState<MergedSummary | null>(null)
  // by time only (Vanixxx, 2026-10-06: sorting by value was not needed): newest or oldest first
  const [desc, setDesc] = useState(true)
  const [reloadKey, setReloadKey] = useState(0)
  // pick two lines and link them (or a transfer and its fee): next to the filters (Vanixxx, 2026-10-06)
  const [picking, setPicking] = useState(false)
  const [view, setView] = useTxView('ocf.tx.view')

  useEffect(() => {
    api.sources().then(setSources, setError)
    api.wallets().then(setWallets, setError)
  }, [])
  // the last row shown: its moment and id, so rows of the same moment are not skipped
  const latest = useRef(0)  // only the newest request fills the list (review 2026-10-25)
  const load = useCallback(async (cursor?: { timestamp: string; id: number }) => {
    const ticket = ++latest.current
    try {
      const page = await api.raw({
        ...filterParams(filter, tz), limit: PAGE, show_hidden: showHidden || undefined, desc: desc ? undefined : 'false',
        ...(cursor ? { [desc ? 'before' : 'after']: cursor.timestamp, cursor_id: cursor.id } : {}),
      })
      if (ticket !== latest.current) return
      setTotal(page.total)
      setRows((old) => (cursor ? [...old, ...page.rows] : page.rows))
    } catch (err) {
      if (ticket === latest.current) setError(err)
    }
  }, [filter, tz, showHidden, desc])
  // load() sets state only after awaiting the server.
  // oxlint-disable-next-line react/set-state-in-effect
  useEffect(() => void load(), [load])

  const changed = () => { setOpen(null); void load(); setReloadKey((k) => k + 1) }
  const name = sourceName(sources, wallets)
  // the search understands the page's own words for kinds, notices and markets:
  // "staub" also asks for the key "dust", "senden" for "send" (Vanixxx, 2026-10-06)
  const query = { ...filterParams(filter, tz), q: expandQuery(filter.q, t) }
  // exactly what the list shows: same filters, same view, same order
  // what the other filters leave, for dimming the rest in the lists
  const [facets, setFacets] = useState<Facets | null>(null)
  const facetKey = JSON.stringify(query)
  useEffect(() => {
    if (raw) return
    let live = true
    api.mergedFacets(JSON.parse(facetKey) as Record<string, string | undefined>).then((f) => { if (live) setFacets(f) }, () => {})
    return () => { live = false }
  }, [facetKey, raw])
  const exportMenu = !raw && <ExportMenu path="/api/export/transactions" params={{ ...query, tz, desc: desc ? undefined : 'false' }} />
  const lookup = sourceLookup(sources, wallets)
  // exchanges first, then every wallet with its networks (ADR 0034)
  const choices: SourceChoice[] = [
    { group: t('pages.sources.exchanges'), options: sources.filter((s) => s.kind === 'exchange').map((s) => ({ id: s.id, label: s.label })) },
    ...wallets.map((w) => ({
      group: w.name,
      options: sources.filter((s) => s.wallet_id === w.id).map((s) => ({ id: s.id, label: s.label })),
    })),
  ].filter((c) => c.options.length > 0)

  return (
    <>
      {/* "add" as a round button floating up right, on the phone and on the PC (Vanixxx, 2026-10-08) */}
      {choices.length > 0 && (
        <Fab label={t('manual.addShort')} onClick={() => { setCopy(null); setAdding('one'); setSaved(false) }}
          className="accent-fill right-4 top-3 md:right-6 md:top-6">
          <Plus size={24} aria-hidden="true" />
        </Fab>
      )}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader title={t('pages.transactions.title')} subtitle={raw ? t('pages.transactions.rawNote') : t('merged.subtitle')} />
          {/* room for the round "add" button up right */}
          <div className="hidden flex-wrap items-center gap-2 md:mr-16 md:flex">{exportMenu}<CurrencySwitch /></div>
      </div>
      {/* a window over the list: the place in it stays (Vanixxx, 2026-10-08) */}
      {adding === 'one' && (
        <Modal label={t('manual.add')} onClose={closeAdding}>
          <EntryForm key={copy?.n ?? 0} choices={choices} tz={tz} copy={copy ?? undefined}
            onCancel={closeAdding} onTemplate={() => setAdding('template')}
            onDone={() => { closeAdding(); setSaved(true); changed() }} />
        </Modal>
      )}
      {adding === 'template' && (
        <Modal label={t('manual.template')} onClose={closeAdding}>
          <TemplateImport choices={choices} exchanges={sources.filter((s) => s.kind === 'exchange').map((s) => s.id)} tz={tz} onImported={changed} onClose={closeAdding} />
        </Modal>
      )}
      {/* where the user is, not at the top of the page */}
      {saved && (
        <p role="status" className="fixed bottom-24 left-1/2 z-40 m-0 -translate-x-1/2 rounded-ctl border border-line bg-surface px-4 py-2.5 text-sm text-up shadow-xl md:bottom-6">
          {t('manual.saved')}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Filters value={filter} onChange={setFilter} sources={sources} wallets={wallets} merged={!raw} summary={summary} facets={raw ? null : facets}
          extra={!raw && (
            <Button variant="ghost" aria-pressed={picking} onClick={() => setPicking(!picking)}>
              <Link2 size={14} aria-hidden="true" />{picking ? t('merged.pick.stop') : t('merged.pick.start')}
            </Button>
          )} phoneExtra={exportMenu} />
        <button type="button" onClick={() => setDesc(!desc)} aria-label={desc ? t('common.descending') : t('common.ascending')}
          title={desc ? t('common.descending') : t('common.ascending')}
          className="inline-flex items-center gap-1.5 rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-muted hover:text-fg">
          {desc ? <ArrowDownWideNarrow size={16} aria-hidden="true" /> : <ArrowUpNarrowWide size={16} aria-hidden="true" />}
          {desc ? t('pages.transactions.newestFirst') : t('pages.transactions.oldestFirst')}
        </button>
        {!raw && <TxViewSwitch value={view} onChange={setView} />}
        {!raw && (
          <label className="flex items-center gap-1.5 text-sm text-muted">
            <select value={pageSize} onChange={(e) => setPageSize(Number(e.target.value))} aria-label={t('pages.transactions.pageSize')}
              className="rounded-ctl border border-line bg-surface-2 px-2 py-2 text-sm text-fg">
              {PAGE_SIZES.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
            {t('pages.transactions.perPage')}
          </label>
        )}
        <Toggle id="show-raw" label={t('merged.rawToggle')} checked={raw} onChange={setRaw} />
        {!raw && mergedTotal !== null && <span className="num ml-auto text-sm text-muted">{t('pages.transactions.total', { count: mergedTotal })}</span>}
        {raw && <Toggle id="show-hidden" label={t('manual.showHidden')} checked={showHidden} onChange={setShowHidden} />}
        {raw && total !== null && (
          <span className="num ml-auto text-sm text-muted">{t('pages.transactions.total', { count: total })}</span>
        )}
      </div>
      <ErrorText>{error ? errorText(error) : null}</ErrorText>

      {!raw ? (
        <MergedList compact={view === 'compact'} pageSize={pageSize} onTotal={setMergedTotal} onCopy={copyRow} picking={picking} setPicking={setPicking} onSummary={setSummary} name={name} lookup={lookup} params={{ ...query, desc: desc ? undefined : 'false' }} tz={tz} reloadKey={reloadKey} />
      ) : total === null ? (
        <p className="text-sm text-muted">{t('common.loading')}</p>
      ) : rows.length === 0 ? (
        <Card><p className="m-0 text-sm text-muted">{t('pages.transactions.empty')}</p></Card>
      ) : (
        <>
          {/* Phone: one card per row (a twelve-column table is unusable on a phone, ADR 0013). */}
          <ul className="m-0 grid list-none gap-2 p-0 md:hidden">
            {rows.map((r) => (
              <li key={r.id} className="card grid gap-1.5 p-3">
                <div className={cx('grid gap-1.5', (r.covered_by_api || r.state !== 'current') && 'opacity-55')}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex min-w-0 items-center gap-2.5"><KindIcon kind={iconKind(r)} /><b className="truncate text-sm">{kindLabel(t, r)}</b></span>
                    <span className="flex items-center gap-1 text-xs text-muted">
                      {dateTime(r.timestamp, tz)}
                      <ActionsButton id={r.id} open={open} setOpen={setOpen} />
                    </span>
                  </div>
                  <Sides r={r} />
                  <span className="text-xs text-muted">{name(r.source_id)} · {t(`pages.sources.channels.${r.channel}`)}
                    {r.covered_by_api && <> · {t('pages.transactions.coveredByApi')}</>}
                    {r.state !== 'current' && <> · {t(`manual.states.${r.state}`)}</>}
                    {r.state === 'current' && r.edited && r.channel === 'manual' && <> · {t('manual.edited')}</>}</span>
                </div>
                {open === r.id && <RowActions row={r} tz={tz} onChanged={changed} />}
              </li>
            ))}
          </ul>
          <div className="card hidden overflow-x-auto p-0 md:block">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="text-left">
                  {['time', 'kind', 'incoming', 'outgoing', 'fee', 'source'].map((c) => (
                    <th key={c} className="label border-b border-line px-3 py-2.5 font-normal">{t(`pages.transactions.${c}`)}</th>
                  ))}
                  <th className="border-b border-line px-1"><span className="sr-only">{t('manual.actions')}</span></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <Fragment key={r.id}>
                  <tr className={cx('border-b border-line last:border-b-0', (r.covered_by_api || r.state !== 'current') && 'opacity-55')}
                    title={r.covered_by_api ? t('pages.transactions.coveredByApi') : r.comment ?? undefined}>
                    <td className="num whitespace-nowrap px-3 py-2 text-muted">{dateTime(r.timestamp, tz)}</td>
                    <td className="px-3 py-2"><span className="flex items-center gap-2"><KindIcon kind={iconKind(r)} className="h-6 w-6" />{kindLabel(t, r)}</span></td>
                    <td className="num px-3 py-2 text-up">{side(r.incoming, '+')}</td>
                    <td className="num px-3 py-2 text-down">{side(r.outgoing, '−')}</td>
                    <td className="num px-3 py-2 text-muted">{side(r.fee, '')}</td>
                    <td className="px-3 py-2 text-muted">{name(r.source_id)} · {t(`pages.sources.channels.${r.channel}`)}
                      {r.state !== 'current' && <> · {t(`manual.states.${r.state}`)}</>}
                      {r.state === 'current' && r.edited && r.channel === 'manual' && <> · {t('manual.edited')}</>}</td>
                    <td className="px-1 py-1"><ActionsButton id={r.id} open={open} setOpen={setOpen} /></td>
                  </tr>
                  {open === r.id && (
                    <tr className="border-b border-line"><td colSpan={7} className="px-3 py-3"><RowActions row={r} tz={tz} onChanged={changed} /></td></tr>
                  )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
          {rows.length < (total ?? 0) && (
            <Button variant="ghost" className="justify-self-center" onClick={() => void load(rows[rows.length - 1])}>
              {t('pages.transactions.loadMore')}
            </Button>
          )}
        </>
      )}
    </>
  )
}

