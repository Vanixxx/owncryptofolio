import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { locale } from '../../i18n'
import { AssetField } from '../../components/AssetField'
import { SourceAvatar } from '../../components/SourceLogo'
import { Button, ErrorText, Field } from '../../components/ui'
import { Combobox, type ComboOption } from '../../components/ui/Combobox'
import { api, type ManualInput, type MergedRow, type Source, type Wallet } from '../../lib/api'
import { entryOf } from '../../lib/entry'
import type { SourceRef } from '../../lib/txFilter'
import { useErrorText } from '../../lib/useErrorText'

type Pair = [string, string] // amount, asset
const pair = (side: [string | null, string | null]): Pair => [side[1] ?? '', side[0] ?? '']

/** Local "YYYY-MM-DDTHH:MM:SS" moved by some milliseconds (read as UTC: only the
 * difference matters, so the gap between send and receive is kept). */
function shift(local: string, ms: number): string {
  return new Date(new Date(`${local}Z`).getTime() + ms).toISOString().slice(0, 19)
}

/** One form for a whole transfer (Vanixxx, 2026-10-06): date and time once, then what went
 * out, what arrived and every fee — the send's own and each booking attached to it —
 * each in its frame with its wallet. Every changed row is saved as a correction; the link
 * and the attachments follow the new versions. */
export function TransferForm({ send, receive, extras, lookup, name, tz, onDone, onCancel }: {
  send: MergedRow; receive: MergedRow; extras: MergedRow[]; lookup: (id: number) => SourceRef; name: (id: number) => string
  tz: string; onDone: () => void; onCancel: () => void
}) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const local = (r: MergedRow) => entryOf(r, tz).time
  const [day, setDay] = useState(local(send).slice(0, 10))
  const [clock, setClock] = useState(local(send).slice(11, 19))
  const [out, setOut] = useState(pair(send.outgoing))
  const [inc, setInc] = useState(pair(receive.incoming))
  // one fee of the transfer itself, on the side it was paid (Vanixxx, 2026-10-06: pick the
  // wallet); only when both rows carry one, both are shown
  const both = !!(send.fee[0] && receive.fee[0])
  const [feeOn, setFeeOn] = useState<'send' | 'receive'>(!send.fee[0] && receive.fee[0] ? 'receive' : 'send')
  const [sendFee, setSendFee] = useState(pair(send.fee))
  const [recvFee, setRecvFee] = useState(pair(receive.fee))
  const ownFee = feeOn === 'send' ? sendFee : recvFee
  const setOwnFee = (p: Pair) => (feeOn === 'send' ? setSendFee(p) : setRecvFee(p))
  const moveFee = (to: 'send' | 'receive') => {
    if (to === feeOn) return
    const p = ownFee
    if (to === 'send') { setSendFee(p); setRecvFee(['', '']) } else { setRecvFee(p); setSendFee(['', '']) }
    setFeeOn(to)
  }
  const [extraFrom, setExtraFrom] = useState<Record<number, string>>(() => Object.fromEntries(extras.map((x) => [x.id, String(x.source_id)])))
  const [extraFees, setExtraFees] = useState<Record<number, Pair>>(() =>
    Object.fromEntries(extras.map((x) => [x.id, pair(x.fee[0] ? x.fee : x.outgoing)])))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  // the wallet or exchange of each side can change too (Vanixxx, 2026-10-08)
  const [fromId, setFromId] = useState(String(send.source_id))
  const [toId, setToId] = useState(String(receive.source_id))
  const [srcs, setSrcs] = useState<{ sources: Source[]; wallets: Wallet[] } | null>(null)
  useEffect(() => {
    Promise.all([api.sources(), api.wallets()]).then(([sources, wallets]) => setSrcs({ sources, wallets }), setError)
  }, [])
  const sourceOptions: ComboOption[] = srcs ? [
    ...srcs.sources.filter((x) => x.kind === 'exchange').map((x) => ({ value: String(x.id), label: x.label, group: t('pages.sources.exchanges'), icon: <SourceAvatar source={x} size={18} /> })),
    ...srcs.wallets.flatMap((w) => srcs.sources.filter((x) => x.wallet_id === w.id).map((x) => ({
      value: String(x.id), label: `${w.name} – ${x.label}`, group: w.name, icon: <SourceAvatar source={x} wallet={w} size={18} />,
    }))),
  ] : []

  // what lay at "from" at that moment, before this send (Vanixxx, 2026-10-11)
  const tidy = clock.replace(/:$/, '').padStart(5, '0')
  const moment = day && /^\d{2}:\d{2}(:\d{2})?$/.test(tidy) ? `${day}T${tidy.length === 5 ? `${tidy}:00` : tidy}` : ''
  const outAsset = out[1].trim().toUpperCase()
  const heldKey = moment && outAsset && fromId ? `${fromId}|${outAsset}|${moment}` : ''
  const [fetched, setFetched] = useState<{ key: string; amount: string | null } | null>(null)
  const held = fetched && fetched.key === heldKey ? fetched.amount : null
  useEffect(() => {
    if (!heldKey) return
    let live = true
    const id = window.setTimeout(() => {
      api.balanceAt(Number(fromId), outAsset, moment, send.market, send.id)
        .then((b) => { if (live) setFetched({ key: heldKey, amount: b.amount }) }, () => {})
    }, 300)
    return () => { live = false; window.clearTimeout(id) }
  }, [heldKey, fromId, outAsset, moment, send.market, send.id])
  const shown = (v: string) => Number(v).toLocaleString(locale(), { maximumFractionDigits: 10 })

  const same = (a: Pair, b: Pair) => a[0].trim() === b[0].trim() && a[1].trim().toUpperCase() === b[1].trim().toUpperCase()
  const put = (b: ManualInput, side: 'incoming' | 'outgoing' | 'fee', p: Pair) => {
    if (p[0].trim() || p[1].trim()) { b[`${side}_amount`] = p[0].trim(); b[`${side}_asset`] = p[1].trim().toUpperCase() }
  }

  async function submit(ev: FormEvent) {
    ev.preventDefault()
    const time = `${day}T${clock.length === 5 ? `${clock}:00` : clock}`
    const moved = new Date(`${time}Z`).getTime() - new Date(`${local(send)}Z`).getTime()
    setBusy(true)
    try {
      // only what changed becomes a new version
      const fromMoved = Number(fromId) !== send.source_id, toMoved = Number(toId) !== receive.source_id
      if (moved || fromMoved || !same(out, pair(send.outgoing)) || !same(sendFee, pair(send.fee))) {
        const b: ManualInput = { kind: 'send', market: 'spot', time, comment: send.comment ?? '', source_id: Number(fromId) }
        put(b, 'outgoing', out); put(b, 'fee', sendFee)
        await api.editRaw(send.id, b)
      }
      if (moved || toMoved || !same(inc, pair(receive.incoming)) || !same(recvFee, pair(receive.fee))) {
        const b: ManualInput = { kind: 'receive', market: 'spot', time: shift(local(receive), moved), comment: receive.comment ?? '', source_id: Number(toId) }
        put(b, 'incoming', inc); put(b, 'fee', recvFee)
        await api.editRaw(receive.id, b)
      }
      for (const x of extras) {
        const p = extraFees[x.id]
        const from = Number(extraFrom[x.id])
        if (from === x.source_id && same(p, pair(x.fee[0] ? x.fee : x.outgoing))) continue
        // an attached booking counts as the transfer's fee: corrected, it is one
        const b: ManualInput = { kind: 'fee', market: 'spot', time: local(x), comment: x.comment ?? '', source_id: from }
        put(b, 'fee', p)
        await api.editRaw(x.id, b)
      }
      onDone()
    } catch (err) { setError(err) } finally { setBusy(false) }
  }

  const frame = 'm-0 grid content-start gap-3 rounded-ctl border border-line bg-surface p-3'
  const box = (key: string, title: string, row: MergedRow, p: Pair, set: (p: Pair) => void, required: boolean, pick?: ReactNode): ReactNode => (
    <fieldset key={key} className={frame}>
      <legend className="px-1 text-sm font-semibold">{title}</legend>
      {/* whose it is: the wallet or exchange of that row — or a choice between the two */}
      {pick ?? (
        <span className="flex min-w-0 items-center gap-2 text-xs text-muted">
          <SourceAvatar {...lookup(row.source_id)} size={20} /><span className="truncate">{name(row.source_id)}</span>
        </span>
      )}
      {/* the coin with its icon and the search, like the entry form (Vanixxx, 2026-10-11) */}
      <div className="grid items-start gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] md:grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="grid min-w-0 gap-1">
          <Field id={`tf-${key}-amount`} label={t('manual.amount')} inputMode="decimal" value={p[0]} onChange={(e) => set([e.target.value, p[1]])} required={required}
            placeholder={key === 'out' && held !== null ? t('manual.maxHeld', { amount: shown(held) }) : undefined} />
          {key === 'out' && held !== null && (
            <button type="button" onClick={() => set([String(held), p[1]])}
              className={`justify-self-start border-0 bg-transparent p-0 text-left text-xs ${Number(held) <= 0 ? 'text-warn' : 'text-muted hover:text-accent'}`}>
              {t('manual.heldThen', { amount: shown(held), asset: outAsset })}
            </button>
          )}
        </div>
        <AssetField id={`tf-${key}-asset`} label={t('manual.asset')} value={p[1]} onChange={(v) => set([p[0], v])} required={required} />
      </div>
    </fieldset>
  )

  return (
    <form onSubmit={submit} className="grid gap-4 rounded-ctl bg-surface-2 p-3">
      <div className="grid grid-cols-2 gap-3 md:max-w-md">
        <Field id={`tf-${send.id}-day`} label={t('manual.date')} type="date" value={day} onChange={(e) => setDay(e.target.value)} required />
        <Field id={`tf-${send.id}-time`} label={t('manual.time')} inputMode="numeric" pattern="[0-2]?[0-9]:[0-5][0-9](:[0-5][0-9])?"
          value={clock} onChange={(e) => setClock(e.target.value)} required />
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        {box('out', t('merged.roles.send'), send, out, setOut, true,
          <Combobox noAll label={t('merged.transferForm.fromWallet')} allLabel={name(send.source_id)} value={fromId} onChange={setFromId} options={sourceOptions} />)}
        {box('in', t('merged.roles.receive'), receive, inc, setInc, true,
          <Combobox noAll label={t('merged.transferForm.toWallet')} allLabel={name(receive.source_id)} value={toId} onChange={setToId} options={sourceOptions} />)}
        {both ? (
          <>
            {box('fee', t('merged.roles.extra'), send, sendFee, setSendFee, false)}
            {box('rfee', t('merged.roles.extra'), receive, recvFee, setRecvFee, false)}
          </>
        ) : (send.fee[0] || receive.fee[0] || extras.length === 0) && (
          // left out empty when an attached booking is the fee
          box('fee', t('merged.roles.extra'), feeOn === 'send' ? send : receive, ownFee, setOwnFee, false, (
            <label className="flex min-w-0 items-center gap-2 text-xs text-muted">
              <SourceAvatar {...lookup((feeOn === 'send' ? send : receive).source_id)} size={20} />
              <select aria-label={t('merged.transferForm.feeWallet')} value={feeOn} onChange={(e) => moveFee(e.target.value as 'send' | 'receive')}
                className="min-w-0 flex-1 rounded-ctl border border-line bg-surface-2 px-2 py-1.5 text-sm text-fg">
                <option value="send">{name(send.source_id)}</option>
                <option value="receive">{name(receive.source_id)}</option>
              </select>
            </label>
          ))
        )}
        {extras.map((x) => box(`x${x.id}`, t('merged.extraFee'), x, extraFees[x.id], (p) => setExtraFees({ ...extraFees, [x.id]: p }), true,
          <Combobox noAll label={t('merged.transferForm.feeWallet')} allLabel={name(x.source_id)} value={extraFrom[x.id]}
            onChange={(v) => setExtraFrom({ ...extraFrom, [x.id]: v })} options={sourceOptions} />))}
      </div>
      <span className="text-xs leading-relaxed text-muted">{t('manual.timeHint', { tz })} {t('merged.transferForm.hint')}</span>
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={busy}>{t('common.save')}</Button>
        <Button type="button" variant="ghost" onClick={onCancel}>{t('common.cancel')}</Button>
      </div>
    </form>
  )
}
