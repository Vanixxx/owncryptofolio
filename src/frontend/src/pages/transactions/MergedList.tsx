import { CheckSquare, ChevronDown, Copy, CreditCard, Hand, Eye, EyeOff, Info, Landmark, Receipt, Sparkles, Tag, Trash2, Undo2, History, Layers, Link2, Pencil, Search, Square, Unlink, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { locale } from '../../i18n'
import { useSettings } from '../../app/settings'
import { Button, Card, ErrorText, StatusPill } from '../../components/ui'
import { Confirm } from '../../components/ui/Confirm'
import {
  api, type MergedItem, type MergedRow, type MergedSummary, type TradeResult, type TransferCandidate,
} from '../../lib/api'
import { cx } from '../../lib/cx'
import { dateTime, money, percent, priceText, quantity, trend } from '../../lib/format'
import { iconKind, kindLabel, side } from '../../lib/rows'
import { useErrorText } from '../../lib/useErrorText'
import { RowActions, RowVersions } from '../RowActions'
import { EntryForm } from '../sources/EntryForm'
import { entryOf } from '../../lib/entry'
import { SourceAvatar } from '../../components/SourceLogo'
import type { SourceRef } from '../../lib/txFilter'
import { ActionMenu, ActionsButton, Sides, Tabs } from './parts'
import { TaxTab } from './TaxTab'
import { rateText, tradeRate } from '../../lib/rate'
import { Flow, TxShell } from './Card'
import { AllVersions, Details, Origin, SingleList, type Single } from './Details'
import { TransferForm } from './TransferForm'
import { CompactLine } from './CompactLine'

type Show = 'normal' | 'clean' | 'short' | 'auto' | 'open' | 'ambiguous' | 'dust' | 'spam' | 'edited' | 'noted' | 'marked' | 'mcp'
/** Where the list was left: same filter → back to that place, that line open (Vanixxx, 2026-10-08). */
const PLACE = 'ocf.tx.place'
type Place = { key: string; count: number; y: number; open: number[] | number | null }
function readPlace(): Place | null {
  try { return JSON.parse(localStorage.getItem(PLACE) ?? 'null') as Place | null } catch { return null }
}

/** Only going out: a fee, an "other" deduction — it may belong to a transfer as its fee. */
const feeLike = (r: MergedRow) => !r.incoming[0] && !!(r.outgoing[0] || r.fee[0])
/** What a row counts as when picking: half of a transfer, or a fee for one. */
const pickKind = (r: MergedRow) => (r.kind === 'send' || r.kind === 'receive' ? r.kind : feeLike(r) ? 'fee' : null)

/** One line per transfer, spam out, open sends to explain (ADR 0005, 0039). */
export function MergedList({ name, lookup, params, tz, reloadKey, onSummary, picking, setPicking, onCopy, pageSize = 100, onTotal, embedded = false, compact = false, focus }: {
  name: (id: number) => string; lookup: (id: number) => SourceRef; params: Record<string, string | undefined>; tz: string; reloadKey: number
  onSummary?: (s: MergedSummary) => void; picking: boolean; setPicking: (v: boolean) => void
  /** start a new entry from this row's values; a transfer passes where it went */
  onCopy?: (row: MergedRow, to?: number) => void
  pageSize?: number; onTotal?: (n: number) => void
  /** inside another page: no hint line, and the transactions page keeps its own place */
  embedded?: boolean
  /** one short line per transaction, a tap opens it as the full card (Vanixxx, 2026-10-22) */
  compact?: boolean
  /** the coin the list is about (holdings): compact lines show only it */
  focus?: string
}) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  // the notice filter lives with the other filters (Vanixxx, 2026-10-06)
  const show = (params.show ?? 'normal') as Show
  const [items, setItems] = useState<MergedItem[]>([])
  const [total, setTotal] = useState<number | null>(null)
  const [summary, setSummary] = useState<MergedSummary | null>(null)
  // several lines may be open at once (Vanixxx, 2026-10-09)
  const [opened, setOpened] = useState<Set<number>>(() => new Set())
  const toggleLine = (id: number) => setOpened((old) => { const n = new Set(old); if (n.has(id)) n.delete(id); else n.add(id); return n })
  const showLine = (id: number) => setOpened((old) => (old.has(id) ? old : new Set(old).add(id)))
  // a futures position goes by its first booking, negative to stay apart from row ids
  const lineId = (i: MergedItem) => (i.type === 'transfer' ? i.send.id : i.type === 'row' ? i.row.id : -i.row_ids[0])
  const [error, setError] = useState<unknown>(null)
  // pick two lines and link them, no suggestion needed (Vanixxx, 2026-10-06)
  type Pick = { kind: string; dust: boolean }
  const [picked, setPicked] = useState<Record<number, Pick>>({})
  const [busy, setBusy] = useState(false)
  // a new round of picking starts empty
  const [wasPicking, setWasPicking] = useState(picking)
  if (wasPicking !== picking) { setWasPicking(picking); setPicked({}) }
  const ofKind = (kind: string) => Object.entries(picked).filter(([, p]) => p.kind === kind).map(([id]) => Number(id))
  const pickedIds = Object.keys(picked).map(Number)
  // dust suggestions picked (and nothing else): handled in one go (Vanixxx, 2026-10-06)
  const pickedDust = Object.entries(picked).filter(([, p]) => p.dust).map(([id]) => Number(id))
  const onlyDust = pickedDust.length > 0 && pickedDust.length === pickedIds.length
  const pickedSend = ofKind('send'), pickedRecv = ofKind('receive'), pickedFee = ofKind('fee'), pickedTransfer = ofKind('transfer')
  // a transfer and its fee bookings (a small send counts as one too): attach them
  const attachable = pickedTransfer.length === 1 && pickedRecv.length === 0 && pickedFee.length + pickedSend.length > 0
  const linkable = pickedSend.length === 1 && pickedRecv.length === 1 && pickedFee.length === 0 && pickedTransfer.length === 0
  const togglePick = (id: number, kind: string, dust = false) => setPicked((old) => {
    const next = { ...old }
    if (next[id]) delete next[id]
    else next[id] = { kind, dust }
    return next
  })
  const pickOf = (i: MergedItem): [number, Pick] | null => i.type === 'transfer'
    ? [i.send.id, { kind: 'transfer', dust: false }]
    : i.type === 'row' && pickKind(i.row) ? [i.row.id, { kind: pickKind(i.row)!, dust: i.dust }] : null
  // everything the current filter shows, not only the loaded page
  async function pickAll() {
    setBusy(true)
    try {
      const all: Record<number, Pick> = {}
      for (let offset = 0; ; offset += 500) {
        const page = await api.merged({ ...params, offset, limit: 500 })
        for (const i of page.items) { const p = pickOf(i); if (p) all[p[0]] = p[1] }
        if (offset + 500 >= page.total) break
      }
      setPicked(all)
    } catch (err) { setError(err) } finally { setBusy(false) }
  }
  const finishPick = () => { setPicked({}); setPicking(false); changed() }
  const linkPicked = () => api.linkTransfer(pickedSend[0], pickedRecv[0]).then(finishPick, setError)
  const notDustPicked = () => api.setDust(pickedDust, false).then(finishPick, setError)
  const spamPicked = () => api.setSpam(pickedDust, true).then(finishPick, setError)
  const attachPicked = () => Promise.all([...pickedFee, ...pickedSend].map((id) => api.attachExtra(pickedTransfer[0], id)))
    .then(finishPick, setError)

  const placeKey = JSON.stringify(params)
  // read once: the place to go back to, if the filter is the same as then
  const [restore] = useState(() => { const p = embedded ? null : readPlace(); return p && p.key === placeKey ? p : null })
  const restoring = useRef(restore)
  // only the newest request may fill the list: a slower answer to an older filter is dropped
  // (review 2026-10-25)
  const latest = useRef(0)
  const load = useCallback(async (offset = 0) => {
    const ticket = ++latest.current
    try {
      const back = offset === 0 ? restoring.current : null
      const limit = back ? Math.min(500, Math.max(pageSize, back.count)) : pageSize
      const page = await api.merged({ ...params, offset, limit })
      if (ticket !== latest.current) return
      setTotal(page.total); setSummary(page.summary); onSummary?.(page.summary); onTotal?.(page.total)
      setItems((old) => (offset ? [...old, ...page.items] : page.items))
      if (back) {
        restoring.current = null
        setOpened(new Set(Array.isArray(back.open) ? back.open : back.open != null ? [back.open] : []))
        requestAnimationFrame(() => requestAnimationFrame(() => window.scrollTo(0, back.y)))
      }
    } catch (err) { if (ticket === latest.current) setError(err) }
  // params is a new object on every render: compare by content
  // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [placeKey, pageSize])
  // remember the place: loaded lines, scroll position, the open line
  const count = items.length
  useEffect(() => {
    if (embedded || restoring.current) return
    const save = () => {
      try { localStorage.setItem(PLACE, JSON.stringify({ key: placeKey, count, y: window.scrollY, open: [...opened] } satisfies Place)) } catch { /* private mode */ }
    }
    save()
    let timer = 0
    const onScroll = () => { window.clearTimeout(timer); timer = window.setTimeout(save, 200) }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => { window.removeEventListener('scroll', onScroll); window.clearTimeout(timer) }
  }, [placeKey, count, opened, embedded])
  // load() sets state only after awaiting the server.
  // oxlint-disable-next-line react/set-state-in-effect
  useEffect(() => void load(), [load, reloadKey])
  const changed = () => { setOpened(new Set()); setError(null); void load() }

  const lines = compact && !picking
  // unique per line: a futures position has no line id, and shared keys mix up the list
  const itemKey = (i: MergedItem) => (i.type === 'position' ? `p${i.row_ids[0]}` : i.type === 'transfer' ? `t${i.send.id}` : `r${i.row.id}`)
  const card = (i: MergedItem) => i.type === 'transfer' ? (
    <TransferCard key={`t${i.send.id}`} item={i} name={name} lookup={lookup} tz={tz} isOpen={opened.has(lineId(i))} toggle={() => toggleLine(lineId(i))} show={() => showLine(lineId(i))} onChanged={changed} onCopy={onCopy}
      pick={picking ? { checked: !!picked[i.send.id], toggle: () => togglePick(i.send.id, 'transfer') } : undefined} />
  ) : i.type === 'position' ? (
    <PositionCard key={`p${i.row_ids[0]}`} item={i} name={name} lookup={lookup} tz={tz} onChanged={changed}
      control={lines ? { open: true, toggle: () => toggleLine(lineId(i)) } : undefined} />
  ) : (
    <RowCard key={i.row.id} item={i} name={name} lookup={lookup} tz={tz} isOpen={opened.has(lineId(i))} toggle={() => toggleLine(lineId(i))} show={() => showLine(lineId(i))} onChanged={changed} onCopy={onCopy}
      pick={picking && pickKind(i.row) ? { checked: !!picked[i.row.id], toggle: () => togglePick(i.row.id, pickKind(i.row)!, i.dust) } : undefined} />
  )

  async function hideAllDust() {
    // every page, not only the first 500 (review 2026-10-25)
    try {
      const ids: number[] = []
      for (let offset = 0; ; offset += 500) {
        const page = await api.merged({ ...params, show: 'dust', offset, limit: 500 })
        ids.push(...page.items.flatMap((i) => (i.type === 'row' ? [i.row.id] : [])))
        if (offset + 500 >= page.total) break
      }
      await api.setSpam(ids, true)
      changed()
    } catch (err) { setError(err) }
  }

  return (
    <>
      {summary && !embedded && (
        <div className="grid gap-2">
          <p className="m-0 text-xs leading-relaxed text-muted">
            {t(`merged.hints.${show}`, { transfers: summary.transfers, rows: summary.rows })}
          </p>
          {picking && <p className="m-0 text-xs text-accent">{t('merged.pick.hint')}</p>}
          {show === 'dust' && summary.dust > 0 && (
            <Confirm label={t('merged.hideAllDust', { count: summary.dust })} question={t('merged.hideAllDustConfirm', { count: summary.dust })}
              onConfirm={() => void hideAllDust()} />
          )}
        </div>
      )}
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
      {total === null ? (
        <p className="text-sm text-muted">{t('common.loading')}</p>
      ) : items.length === 0 ? (
        <Card><p className="m-0 text-sm text-muted">{t(`merged.empty.${show}`)}</p></Card>
      ) : (
        <ul className={cx('m-0 grid list-none p-0', lines ? 'divide-y divide-line rounded-card border border-line' : 'gap-2')}>
          {items.map((i) => lines && !opened.has(lineId(i)) ? (
            <CompactLine key={`c${itemKey(i)}`} item={i} focus={focus} name={name} lookup={lookup} tz={tz} onOpen={() => showLine(lineId(i))} />
          ) : lines ? (
            // an opened line: the full card with its details, closing it brings the line back
            <li key={`o${itemKey(i)}`} className="p-1.5"><ul className="m-0 grid list-none p-0">{card(i)}</ul></li>
          ) : card(i))}
        </ul>
      )}
      {picking && (
        <div className="sticky bottom-20 z-20 flex flex-wrap items-center justify-between gap-2 rounded-card border border-line bg-surface p-3 shadow-xl md:bottom-4">
          <span className="grid gap-0.5 text-sm">
            {t('merged.pick.status', { sends: pickedSend.length, receives: pickedRecv.length, transfers: pickedTransfer.length, fees: pickedFee.length })}
            {pickedDust.length > 0 && <span className="text-xs text-warn">{t('merged.pick.dust', { count: pickedDust.length })}</span>}
          </span>
          <span className="flex flex-wrap gap-2">
            <Button variant="ghost" disabled={busy} onClick={() => void pickAll()}><CheckSquare size={14} aria-hidden="true" />{t('merged.pick.all')}</Button>
            <Button variant="ghost" disabled={pickedIds.length === 0} onClick={() => setPicked({})}><Square size={14} aria-hidden="true" />{t('merged.pick.none')}</Button>
            {/* leave picking right here, not only up at the filters (Vanixxx, 2026-10-10) */}
            <Button variant="ghost" onClick={() => setPicking(false)}><X size={14} aria-hidden="true" />{t('merged.pick.stop')}</Button>
            {onlyDust ? (
              <>
                <Button onClick={() => void notDustPicked()}>{t('merged.pick.notDust', { count: pickedDust.length })}</Button>
                <Button variant="ghost" onClick={() => void spamPicked()}>{t('merged.pick.spam', { count: pickedDust.length })}</Button>
              </>
            ) : attachable ? (
              <Button onClick={() => void attachPicked()}>{t('merged.attachFee')}</Button>
            ) : (
              <Button disabled={!linkable} onClick={() => void linkPicked()}>
                <Link2 size={14} aria-hidden="true" />{t('merged.link')}
              </Button>
            )}
          </span>
        </div>
      )}
      {items.length < (total ?? 0) && (
        <Button variant="ghost" className="justify-self-center" onClick={() => void load(items.length)}>{t('pages.transactions.loadMore')}</Button>
      )}
    </>
  )
}

type CardProps<T> = { item: T; name: (id: number) => string; lookup: (id: number) => SourceRef; tz: string
  isOpen: boolean; toggle: () => void; show: () => void; onChanged: () => void }

function TransferCard({ item, name, lookup, tz, isOpen, toggle, show, onChanged, pick, onCopy }: CardProps<Extract<MergedItem, { type: 'transfer' }>> & {
  pick?: { checked: boolean; toggle: () => void }; onCopy?: (row: MergedRow, to?: number) => void
}) {
  const { t } = useTranslation()
  const currency = useSettings().settings['general.currency']
  const errorText = useErrorText()
  const [error, setError] = useState<unknown>(null)
  const { send, receive } = item
  const [offer, setOffer] = useState<MergedRow[] | null>(null)
  // tabs like a spreadsheet's sheets, "Details" first (Vanixxx, 2026-10-06)
  const [tab, setTab] = useState<'details' | 'edit' | 'singles' | 'versions' | 'tax' | 'fee'>('details')
  const pickTab = (v: typeof tab) => {
    setTab(v)
    if (v === 'fee') api.attachable(send.id).then(setOffer, setError)
  }
  // the menu opens the line at the right tab, or acts right away (Vanixxx, 2026-10-08)
  const openAt = (v: typeof tab) => { show(); pickTab(v) }
  const singles: Single[] = [{ role: 'send', row: send }, { role: 'receive', row: receive }, ...item.extras.map((row) => ({ role: 'extra' as const, row }))]
  const edited = singles.some((x) => x.row.modified)
  const byHand = [send, receive].some((x) => (x.origin ?? x.channel) === 'manual')
  const detach = (id: number) => void api.detachExtra(id).then(onChanged, setError)
  return (
    <TxShell at={item.at} tz={tz} kind="transfer" title={t('merged.transfer')}
      lead={pick && <input type="checkbox" checked={pick.checked} onChange={pick.toggle} aria-label={t('merged.pick.one')} className="h-6 w-6 shrink-0 accent-[var(--accent)]" />}
      onPick={pick?.toggle} picked={pick?.checked} onToggle={toggle}
      // "edited" up right, where single lines show it too (Vanixxx, 2026-10-06)
      mark={(edited || byHand) && (
        <span className="inline-flex items-center gap-2">
          {/* a transfer entered or copied by hand says so, like a single line (Vanixxx, 2026-10-08) */}
          {byHand && <span className="inline-flex items-center gap-1 text-muted" title={t('pages.sources.channels.manual')}><Hand size={11} aria-label={t('pages.sources.channels.manual')} /><span className="hidden md:inline">{t('pages.sources.channels.manual')}</span></span>}
          {edited && <span className="inline-flex items-center gap-1 text-accent" title={t('manual.edited')}><Pencil size={11} aria-label={t('manual.edited')} /><span className="hidden md:inline">{t('manual.edited')}</span></span>}
        </span>
      )}
      action={<ActionMenu items={[
        { label: t('merged.tabs.details'), icon: <Info size={14} />, onSelect: () => openAt('details') },
        { label: t('merged.editTransfer'), icon: <Pencil size={14} />, onSelect: () => openAt('edit') },
        { label: t('merged.singles'), icon: <Layers size={14} />, onSelect: () => openAt('singles') },
        { label: t('merged.versions'), icon: <History size={14} />, onSelect: () => openAt('versions') },
        { label: t('tax.row.tab'), icon: <Landmark size={14} />, onSelect: () => openAt('tax') },
        { label: t('merged.attachFee'), icon: <Receipt size={14} />, onSelect: () => openAt('fee') },
        onCopy && { label: t('manual.copy'), icon: <Copy size={14} />, onSelect: () => onCopy(send, receive.source_id) },
        // the whole transfer goes: both halves hidden, own entries deleted (Vanixxx, 2026-10-08)
        { label: t('merged.hideTransfer'), icon: <Trash2 size={14} />, danger: true, confirm: t('merged.hideTransferConfirm'),
          onSelect: () => void Promise.all([api.hideRaw(send.id), api.hideRaw(receive.id)]).then(onChanged, (e) => { setError(e); show() }) },
        { label: t('merged.split'), icon: <Unlink size={14} />, danger: true, confirm: t('merged.splitConfirm'),
          onSelect: () => void api.splitTransfer(send.id, receive.id).then(onChanged, (e) => { setError(e); show() }) },
      ]} />}
      side={<>
        {singles.map((x) => x.row.auto_deposit && <AutoDeposit key={x.row.id} d={x.row.auto_deposit} />)}
        {item.short && (
          <span className="justify-self-start rounded-full border border-down/40 px-2 py-0.5 text-down" title={t('merged.badges.shortHint')}>
            {t('merged.badges.short', { assets: [...new Set(singles.flatMap((x) => x.row.short ?? []))].join(', ') })}
          </span>
        )}
        {item.network_fee && <span>{t('merged.networkFee')} <span className="num">{side(item.network_fee, '')}</span></span>}
        {send.fee[0] && <span>{t('pages.transactions.fee')} <span className="num">{side(send.fee, '')}</span>{send.values?.fee && send.fee[0] !== currency && <> ≈ {money(send.values.fee, currency)}</>}</span>}
        {item.extras.map((x) => (
          <span key={x.id}>{t('merged.extraFee')} <span className="num">{side(x.outgoing[0] ? x.outgoing : x.fee, '')}</span>
            {(x.values?.outgoing ?? x.values?.fee) && <> ≈ {money(x.values?.outgoing ?? x.values?.fee ?? null, currency)}</>}</span>
        ))}
      </>}
      below={isOpen && (
        <div className="grid gap-3 border-t border-line pt-2">
          <Tabs value={tab} onChange={pickTab} tabs={[
            { value: 'details', label: t('merged.tabs.details') },
            { value: 'edit', label: <><Pencil size={14} aria-hidden="true" />{t('merged.editTransfer')}</> },
            { value: 'singles', label: <><Layers size={14} aria-hidden="true" />{t('merged.singles')}</> },
            { value: 'versions', label: <><History size={14} aria-hidden="true" />{t('merged.versions')}</> },
            { value: 'tax', label: <><Landmark size={14} aria-hidden="true" />{t('tax.row.tab')}</> },
            { value: 'fee', label: t('merged.attachFee') },
          ]} />
          {tab === 'details' && (
            <>
              <Details singles={singles} lookup={lookup} name={name} reason={item.reason} onChanged={onChanged} />
            </>
          )}
          {tab === 'edit' && <TransferForm send={send} receive={receive} extras={item.extras} lookup={lookup} name={name} tz={tz} onDone={onChanged} onCancel={() => setTab('details')} />}
          {/* the singles are read here; changing them is "edit transfer" (Vanixxx, 2026-10-06) */}
          {tab === 'singles' && <SingleList singles={singles} lookup={lookup} name={name} tz={tz} onDetach={detach} />}
          {tab === 'versions' && <AllVersions singles={singles} tz={tz} reason={item.reason} linkedAt={item.linked_at} onDetach={detach} onChanged={onChanged} />}
          {tab === 'tax' && <TaxTab ids={singles.map((x) => x.row.id)} tz={tz} />}
          {tab === 'fee' && offer && (offer.length === 0 ? <p className="m-0 text-sm text-muted">{t('merged.noAttachable')}</p> : (
            <ul className="m-0 grid list-none gap-1.5 rounded-ctl bg-surface-2 p-2">
              {offer.map((x) => (
                <li key={x.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                  <span>{kindLabel(t, x)} · <span className="num">{side(x.outgoing[0] ? x.outgoing : x.fee, '−')}</span> <span className="text-xs text-muted">{dateTime(x.timestamp, tz)}</span></span>
                  <Button variant="ghost" onClick={() => void api.attachExtra(send.id, x.id).then(onChanged, setError)}>{t('merged.attach')}</Button>
                </li>
              ))}
            </ul>
          ))}
          <ErrorText>{error ? errorText(error) : null}</ErrorText>
        </div>
      )}>
      {/* from → to with logo, name, network, amount and its value (Vanixxx, 2026-10-05/06) */}
      <Flow from={{ who: lookup(send.source_id), fallback: name(send.source_id), side: send.outgoing, worth: send.values?.outgoing, sign: '−', tone: 'down', label: t('merged.from') }}
        to={{ who: lookup(receive.source_id), fallback: name(receive.source_id), side: receive.incoming, worth: receive.values?.incoming, sign: '+', tone: 'up', label: t('merged.to') }} />
    </TxShell>
  )
}

function RowCard({ item, name, lookup, tz, isOpen, toggle, show, onChanged, pick, onCopy }: CardProps<Extract<MergedItem, { type: 'row' }>> & {
  pick?: { checked: boolean; toggle: () => void }; onCopy?: (row: MergedRow, to?: number) => void
}) {
  const { t } = useTranslation()
  const currency = useSettings().settings['general.currency']
  const errorText = useErrorText()
  const [error, setError] = useState<unknown>(null)
  const [cands, setCands] = useState<TransferCandidate[] | null>(null)
  const [transfers, setTransfers] = useState<{ send: MergedRow; receive: MergedRow }[] | null>(null)
  const r = item.row
  const isSend = r.kind === 'send'
  // what this line can be linked to: its partner (send/receive) or its transfer (a fee)
  const linkTo = item.spam ? null : isSend || r.kind === 'receive' ? 'partner' : feeLike(r) ? 'transfer' : null
  const [tab, setTab] = useState<'details' | 'edit' | 'versions' | 'tax' | 'link'>('details')
  const pickTab = (v: typeof tab) => {
    setTab(v)
    if (v === 'link' && linkTo === 'partner') api.transferCandidates(r.id).then(setCands, setError)
    if (v === 'link' && linkTo === 'transfer') api.transfersFor(r.id).then(setTransfers, setError)
  }
  const openAt = (v: typeof tab) => { show(); pickTab(v) }
  // an error opens the line: its message shows there
  const act = (p: Promise<unknown>) => void p.then(onChanged, (e) => { setError(e); show() })
  // back to what the source delivered: the first version counts again
  const reset = () => act(api.rawHistory(r.id).then((v) => api.restoreRaw(v[0].id)))
  const ownEntry = r.channel === 'manual' && r.corrects === null
  const out = r.outgoing[0] ? { side: r.outgoing, worth: r.values?.outgoing, sign: '−', tone: 'down' as const } : undefined
  const inc = r.incoming[0] ? { side: r.incoming, worth: r.values?.incoming, sign: '+', tone: 'up' as const } : undefined
  const feeOnly = !out && !inc && r.fee[0] ? { side: r.fee, worth: r.values?.fee, sign: '−', tone: 'down' as const } : undefined
  return (
    <TxShell at={r.timestamp} tz={tz} kind={iconKind(r)} title={kindLabel(t, r)} dim={!!item.spam} futures={r.market === 'futures'}
      lead={pick && <input type="checkbox" checked={pick.checked} onChange={pick.toggle} aria-label={t('merged.pick.one')} className="h-6 w-6 shrink-0 accent-[var(--accent)]" />}
      onPick={pick?.toggle} picked={pick?.checked} onToggle={toggle}
      action={<ActionMenu items={[
        { label: t('merged.tabs.details'), icon: <Info size={14} />, onSelect: () => openAt('details') },
        r.state === 'current' && { label: t('manual.edit'), icon: <Pencil size={14} />, onSelect: () => openAt('edit') },
        { label: t('merged.versions'), icon: <History size={14} />, onSelect: () => openAt('versions') },
        { label: t('tax.row.tab'), icon: <Landmark size={14} />, onSelect: () => openAt('tax') },
        linkTo && { label: t(linkTo === 'partner' ? 'merged.findPartner' : 'merged.findTransfer'), icon: <Search size={14} />, onSelect: () => openAt('link') },
        onCopy && { label: t('manual.copy'), icon: <Copy size={14} />, onSelect: () => onCopy(r) },
        isSend && item.open && { label: t('merged.marks.external'), icon: <Tag size={14} />, onSelect: () => act(api.markOpenSend(r.id, 'external')) },
        isSend && item.open && { label: t('merged.marks.own_untracked'), icon: <Tag size={14} />, onSelect: () => act(api.markOpenSend(r.id, 'own_untracked')) },
        // gone for good, e.g. Trastra's insolvency (Vanixxx, 2026-10-11)
        isSend && item.open && { label: t('merged.marks.lost'), icon: <Tag size={14} />, onSelect: () => act(api.markOpenSend(r.id, 'lost')) },
        // a receive without counterpart: own wallet, bought outside, or income (Vanixxx, 2026-10-11)
        ...(r.kind === 'receive' && item.open ? (['own_untracked', 'bought', 'income'] as const).map((m) => (
          { label: t(`merged.marksIn.${m}`), icon: <Tag size={14} />, onSelect: () => act(api.markOpenSend(r.id, m)) })) : []),
        item.open_mark && { label: t('merged.unmark'), icon: <Tag size={14} />, onSelect: () => act(api.markOpenSend(r.id, null)) },
        item.dust && { label: t('merged.notDust'), icon: <Sparkles size={14} />, onSelect: () => act(api.setDust([r.id], false)) },
        item.dust && { label: t('merged.hideAsSpam'), icon: <EyeOff size={14} />, onSelect: () => act(api.setSpam([r.id], true)) },
        item.spam === 'tx' && { label: t('merged.notSpam'), icon: <Eye size={14} />, onSelect: () => act(api.setSpam([r.id], false)) },
        r.modified && { label: t('manual.reset'), icon: <Undo2 size={14} />, confirm: t('manual.resetConfirm'), onSelect: reset },
        r.state === 'current' && { label: ownEntry ? t('manual.delete') : t('manual.hide'), icon: <Trash2 size={14} />, danger: true,
          confirm: ownEntry ? t('manual.deleteConfirm') : t('manual.hideConfirm'), onSelect: () => act(api.hideRaw(r.id)) },
      ]} />}
      side={<>
        {(() => {
          const fee = r.fee[0] && !feeOnly
            ? <span>{t('pages.transactions.fee')} <span className="num">{side(r.fee, '')}</span>{r.values?.fee && r.fee[0] !== currency && <> ≈ {money(r.values.fee, currency)}</>}</span>
            : null
          // phone: rate under the given box, fee under the received one — a line saved
          // (Vanixxx, 2026-10-13); wider screens keep one item per line
          return r.kind === 'trade' && fee ? (
            <span className="grid grid-cols-[minmax(0,1fr)_18px_minmax(0,1fr)] gap-x-2 gap-y-1 md:grid-cols-1">
              <RateLine r={r} /><span className="md:hidden" aria-hidden="true" />{fee}
            </span>
          ) : <>{r.kind === 'trade' && <RateLine r={r} />}{fee}</>
        })()}
        <span className="flex min-w-0 items-center gap-1.5"><SourceAvatar {...lookup(r.source_id)} size={16} /><span className="truncate">{name(r.source_id)}</span> · <Origin row={r} /></span>
        {r.raw_symbols.length > 0 && <span>{t('merged.rawSymbol', { symbols: r.raw_symbols.join(', ') })}</span>}
        <span className="flex flex-wrap gap-1">
          {/* the balance ran below zero here: something before is missing (Vanixxx, 2026-10-08) */}
          {r.auto_deposit && <AutoDeposit d={r.auto_deposit} />}
          {r.card && (
            <span className="inline-flex items-center gap-1 justify-self-start rounded-full border border-warn/50 px-2 py-0.5 text-warn" title={t('merged.badges.cardHint')}>
              <CreditCard size={12} aria-hidden="true" />{t('merged.badges.card')}
            </span>
          )}
          {!!r.short?.length && <span className="rounded-full border border-down/40 px-2 py-0.5 text-down" title={t('merged.badges.shortHint')}>{t('merged.badges.short', { assets: r.short.join(', ') })}</span>}
          {item.open && <StatusPill ok={false}>{t(item.ambiguous ? 'merged.badges.ambiguous' : 'merged.badges.open')}</StatusPill>}
          {item.open_mark && <span className="rounded-full border border-line px-2 py-0.5">{t(`merged.${r.kind === 'receive' ? 'marksIn' : 'marks'}.${item.open_mark}`)}</span>}
          {item.dust && <span className="rounded-full border border-line px-2 py-0.5 text-warn">{t('merged.badges.dust')}</span>}
          {item.spam && <span className="rounded-full border border-line px-2 py-0.5">{t(`merged.badges.spam_${item.spam}`)}</span>}
        </span>
      </>}
      below={isOpen && (
        <div className="grid gap-3 border-t border-line pt-2">
          <Tabs value={tab} onChange={pickTab} tabs={[
            { value: 'details', label: t('merged.tabs.details') },
            ...(r.state === 'current' ? [{ value: 'edit' as const, label: <><Pencil size={14} aria-hidden="true" />{t('manual.edit')}</> }] : []),
            { value: 'versions', label: <><History size={14} aria-hidden="true" />{t('merged.versions')}</> },
            { value: 'tax', label: <><Landmark size={14} aria-hidden="true" />{t('tax.row.tab')}</> },
            ...(linkTo ? [{ value: 'link' as const, label: <><Search size={14} aria-hidden="true" />{t(linkTo === 'partner' ? 'merged.findPartner' : 'merged.findTransfer')}</> }] : []),
          ]} />
          {tab === 'details' && (
            <>
              {item.result && <TradeResultBox res={item.result} />}
              <Details singles={[{ role: 'row', row: r }]} lookup={lookup} name={name} onChanged={onChanged} />
              {item.spam === 'asset' && <p className="m-0 text-xs text-muted">{t('merged.spamAssetHint')}</p>}
            </>
          )}
          {tab === 'edit' && <EntryForm entry={entryOf(r, tz)} fromSourceId={r.source_id} tz={tz} onDone={onChanged} onCancel={() => setTab('details')} />}
          {tab === 'versions' && <RowVersions row={r} tz={tz} onChanged={onChanged} />}
          {tab === 'tax' && <TaxTab ids={[r.id]} tz={tz} />}
          {tab === 'link' && cands && <Candidates cands={cands} name={name} tz={tz} onLinked={onChanged} />}
          {tab === 'link' && transfers && (transfers.length === 0 ? <p className="m-0 text-sm text-muted">{t('merged.noTransfers')}</p> : (
            <ul className="m-0 grid list-none gap-1.5 rounded-ctl bg-surface-2 p-2">
              {transfers.map((x) => (
                <li key={x.send.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                  <span className="grid">
                    <span>{name(x.send.source_id)} → {name(x.receive.source_id)} · <span className="num">{side(x.send.outgoing, '−')}</span></span>
                    <span className="text-xs text-muted">{dateTime(x.send.timestamp, tz)}</span>
                  </span>
                  <Button variant="ghost" onClick={() => void api.attachExtra(x.send.id, r.id).then(onChanged, setError)}>{t('merged.attach')}</Button>
                </li>
              ))}
            </ul>
          ))}
          <ErrorText>{error ? errorText(error) : null}</ErrorText>
        </div>
      )}>
      {/* a trade (and any two-sided line) like a transfer: what went out → what came in */}
      <Flow from={out ?? feeOnly} to={inc} />
    </TxShell>
  )
}

function Candidates({ cands, name, tz, onLinked }: {
  cands: TransferCandidate[]; name: (id: number) => string; tz: string; onLinked: () => void
}) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [error, setError] = useState<unknown>(null)
  if (cands.length === 0) return <p className="m-0 text-sm text-muted">{t('merged.noCandidates')}</p>
  return (
    <ul className="m-0 grid list-none gap-1.5 rounded-ctl bg-surface-2 p-2">
      {cands.map((c) => (
        <li key={c.partner.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span className="grid">
            <span>{name(c.partner.source_id)} · <span className="num">{c.partner.kind === 'send' ? side(c.partner.outgoing as MergedRow['outgoing'], '−') : side(c.partner.incoming as MergedRow['incoming'], '+')}</span></span>
            <span className="text-xs text-muted">
              {dateTime(c.partner.timestamp, tz)} · {t('merged.candidateGap', { minutes: c.minutes, pct: Number(c.diff_pct).toLocaleString(locale()) })}
              {c.sharp && !c.split_before && <> · {t('merged.sharp')}</>}
              {c.split_before && <> · <span className="text-warn">{t('merged.splitBefore')}</span></>}
            </span>
          </span>
          <Button variant="ghost" onClick={() => void api.linkTransfer(c.send_id, c.receive_id).then(onLinked, setError)}>
            <Link2 size={14} aria-hidden="true" />{t('merged.link')}
          </Button>
        </li>
      ))}
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
    </ul>
  )
}

/** A closed futures position as one line: its result, funding and fees, the bookings
 * behind it on demand (ADR 0040). */
function PositionCard({ item: p, name, lookup, tz, onChanged, control }: {
  item: Extract<MergedItem, { type: 'position' }>; name: (id: number) => string; lookup: (id: number) => SourceRef; tz: string; onChanged: () => void
  /** the compact list opens and closes the card itself */
  control?: { open: boolean; toggle: () => void }
}) {
  const { t } = useTranslation()
  const [ownOpen, setOwnOpen] = useState(false)
  const open = control ? control.open : ownOpen
  const setOpen = (v: boolean) => (control ? control.toggle() : setOwnOpen(v))
  // the bookings behind a position are raw rows like any other: edit, hide, history
  const [rowOpen, setRowOpen] = useState<number | null>(null)
  const dir = trend(p.result)
  const result = p.result.replace('-', '')
  return (
    <TxShell at={p.closed} tz={tz} kind="futures_position" title={p.instrument} onToggle={() => setOpen(!open)} futures
      badge={p.side && (
        <span className={cx('justify-self-start rounded-full px-2 py-0.5 text-[0.7rem] font-semibold uppercase',
          p.side === 'long' ? 'bg-up/15 text-up' : 'bg-down/15 text-down')}>{t(`holdings.futures.${p.side}`)}</span>
      )}
      action={
        <button type="button" aria-expanded={open} aria-label={t('merged.positionRows', { count: p.rows.length })} onClick={() => setOpen(!open)}
          className="rounded-ctl p-1.5 text-muted hover:bg-surface-2 hover:text-fg">
          <ChevronDown size={18} aria-hidden="true" className={cx('transition-transform', !open && '-rotate-90')} />
        </button>
      }
      side={<>
        {p.short && (
          <span className="justify-self-start rounded-full border border-down/40 px-2 py-0.5 text-down" title={t('merged.badges.shortHint')}>
            {t('merged.badges.short', { assets: [...new Set(p.rows.flatMap((x) => x.short ?? []))].join(', ') })}
          </span>
        )}
        <span className="num">{t('holdings.futures.parts', { pnl: quantity(p.pnl), funding: quantity(p.funding), fees: quantity(p.fees) })}</span>
        <span className="flex min-w-0 items-center gap-1.5"><SourceAvatar {...lookup(p.source_id)} size={16} /><span className="truncate">{name(p.source_id)}</span></span>
        <span>{t('merged.positionSpan', { from: dateTime(p.opened, tz) })} · {t('merged.positionRows', { count: p.rows.length })}</span>
      </>}
      below={open && (
        <div className="grid gap-3 border-t border-line pt-2">
        <ul className="m-0 grid list-none gap-1 p-0">
          {p.rows.map((r) => (
            <li key={r.id} className="grid gap-1">
              <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-0.5 text-xs md:grid-cols-[11rem_9rem_minmax(0,1fr)_auto]">
                <span className="num text-muted">{dateTime(r.timestamp, tz)}</span>
                <span className="text-muted">{t(`kinds.${r.kind}`)}{r.edited && <> · {t('manual.edited')}</>}</span>
                <span className="col-span-2 row-start-2 md:col-span-1 md:row-start-auto"><Sides r={r} /></span>
                <span className="col-start-3 row-start-1 md:col-start-auto"><ActionsButton id={r.id} open={rowOpen} setOpen={setRowOpen} /></span>
              </div>
              {rowOpen === r.id && <RowActions row={r} tz={tz} onChanged={onChanged} />}
            </li>
          ))}
        </ul>
        <TaxTab ids={p.rows.map((r) => r.id)} tz={tz} />
        </div>
      )}>
      <Flow from={{ side: [p.coin, result], worth: p.result_value?.replace('-', '') ?? null, sign: dir === 'down' ? '−' : '+', tone: dir === 'up' ? 'up' : dir === 'down' ? 'down' : 'flat' }} />
    </TxShell>
  )
}

/** What this one trade came to (Vanixxx, 2026-10-05): a buy against what the coins are worth
 * today, a sale against what the sold coins would be worth today. Apart from average cost
 * and tax. */
/** The rate of a trade the way exchanges write it: "Kurs 117.553 BTC/USDT" (Vanixxx,
 * 2026-10-13). */
function RateLine({ r }: { r: MergedRow }) {
  const { t } = useTranslation()
  const rate = tradeRate(r.incoming, r.outgoing)
  if (!rate) return null
  return <span className="num">{t('merged.rate', { base: rate.base, price: rateText(rate.price), quote: rate.quote })}</span>
}

function TradeResultBox({ res }: { res: TradeResult }) {
  const { t } = useTranslation()
  const dir = trend(res.result)
  const c = res.currency
  return (
    <div className="grid gap-1.5 rounded-ctl bg-surface-2 p-3 text-sm">
      <span className="label">{t(`merged.result.${res.side}`)}</span>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-4">
        <span className="grid"><span className="text-xs text-muted">{t(`merged.result.then_${res.side}`)}</span><span className="num">{money(res.then, c)}</span></span>
        <span className="grid"><span className="text-xs text-muted">{t(`merged.result.now_${res.side}`, { qty: quantity(res.qty), asset: res.asset })}</span><span className="num">{money(res.now, c)}</span></span>
        <span className="grid"><span className="text-xs text-muted">{t('merged.result.price')}</span>
          <span className="num">{res.price_then ? priceText(Number(res.price_then), c) : '—'} → {res.price_now ? priceText(Number(res.price_now), c) : '—'}</span></span>
        <span className="grid"><span className="text-xs text-muted">{t(`merged.result.pl_${res.side}`)}</span>
          <span className={cx('num font-semibold', dir === 'up' && 'text-up', dir === 'down' && 'text-down')}>{money(res.result, c, true)} {percent(res.pct)}</span></span>
      </div>
    </div>
  )
}

/** Money the app assumed paid in by card at this line: more was spent here than was there
 * (a card buy, Vanixxx 2026-10-09). Marked, so a missing deposit is not mistaken for it. */
function AutoDeposit({ d: [asset, amount] }: { d: [string, string] }) {
  const { t } = useTranslation()
  return (
    <span className="inline-flex items-center gap-1 justify-self-start rounded-full border border-accent/40 px-2 py-0.5 text-accent" title={t('merged.badges.autoHint')}>
      <CreditCard size={12} aria-hidden="true" />{t('merged.badges.auto', { amount: money(amount, asset) })}
    </span>
  )
}
