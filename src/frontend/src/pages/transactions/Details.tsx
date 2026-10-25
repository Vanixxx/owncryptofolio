import { ExternalLink, Hand, Pencil, Undo2, Unlink } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { SourceAvatar } from '../../components/SourceLogo'
import { Button, ErrorText } from '../../components/ui'
import { amount, dateTime } from '../../lib/format'
import { side } from '../../lib/rows'
import { api, type HistoryEntry, type MergedRow } from '../../lib/api'
import type { SourceRef } from '../../lib/txFilter'
import { useErrorText } from '../../lib/useErrorText'
import { VersionList } from '../RowActions'
import { Sides } from './parts'
import { explorerUrl, sameTx } from '../../lib/explorer'

export type Role = 'send' | 'receive' | 'extra' | 'row'
export type Single = { role: Role; row: MergedRow }

/** Where a line came from: API, file, chain or by hand — and "edited" when a person
 * changed it (Vanixxx, 2026-10-06: a corrected chain row is not "by hand"). */
export function Origin({ row }: { row: MergedRow }) {
  const { t } = useTranslation()
  return (
    <span className="inline-flex items-center gap-1">
      {/* entered by hand: a mark of its own, as "API" or "Datei" say where else a line came from */}
      {(row.origin ?? row.channel) === 'manual' && <Hand size={11} aria-hidden="true" />}
      {t(`pages.sources.channels.${row.origin ?? row.channel}`)}
      {row.modified && (
        <span className="inline-flex items-center gap-0.5 text-accent" title={t('manual.edited')}>
          <Pencil size={11} aria-hidden="true" /><span>{t('manual.edited')}</span>
        </span>
      )}
    </span>
  )
}

/** The facts behind a line, shown only when it is open: per single transaction its
 * source, origin, transaction ID and addresses; for a transfer how it was linked. */
export function Details({ singles, lookup, name, reason, onChanged }: {
  singles: Single[]; lookup: (id: number) => SourceRef; name: (id: number) => string; reason?: string; onChanged: () => void
}) {
  const { t } = useTranslation()
  // the line's note sits on its first row (a transfer: the send)
  const comments = singles.filter((s) => s.row.comment)
  return (
    <div className="grid gap-2 rounded-ctl bg-surface-2 p-3 text-xs">
      <Note row={singles[0].row} onChanged={onChanged} />
      {comments.map((s) => (
        <Fact key={s.row.id} label={t('merged.details.comment')}>{s.row.comment}{comments.length > 1 && <span className="text-muted"> · {t(`merged.roles.${s.role}`)}</span>}</Fact>
      ))}
      {reason && <Fact label={t('merged.details.reason')}>{t(`merged.reasons.${reason}`)}</Fact>}
      {singles.map(({ role, row }) => {
        const who = lookup(row.source_id)
        return (
          <div key={row.id} className="grid gap-1 border-t border-line pt-2 first:border-t-0 first:pt-0">
            {singles.length > 1 && <b className="text-sm">{t(`merged.roles.${role}`)}</b>}
            <Fact label={t('merged.details.source')}>
              <span className="inline-flex min-w-0 items-center gap-1.5"><SourceAvatar {...who} size={16} /><span className="truncate">{name(row.source_id)}</span></span>
            </Fact>
            <Fact label={t('merged.details.channel')}><Origin row={row} /></Fact>
            {row.external_id && !row.external_id.startsWith('form:') && <Fact label={t('merged.details.txId')} mono><TxId row={row} singles={singles} lookup={lookup} /></Fact>}
            {who.source?.address && <Fact label={t('merged.details.own')} mono>{who.source.address}</Fact>}
            {row.counterparty && <Fact label={t('merged.details.counterparty')} mono>{row.counterparty}</Fact>}
            {/* the balance right after this line at its place: below zero means something is missing */}
            {row.after && Object.keys(row.after).length > 0 && (
              <Fact label={t('merged.details.after')}>
                <span className="num flex flex-wrap gap-x-3">
                  {Object.entries(row.after).map(([asset, qty]) => (
                    <span key={asset} className={row.short?.includes(asset) ? 'font-semibold text-down' : ''}>{amount(qty)} {asset}</span>
                  ))}
                </span>
              </Fact>
            )}
          </div>
        )
      })}
    </div>
  )
}

/** Vanixxx's own note, shown and changed right in the details (Vanixxx, 2026-10-06). It is
 * not part of the transaction: writing one marks nothing as edited. */
function Note({ row, onChanged }: { row: MergedRow; onChanged: () => void }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(row.note ?? '')
  const [error, setError] = useState<unknown>(null)
  const save = (e: FormEvent) => {
    e.preventDefault()
    api.setNote(row.id, text).then(() => { setEditing(false); onChanged() }, setError)
  }
  if (!editing) {
    return (
      <Fact label={t('merged.details.note')}>
        <span className="inline-flex flex-wrap items-center gap-2">
          {row.note ? <span className="whitespace-pre-wrap">{row.note}</span> : <span className="text-muted">—</span>}
          <button type="button" onClick={() => setEditing(true)} className="inline-flex items-center gap-1 rounded p-0.5 text-accent hover:underline">
            <Pencil size={12} aria-hidden="true" />{row.note ? t('manual.edit') : t('merged.details.addNote')}
          </button>
        </span>
      </Fact>
    )
  }
  return (
    <form onSubmit={save} className="grid gap-2">
      <label className="grid gap-1">
        <span className="text-muted">{t('merged.details.note')}</span>
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={2} maxLength={2000} autoFocus
          className="w-full rounded-ctl border border-line bg-surface px-3 py-2 text-base text-fg outline-none focus:border-accent md:text-sm" />
      </label>
      <span className="flex flex-wrap gap-2">
        <Button type="submit">{t('common.save')}</Button>
        <Button type="button" variant="ghost" onClick={() => { setEditing(false); setText(row.note ?? '') }}>{t('common.cancel')}</Button>
      </span>
      {error ? <ErrorText>{errorText(error)}</ErrorText> : null}
    </form>
  )
}

function Fact({ label, mono = false, children }: { label: string; mono?: boolean; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-2">
      <span className="text-muted">{label}</span>
      <span className={mono ? 'font-mono [overflow-wrap:anywhere]' : 'min-w-0'}>{children}</span>
    </div>
  )
}

/** Every single transaction behind a merged line (Vanixxx, 2026-10-06): where, when, what,
 * from where — read only; a fee attached to a transfer can be taken off again. */
/** The transaction ID, linked to the block explorer of its network — or, on an exchange
 * side, of the chain side carrying the same hash (Vanixxx, 2026-10-14). */
function TxId({ row, singles, lookup }: { row: MergedRow; singles: Single[]; lookup: (id: number) => SourceRef }) {
  const { t } = useTranslation()
  let url = explorerUrl(lookup(row.source_id).source?.provider, row.external_id)
  if (!url) {
    for (const s of singles) {
      if (s.row.id !== row.id && sameTx(s.row.external_id, row.external_id)) {
        url = explorerUrl(lookup(s.row.source_id).source?.provider, s.row.external_id)
        if (url) break
      }
    }
  }
  if (!url) return <>{row.external_id}</>
  return (
    <a href={url} target="_blank" rel="noreferrer noopener" title={t('merged.details.explorer')} onClick={(e) => e.stopPropagation()}
      className="inline-flex items-start gap-1 text-accent no-underline hover:underline">
      <span className="[overflow-wrap:anywhere]">{row.external_id}</span><ExternalLink size={12} aria-hidden="true" className="mt-0.5 shrink-0" />
    </a>
  )
}

export function SingleList({ singles, lookup, name, tz, onDetach }: {
  singles: Single[]; lookup: (id: number) => SourceRef; name: (id: number) => string; tz: string; onDetach: (id: number) => void
}) {
  const { t } = useTranslation()
  return (
    <ul className="m-0 grid list-none gap-2 p-0">
      {singles.map(({ role, row }) => (
        <li key={row.id} className="grid gap-2 rounded-ctl border border-line p-2.5 text-xs">
          <span className="flex flex-wrap items-center justify-between gap-2">
            <b className="text-sm">{t(`merged.roles.${role}`)}{row.kind !== role && <span className="font-normal text-muted"> · {t(`kinds.${row.kind}`, { defaultValue: row.kind })}</span>}</b>
            <span className="num text-muted">{dateTime(row.timestamp, tz)}</span>
          </span>
          <span className="flex min-w-0 items-center gap-2">
            <SourceAvatar {...lookup(row.source_id)} size={22} />
            <span className="truncate text-sm">{name(row.source_id)}</span>
            <span className="text-muted">· <Origin row={row} /></span>
          </span>
          <Sides r={row} />
          {row.external_id && !row.external_id.startsWith('form:') && (
            <span className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-2"><span className="text-muted">{t('merged.details.txId')}</span><span className="font-mono [overflow-wrap:anywhere]"><TxId row={row} singles={singles} lookup={lookup} /></span></span>
          )}
          {row.counterparty && (
            <span className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-2"><span className="text-muted">{t('merged.details.counterparty')}</span><span className="font-mono [overflow-wrap:anywhere]">{row.counterparty}</span></span>
          )}
          {role === 'extra' && (
            <Button variant="ghost" className="justify-self-start" onClick={() => onDetach(row.id)}><Unlink size={14} aria-hidden="true" />{t('merged.detach')}</Button>
          )}
        </li>
      ))}
    </ul>
  )
}

/** The versions of all single transactions of a line, collected, with what a person
 * decided about the line: linked by hand, a fee attached — that one can be undone here. */
export function AllVersions({ singles, tz, reason, linkedAt, onDetach, onChanged }: {
  singles: Single[]; tz: string; reason?: string; linkedAt?: string | null; onDetach: (id: number) => void; onChanged: () => void
}) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [all, setAll] = useState<{ role: Role; id: number; history: HistoryEntry[] }[] | null>(null)
  const [error, setError] = useState<unknown>(null)
  const ids = singles.map((s) => s.row.id).join(',')
  useEffect(() => {
    let alive = true
    Promise.all(singles.map((s) => api.rawHistory(s.row.id).then((history) => ({ role: s.role, id: s.row.id, history }))))
      .then((r) => { if (alive) setAll(r) }, setError)
    return () => { alive = false }
    // the rows' ids decide
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [ids])
  const extras = singles.filter((s) => s.role === 'extra')
  if (error) return <ErrorText>{errorText(error)}</ErrorText>
  if (!all) return <p className="m-0 text-xs text-muted">{t('common.loading')}</p>
  return (
    <div className="grid gap-3">
      {(reason || extras.length > 0) && (
        <div className="grid gap-1.5">
          <b className="text-sm">{t('merged.decisions.title')}</b>
          <ol className="m-0 grid list-none gap-1.5 border-l-2 border-line p-0 pl-3 text-xs">
            {/* how the two halves came together: by hand (when), or found by ID or amount and time */}
            {reason && (
              <li>
                <b>{reason === 'manual' ? t('merged.decisions.linked') : t('merged.decisions.auto')}</b>
                <span className="text-muted">{reason !== 'manual' && <> · {t(`merged.reasons.${reason}`)}</>}{linkedAt && <> · {dateTime(linkedAt, tz)}</>}</span>
              </li>
            )}
            {extras.map(({ row }) => (
              <li key={row.id} className="flex flex-wrap items-baseline gap-x-1.5">
                <b>{t('merged.decisions.attached')}</b>
                <span className="num">{side(row.fee[0] ? row.fee : row.outgoing, '')}</span>
                {row.attached_at && <span className="text-muted">· {dateTime(row.attached_at, tz)}</span>}
                <button type="button" onClick={() => onDetach(row.id)} className="inline-flex items-center gap-1 text-accent hover:underline">
                  · <Undo2 size={11} aria-hidden="true" />{t('merged.decisions.undo')}
                </button>
              </li>
            ))}
          </ol>
        </div>
      )}
      {all.map((a) => (
        <div key={a.id} className="grid gap-1.5">
          {all.length > 1 && <b className="text-sm">{t(`merged.roles.${a.role}`)}</b>}
          <VersionList history={a.history} tz={tz} onReset={(id) => void api.restoreRaw(id).then(onChanged, setError)} />
        </div>
      ))}
    </div>
  )
}
