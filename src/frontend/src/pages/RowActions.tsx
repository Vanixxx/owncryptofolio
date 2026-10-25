import { History, Pencil, RotateCcw, Undo2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button, ErrorText } from '../components/ui'
import { Confirm } from '../components/ui/Confirm'
import { api, type HistoryEntry, type RawRow } from '../lib/api'
import { entryOf } from '../lib/entry'
import { amount, dateTime } from '../lib/format'
import { useErrorText } from '../lib/useErrorText'
import { EntryForm } from './sources/EntryForm'

/** What can be done with one row (ADR 0037): edit, hide or delete, reset to the original,
 * the history with the changes per version — always there (Vanixxx, 2026-10-06). A row
 * linked into a transfer is not hidden from here: that is "split" on the transfer. */
export function RowActions({ row, tz, onChanged, linked = false }: { row: RawRow; tz: string; onChanged: () => void; linked?: boolean }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [mode, setMode] = useState<'idle' | 'edit' | 'history'>('idle')
  const [history, setHistory] = useState<HistoryEntry[] | null>(null)
  const [error, setError] = useState<unknown>(null)
  // own entries are deleted; what a source delivered (also once corrected) is hidden
  const manual = row.channel === 'manual' && row.corrects === null
  const done = () => { setMode('idle'); setError(null); onChanged() }

  async function showHistory() {
    if (mode === 'history') { setMode('idle'); return }
    setMode('history')
    try { setHistory(await api.rawHistory(row.id)) } catch (err) { setError(err) }
  }

  // back to what the source delivered: the first version of the chain counts again
  async function reset() {
    try {
      const versions = await api.rawHistory(row.id)
      await api.restoreRaw(versions[0].id)
      done()
    } catch (err) { setError(err) }
  }

  if (mode === 'edit') {
    return <EntryForm entry={entryOf(row, tz)} fromSourceId={row.source_id} tz={tz} onDone={done} onCancel={() => setMode('idle')} />
  }
  return (
    <div className="grid gap-2">
      <div className="flex flex-wrap items-center gap-2">
        {row.state === 'current' ? (
          <>
            <Button variant="ghost" onClick={() => setMode('edit')}><Pencil size={14} aria-hidden="true" />{t('manual.edit')}</Button>
            {row.modified && (
              <Confirm label={<><Undo2 size={14} aria-hidden="true" />{t('manual.reset')}</>} question={t('manual.resetConfirm')}
                onConfirm={() => void reset()} />
            )}
            {!linked && (
              <Confirm label={manual ? t('manual.delete') : t('manual.hide')}
                question={manual ? t('manual.deleteConfirm') : t('manual.hideConfirm')}
                onConfirm={() => api.hideRaw(row.id).then(done, setError)} />
            )}
          </>
        ) : (
          <Button variant="ghost" onClick={() => void api.restoreRaw(row.id).then(done, setError)}>
            <RotateCcw size={14} aria-hidden="true" />{t('manual.unhide')}
          </Button>
        )}
        <Button variant="ghost" aria-expanded={mode === 'history'} onClick={() => void showHistory()}>
          <History size={14} aria-hidden="true" />{t('merged.versions')}
        </Button>
      </div>
      {mode === 'history' && history && <VersionList history={history} tz={tz} onReset={(id) => api.restoreRaw(id).then(done, setError)} />}
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
    </div>
  )
}

export function RowVersions({ row, tz, onChanged }: { row: RawRow; tz: string; onChanged: () => void }) {
  const errorText = useErrorText()
  const [history, setHistory] = useState<HistoryEntry[] | null>(null)
  const [error, setError] = useState<unknown>(null)
  useEffect(() => {
    let alive = true
    api.rawHistory(row.id).then((h) => { if (alive) setHistory(h) }, setError)
    return () => { alive = false }
  }, [row.id])
  if (error) return <ErrorText>{errorText(error)}</ErrorText>
  return history ? <VersionList history={history} tz={tz} onReset={(id) => void api.restoreRaw(id).then(onChanged, setError)} /> : null
}

/** The versions of one row, oldest first, each with what changed against the one before. */
export function VersionList({ history, tz, onReset }: { history: HistoryEntry[]; tz: string; onReset?: (id: number) => void }) {
  const { t } = useTranslation()
  if (history.length <= 1 && history[0]?.state === 'current') {
    return <p className="m-0 text-xs text-muted">{t('merged.details.none')}</p>
  }
  // compact like the details (Vanixxx, 2026-10-06): a thin line per version, the changes inline
  return (
    <ol className="m-0 grid list-none gap-1.5 border-l-2 border-line p-0 pl-3">
      {history.map((h, i) => (
        <Version key={h.id} entry={h} previous={i > 0 ? history[i - 1] : null} tz={tz}
          onReset={onReset && (() => onReset(h.id))} />
      ))}
    </ol>
  )
}

type Field = { key: string; value: string }

function fields(h: HistoryEntry, tz: string, t: (k: string, o?: Record<string, unknown>) => string): Field[] {
  const side = (a: string | null, n: string | null) => (a && n ? `${amount(n)} ${a}` : '—')
  const kind = t(`kinds.${h.kind}`, { defaultValue: h.kind })
  return [
    { key: 'time', value: dateTime(h.timestamp, tz) },
    { key: 'kind', value: h.market === 'futures' ? `Futures · ${kind}${h.instrument ? ` · ${h.instrument}` : ''}` : kind },
    { key: 'incoming', value: side(h.incoming_asset, h.incoming_amount) },
    { key: 'outgoing', value: side(h.outgoing_asset, h.outgoing_amount) },
    { key: 'fee', value: side(h.fee_asset, h.fee_amount) },
    { key: 'comment', value: h.comment || '—' },
  ]
}

function Version({ entry: h, previous, tz, onReset }: {
  entry: HistoryEntry; previous: HistoryEntry | null; tz: string; onReset?: () => void
}) {
  const { t } = useTranslation()
  const now = fields(h, tz, t)
  const before = previous ? fields(previous, tz, t) : null
  // the first version: what it was (kind and amounts), not every field; later ones: what changed
  const changed = before
    ? now.filter((f, i) => f.value !== before[i].value)
    : now.filter((f) => f.value !== '—' && f.key !== 'time' && f.key !== 'comment')
  const title = previous ? t('manual.versionEdited') : h.channel === 'manual' ? t('manual.versionFirst') : t('manual.versionOriginal')
  return (
    <li className="grid gap-0.5 text-xs">
      <span className="flex flex-wrap items-baseline gap-x-1.5">
        <b>{title}</b>
        <span className="text-muted">· {t(`pages.sources.channels.${h.channel}`)} · {dateTime(h.recorded_at, tz)}</span>
        {h.state === 'current' && <span className="text-up">· {t('manual.states.current')}</span>}
        {h.state !== 'current' && onReset && (
          <button type="button" onClick={onReset} className="inline-flex items-center gap-1 text-accent hover:underline">
            · <RotateCcw size={11} aria-hidden="true" />{previous ? t('manual.resetHere') : t('manual.resetOriginal')}
          </button>
        )}
      </span>
      <span className="num flex flex-wrap gap-x-3 gap-y-0.5 [overflow-wrap:anywhere]">
        {changed.map((f) => {
          const old = before?.find((b) => b.key === f.key)?.value
          return (
            <span key={f.key}>
              <span className="text-muted">{t(`manual.fields.${f.key}`)}</span>{' '}
              {old !== undefined && <><span className="text-muted line-through">{old}</span> → </>}{f.value}
            </span>
          )
        })}
        {changed.length === 0 && <span className="text-muted">{t('manual.noChange')}</span>}
      </span>
    </li>
  )
}
