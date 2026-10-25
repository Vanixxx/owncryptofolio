import { FileSpreadsheet } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useSettings } from '../../app/settings'
import { AssetField } from '../../components/AssetField'
import { SourceAvatar } from '../../components/SourceLogo'
import { Button, ErrorText, Field, Segmented } from '../../components/ui'
import { Combobox, type ComboOption } from '../../components/ui/Combobox'
import { api, type ManualEntry, type ManualInput, type Source, type Wallet } from '../../lib/api'
import { locale } from '../../i18n'
import { KindIcon } from '../transactions/KindIcon'
import { typedTime } from '../../lib/time'
import { useErrorText } from '../../lib/useErrorText'
import { date, money, priceText } from '../../lib/format'
import { rateText, tradeRate } from '../../lib/rate'

type Market = 'spot' | 'futures'
type Side = 'incoming' | 'outgoing' | 'fee'
// Kinds and their sides per market — the same rules the server checks (ADR 0036/0037).
// `need`: sides that must be filled; futures results and transfers take ONE of in/out.
const RULES: Record<Market, Record<string, { sides: Side[]; need: Side[] }>> = {
  spot: {
    trade: { sides: ['incoming', 'outgoing', 'fee'], need: ['incoming', 'outgoing'] },
    receive: { sides: ['incoming', 'fee'], need: ['incoming'] },
    send: { sides: ['outgoing', 'fee'], need: ['outgoing'] },
    fiat_deposit: { sides: ['incoming', 'fee'], need: ['incoming'] },
    fiat_withdrawal: { sides: ['outgoing', 'fee'], need: ['outgoing'] },
    income: { sides: ['incoming'], need: ['incoming'] },
    fee: { sides: ['fee'], need: ['fee'] },
    internal_transfer: { sides: ['incoming', 'outgoing', 'fee'], need: [] },
    migration: { sides: ['incoming', 'outgoing'], need: ['incoming', 'outgoing'] },
    // a send to an own wallet or exchange: saved as a send, then linked to the receive
    // there (found, or entered) — e.g. an "Umbuchung" that really left (Vanixxx, 2026-10-06)
    transfer: { sides: ['outgoing', 'fee'], need: ['outgoing'] },
  },
  futures: {
    realized_pnl: { sides: ['incoming', 'outgoing', 'fee'], need: [] },
    funding: { sides: ['incoming', 'outgoing'], need: [] },
    fee: { sides: ['fee'], need: ['fee'] },
    internal_transfer: { sides: ['incoming', 'outgoing', 'fee'], need: [] },
    income: { sides: ['incoming'], need: ['incoming'] },
  },
}
const INCOME = ['staking', 'reward', 'interest', 'airdrop']
const FIAT_KINDS: Record<string, Side> = { fiat_deposit: 'incoming', fiat_withdrawal: 'outgoing' }


export type SourceChoice = { group: string; options: { id: number; label: string }[] }

/** The one entry form (ADR 0036/0037). With `choices` it asks for the source first; with
 * `entry` it edits (a manual row) or corrects (any other row) — the original stays stored. */
export function EntryForm({ sourceId, choices, entry, copy, fromSourceId, tz, onDone, onCancel, onTemplate }: {
  sourceId?: number; choices?: SourceChoice[]; entry?: ManualEntry; fromSourceId?: number; tz: string; onDone: () => void; onCancel: () => void
  onTemplate?: () => void
  /** a transaction to start from (copy): its values, saved as a new entry (Vanixxx, 2026-10-08) */
  copy?: { entry: ManualEntry; sourceId: number; to?: number }
}) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const currency = useSettings().settings['general.currency']
  const start = entry ?? copy?.entry
  const [target, setTarget] = useState(sourceId ? String(sourceId) : copy ? String(copy.sourceId) : '')
  const [market, setMarket] = useState<Market>(start?.market ?? 'spot')
  const known = (m: Market, k?: string) => (k && k in RULES[m] ? k : m === 'spot' ? 'trade' : 'realized_pnl')
  const [kind, setKind] = useState(known(start?.market ?? 'spot', start?.kind))
  const [income, setIncome] = useState(start?.income_kind ?? 'staking')
  const [instrument, setInstrument] = useState(start?.instrument ?? '')
  const [day, setDay] = useState(start?.time.slice(0, 10) ?? '')
  const [clock, setClock] = useState(start?.time.slice(11, 19) ?? '')
  const [values, setValues] = useState<Record<string, string>>(() => {
    const v: Record<string, string> = { comment: start?.comment ?? '' }
    for (const s of ['incoming', 'outgoing', 'fee'] as Side[]) {
      v[`${s}_asset`] = start?.[`${s}_asset`] ?? ''
      v[`${s}_amount`] = start?.[`${s}_amount`] ?? ''
    }
    return v
  })
  const [byCard, setByCard] = useState(!!start?.paid_by_card)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  // a transfer starts from either side (Vanixxx, 2026-10-11): from a receive, "to" is its own
  // source and only "from" is asked; from a send (or a new entry) "from" is the source
  const anchorSource = entry ? fromSourceId : copy?.sourceId
  const fromReceive = start?.kind === 'receive' && anchorSource !== undefined
  const [to, setTo] = useState(copy?.to ? String(copy.to) : fromReceive ? String(anchorSource) : '')
  const [from, setFrom] = useState('')
  // sources with their logos: for choosing the source and a transfer's target
  const [srcs, setSrcs] = useState<{ sources: Source[]; wallets: Wallet[] } | null>(null)
  const own = sourceId ?? fromSourceId ?? (target ? Number(target) : undefined)
  useEffect(() => {
    Promise.all([api.sources(), api.wallets()]).then(([sources, wallets]) => setSrcs({ sources, wallets }), setError)
  }, [])
  const sourceOption = (id: number, label: string, group: string): ComboOption => {
    const src = srcs?.sources.find((x) => x.id === id)
    const w = srcs?.wallets.find((x) => x.id === src?.wallet_id)
    // a network says whose it is: "Tangem – Ethereum"
    const shown = w && !label.startsWith(w.name) ? `${w.name} – ${label}` : label
    return { value: String(id), label: shown, group, icon: <SourceAvatar source={src} wallet={w} size={18} /> }
  }
  const sourceOptions = (choices ?? []).flatMap((c) => c.options.map((o) => sourceOption(o.id, o.label, c.group)))
  const targetOptions: ComboOption[] = srcs ? [
    ...srcs.sources.filter((x) => x.kind === 'exchange').map((x) => sourceOption(x.id, x.label, t('pages.sources.exchanges'))),
    ...srcs.wallets.flatMap((w) => srcs.sources.filter((x) => x.wallet_id === w.id).map((x) => sourceOption(x.id, `${w.name} – ${x.label}`, w.name))),
  ].filter((o) => Number(o.value) !== (fromReceive ? anchorSource : own)) : []
  const sourceName = (sid?: number) => (sid === undefined ? '' : targetLabel(sid))
  function targetLabel(sid: number) {
    const src = srcs?.sources.find((x) => x.id === sid)
    const w = srcs?.wallets.find((x) => x.id === src?.wallet_id)
    return src ? (w ? `${w.name} – ${src.label}` : src.label) : ''
  }
  const kindOptions: ComboOption[] = Object.keys(RULES[market]).map((k) => ({
    value: k, label: t(`manual.kinds.${k}`), icon: <KindIcon kind={k === 'transfer' ? 'transfer' : k} small />,
  }))
  // fiat in or out starts in the display currency (Vanixxx, 2026-10-08)
  const pickKind = (k: string) => {
    setKind(k)
    // from a receive: what arrived is what was sent, unless typed otherwise
    if (k === 'transfer' && fromReceive && !values.outgoing_amount) {
      set('outgoing_asset', values.incoming_asset); set('outgoing_amount', values.incoming_amount)
    }
    const side = FIAT_KINDS[k]
    if (side && !values[`${side}_asset`]) set(`${side}_asset`, currency)
  }
  const id = `manual-${sourceId ?? 'any'}-${entry?.id ?? 'new'}`
  const set = (k: string, v: string) => setValues((old) => ({ ...old, [k]: v }))
  const rule = RULES[market][kind]
  // a buy paid with euro or dollars may have been paid by card (Vanixxx, 2026-10-10)
  const cardable = kind === 'trade' && ['EUR', 'USD'].includes((values.outgoing_asset ?? '').trim().toUpperCase())
  // as the server reads it: with both marks the last one is the decimal mark (1.234,56 and
  // 1,234.56), else a comma is one (review 2026-10-25: 1,234.56 lost the preview)
  const num = (v: string) => {
    const s = v.replace(/\s/g, '')
    if (s.includes(',') && s.includes('.')) return Number(s.lastIndexOf(',') > s.lastIndexOf('.') ? s.replace(/\./g, '').replace(',', '.') : s.replace(/,/g, ''))
    return Number(s.replace(',', '.'))
  }
  const feeInBought = rule.sides.includes('incoming') && rule.sides.includes('fee') && !!values.fee_asset && values.fee_asset.toUpperCase() === values.incoming_asset.toUpperCase()
    && Number.isFinite(num(values.incoming_amount)) && Number.isFinite(num(values.fee_amount)) && !!values.incoming_amount && !!values.fee_amount
  const arrived = feeInBought ? (num(values.incoming_amount) - num(values.fee_amount)).toLocaleString(locale(), { maximumFractionDigits: 10 }) : ''
  const oneSide = rule.need.length === 0
  // the rate of a buy or sale as soon as both sides are there (Vanixxx, 2026-10-13)
  const rate = kind === 'trade' && values.incoming_amount && values.outgoing_amount
    ? tradeRate([(values.incoming_asset ?? '').trim().toUpperCase(), String(num(values.incoming_amount))],
      [(values.outgoing_asset ?? '').trim().toUpperCase(), String(num(values.outgoing_amount))])
    : null
  // what lay there at that moment, shown in the amount given away (Vanixxx, 2026-10-11)
  const payer = kind === 'transfer' && fromReceive ? (from ? Number(from) : undefined) : own
  const outAsset = (values.outgoing_asset ?? '').trim().toUpperCase()
  const tidy = clock.replace(/:$/, '').padStart(5, '0')  // the time field adds the next colon itself
  const moment = day && /^\d{2}:\d{2}(:\d{2})?$/.test(tidy) ? `${day}T${tidy.length === 5 ? `${tidy}:00` : tidy}` : ''
  const skip = entry && !(kind === 'transfer' && fromReceive) ? entry.id : undefined
  const heldKey = payer && outAsset && moment && rule.sides.includes('outgoing') ? `${payer}|${outAsset}|${moment}|${market}|${skip ?? ''}` : ''
  const [fetched, setFetched] = useState<{ key: string; amount: string | null } | null>(null)
  const held = fetched && fetched.key === heldKey ? fetched.amount : null
  useEffect(() => {
    if (!heldKey || !payer) return
    let live = true
    const id = window.setTimeout(() => {
      api.balanceAt(payer, outAsset, moment, market, skip)
        .then((b) => { if (live) setFetched({ key: heldKey, amount: b.amount }) }, () => {})
    }, 300)
    return () => { live = false; window.clearTimeout(id) }
  }, [heldKey, payer, outAsset, moment, market, skip])

  function switchMarket(m: Market) {
    setMarket(m)
    setKind((k) => known(m, k))
  }

  async function submit(ev: FormEvent) {
    ev.preventDefault()
    const body: ManualInput = {
      kind: (kind === 'transfer' ? 'send' : kind) as ManualInput['kind'], market, time: `${day}T${clock.length === 5 ? `${clock}:00` : clock}`, comment: values.comment,
    }
    if (kind === 'income') body.income_kind = income
    if (cardable && byCard) body.paid_by_card = true
    if (market === 'futures') body.instrument = instrument.trim().toUpperCase()
    for (const s of rule.sides) {
      body[`${s}_asset`] = values[`${s}_asset`].trim().toUpperCase()
      body[`${s}_amount`] = values[`${s}_amount`].trim()
    }
    setBusy(true)
    try {
      if (kind === 'transfer' && fromReceive) {
        // the receive stays as it is: the send is entered where it came from and linked
        const sent = await api.addManual(Number(from), body)
        if (entry) await api.linkTransfer(sent.id, entry.id)
        else await api.makeTransfer(sent.id, Number(to))
        onDone()
        return
      }
      const saved = await (entry ? api.editRaw(entry.id, body) : api.addManual(Number(target || copy?.sourceId), body))
      if (kind === 'transfer') await api.makeTransfer(saved.id, Number(to))
      onDone()
    } catch (err) { setError(err) } finally { setBusy(false) }
  }

  const sideLabel = (s: Side) => t(oneSide && s !== 'fee' ? `manual.sidesOneOf.${market}.${kind}.${s}` : `manual.sides.${s}`,
    { defaultValue: t(`manual.sides.${s}`) })

  return (
    <form onSubmit={submit} className="grid gap-4 rounded-ctl bg-surface-2 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <b className="text-sm">{entry ? t(isManual(entry) ? 'manual.editTitle' : 'manual.correctTitle') : copy ? t('manual.copyTitle') : t('manual.add')}</b>
        {/* many at once from the template: part of "add", not a second button up top */}
        {!entry && !copy && onTemplate && (
          <Button type="button" variant="ghost" onClick={onTemplate}><FileSpreadsheet size={15} aria-hidden="true" />{t('manual.fromTemplate')}</Button>
        )}
      </div>
      {choices && !(kind === 'transfer' && fromReceive) && (
        <div className="grid gap-1.5">
          <span className="label">{kind === 'transfer' ? t('manual.transferFrom') : t('manual.source')}</span>
          <Combobox noAll label={t('manual.source')} allLabel={t('manual.chooseSource')} value={target} onChange={setTarget} options={sourceOptions} />
        </div>
      )}
      <Segmented label={t('manual.market')} value={market} onChange={switchMarket}
        options={[{ value: 'spot', label: 'Spot' }, { value: 'futures', label: 'Futures' }]} />
      <div className="grid gap-1.5">
        <span className="label">{t('manual.kind')}</span>
        <Combobox noAll label={t('manual.kind')} allLabel={t('manual.kind')} value={kind} onChange={pickKind} options={kindOptions} />
      </div>
      {kind === 'transfer' && (
        <div className="grid gap-3">
          {fromReceive ? (
            <div className="grid gap-1.5">
              <span className="label">{t('manual.transferFrom')}</span>
              <Combobox noAll label={t('manual.transferFrom')} allLabel={t('manual.transferToPick')} value={from} onChange={setFrom} options={targetOptions} />
            </div>
          ) : !choices && (
            <p className="m-0 text-sm"><span className="label">{t('manual.transferFrom')}</span> {sourceName(own)}</p>
          )}
          {fromReceive ? (
            <p className="m-0 text-sm"><span className="label">{t('manual.transferTo')}</span> {sourceName(anchorSource)}</p>
          ) : (
            <div className="grid gap-1.5">
              <span className="label">{t('manual.transferTo')}</span>
              <Combobox noAll label={t('manual.transferTo')} allLabel={t('manual.transferToPick')} value={to} onChange={setTo} options={targetOptions} />
            </div>
          )}
          <span className="text-xs leading-relaxed text-muted">
            {fromReceive ? t('manual.transferFromReceiveHint', { amount: values.incoming_amount, asset: values.incoming_asset }) : t('manual.transferHint')}
          </span>
        </div>
      )}
      {kind === 'income' && (
        <div className="grid gap-1.5">
          <span className="label">{t('manual.incomeKind')}</span>
          <Combobox noAll label={t('manual.incomeKind')} allLabel={t('manual.incomeKind')} value={income} onChange={setIncome}
            options={INCOME.map((k) => ({ value: k, label: t(`manual.income.${k}`), icon: <KindIcon kind={`income:${k}`} small /> }))} />
        </div>
      )}
      {market === 'futures' && (
        <Field id={`${id}-instrument`} label={`${t('manual.instrument')} (${t('manual.optional')})`} placeholder="BTCUSDT"
          autoCapitalize="characters" value={instrument} onChange={(e) => setInstrument(e.target.value)} />
      )}
      <div className="grid grid-cols-2 gap-3">
        <Field id={`${id}-day`} label={t('manual.date')} type="date" value={day} onChange={(e) => setDay(e.target.value)} required />
        {/* Text instead of <input type=time>: browsers show AM/PM by OS locale. */}
        <Field id={`${id}-time`} label={t('manual.time')} inputMode="numeric" placeholder="14:05:30" pattern="[0-2]?[0-9]:[0-5][0-9](:[0-5][0-9])?"
          value={clock} onChange={(e) => setClock(typedTime(clock, e.target.value))} required />
      </div>
      <span className="-mt-2 text-xs text-muted">{t('manual.timeHint', { tz })}</span>
      {oneSide && <p className="m-0 text-xs text-muted">{t(`manual.oneSideHint.${market === 'spot' ? 'transfer' : kind}`)}</p>}
      {rule.sides.map((s) => (
        <fieldset key={s} className="m-0 grid grid-cols-[minmax(0,3fr)_minmax(0,2fr)] items-start gap-3 border-0 p-0">
          <legend className="label mb-1.5">{sideLabel(s)}{s === 'fee' || oneSide ? ` (${t('manual.optional')})` : ''}</legend>
          <div className="grid min-w-0 gap-1">
            <Field id={`${id}-${s}-amount`} label={t('manual.amount')} inputMode="decimal"
              placeholder={s === 'outgoing' && held !== null ? t('manual.maxHeld', { amount: Number(held).toLocaleString(locale(), { maximumFractionDigits: 10 }) }) : '0,5'}
              value={values[`${s}_amount`]} onChange={(e) => set(`${s}_amount`, e.target.value)} required={rule.need.includes(s)} />
            {s === 'outgoing' && !payer && !!outAsset && !!moment && (
              <span className="text-xs text-muted">{t(kind === 'transfer' ? 'manual.heldPickFrom' : 'manual.heldPickSource')}</span>
            )}
            {s === 'outgoing' && held !== null && (
              <button type="button" onClick={() => set('outgoing_amount', String(held))}
                className={`justify-self-start border-0 bg-transparent p-0 text-left text-xs ${Number(held) <= 0 ? 'text-warn' : 'text-muted hover:text-accent'}`}>
                {t('manual.heldThen', { amount: Number(held).toLocaleString(locale(), { maximumFractionDigits: 10 }), asset: outAsset })}
              </button>
            )}
          </div>
          <div className="grid min-w-0 gap-1">
            <AssetField id={`${id}-${s}-asset`} label={t('manual.asset')} placeholder={s === 'outgoing' ? 'EUR' : 'BTC'}
              value={values[`${s}_asset`]} onChange={(v) => set(`${s}_asset`, v)} required={rule.need.includes(s)}
              extra={FIAT_KINDS[kind] === s || (kind === 'trade' && s === 'outgoing') ? [currency, currency === 'EUR' ? 'USD' : 'EUR'] : []} />
            <MarketPrice asset={(values[`${s}_asset`] ?? '').trim().toUpperCase()} day={day} amount={num(values[`${s}_amount`] ?? '')} />
          </div>
        </fieldset>
      ))}
      {rate && (
        <p className="m-0 text-xs text-muted">
          <span className="num">{t('merged.rate', { base: rate.base, price: rateText(rate.price), quote: rate.quote })}</span>
          {' '}{t('manual.rateHint')}
        </p>
      )}
      {/* fee in the coin bought: "received" is before the fee — SafeTrade QUBIC was entered
          after it, and the fee came off twice (Vanixxx, 2026-10-09) */}
      {feeInBought && (
        <p className="m-0 rounded-ctl bg-surface px-3 py-2 text-xs leading-relaxed text-muted">
          {t('manual.feeInBought', { arrived: arrived, asset: values.incoming_asset.toUpperCase() })}
        </p>
      )}
      {cardable && (
        <label className="flex items-start gap-2.5 text-sm">
          <input type="checkbox" checked={byCard} onChange={(e) => setByCard(e.target.checked)} className="mt-0.5 h-5 w-5 shrink-0 accent-[var(--accent)]" />
          <span className="grid gap-0.5">{t('manual.paidByCard')}<span className="text-xs text-muted">{t('manual.paidByCardHint')}</span></span>
        </label>
      )}
      <Field id={`${id}-comment`} label={t('manual.comment')} value={values.comment} onChange={(e) => set('comment', e.target.value)} />
      {entry && !isManual(entry) && <p className="m-0 text-xs text-muted">{t('manual.correctHint')}</p>}
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={busy || (kind === 'transfer' && !(fromReceive ? from : to))}>{t('common.save')}</Button>
        <Button type="button" variant="ghost" onClick={onCancel}>{t('common.cancel')}</Button>
      </div>
    </form>
  )
}

/** The coin's market price on the entered day, or now without one (Vanixxx, 2026-10-13):
 * "1 BTC ≈ 60.000 € (Tageskurs 12.03.2024) · 30.000 €". The app keeps one price per coin and
 * day, so only the day is asked: changing the time loads nothing. */
function MarketPrice({ asset, day, amount }: { asset: string; day: string; amount: number }) {
  const { t } = useTranslation()
  const key = asset && asset.length >= 2 ? `${asset}|${day}` : ''
  const [got, setGot] = useState<{ key: string; price: string | null; currency: string; latest: boolean; day: string } | null>(null)
  useEffect(() => {
    if (!key) return
    let live = true
    const id = window.setTimeout(() => {
      api.priceAt(asset, day ? `${day}T12:00` : undefined).then((p) => { if (live) setGot({ key, ...p }) }, () => {})
    }, 400)
    return () => { live = false; window.clearTimeout(id) }
  }, [key, asset, day])
  // the line keeps its place while a new price loads: the last one stays, dimmed, so the
  // fields below do not jump with every change of date or time (Vanixxx, 2026-10-13)
  if (!key) return null
  const loading = !got || got.key !== key
  const show = got && got.price !== null && asset !== got.currency
  return (
    <span className={`min-h-[3lh] md:min-h-[2lh] text-xs text-muted transition-opacity ${loading ? 'opacity-50' : ''}`} aria-busy={loading}>
      {show ? (
        <>
          <span className="num">1 {asset} ≈ {priceText(Number(got.price), got.currency)}</span>
          {' '}{got.latest ? t('manual.priceNow') : t('manual.priceOn', { date: date(got.day) })}
          {Number.isFinite(amount) && amount > 0 && <> · <span className="num">{money(String(Number(got.price) * amount), got.currency)}</span></>}
        </>
      ) : loading ? t('manual.priceLoading') : asset === got?.currency ? null : t('manual.priceNone')}
    </span>
  )
}

// entryOf() keeps the row's channel; entries of the manual list carry none.
function isManual(e: ManualEntry) {
  return !e.channel || e.channel === 'manual'
}
