import { ChevronDown, Download, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button, Card, ErrorText, StatusPill } from '../../components/ui'
import { Confirm } from '../../components/ui/Confirm'
import { api, type TaxCompare, type TaxKept } from '../../lib/api'
import { cx } from '../../lib/cx'
import { date, dateTime, money, quantity, trend } from '../../lib/format'
import { useErrorText } from '../../lib/useErrorText'

/** Every kept report of the year with its state, and a comparison with now or with the
 * version before: key figures side by side, then each transaction that changed (Vanixxx,
 * 2026-10-13). */
export function TaxHistory({ year, kept, tz, onChanged }: { year: number; kept: TaxKept[]; tz: string; onChanged: () => void }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [cmp, setCmp] = useState<{ key: string; data: TaxCompare } | null>(null)
  const [error, setError] = useState<unknown>(null)
  // a version opens for its comment and for deleting it (Vanixxx, 2026-10-13)
  const [unfolded, setUnfolded] = useState<number | null>(null)
  const open = (a: number, b?: number) => {
    const key = `${a}-${b ?? 'now'}`
    if (cmp?.key === key) return setCmp(null)
    api.taxCompare(year, a, b).then((data) => setCmp({ key, data }), setError)
  }
  return (
    <Card title={t('tax.frozen.title')}>
      <ul className="m-0 grid list-none gap-2 p-0 text-sm">
        {kept.map((f, i) => {
          const before = kept[i + 1]
          return (
            <li key={f.id} className="grid gap-1.5 rounded-ctl bg-surface-2 p-2.5">
              <button type="button" onClick={() => setUnfolded(unfolded === f.id ? null : f.id)} aria-expanded={unfolded === f.id}
                className="flex flex-wrap items-center justify-between gap-2 border-0 bg-transparent p-0 text-left text-sm text-fg">
                <span className="flex items-start gap-1.5">
                  <ChevronDown size={16} aria-hidden="true" className={cx('mt-0.5 shrink-0 text-muted transition-transform', unfolded !== f.id && '-rotate-90')} />
                  <span>
                  <b>{dateTime(f.created_at, tz)}</b> · {f.method.toUpperCase()} · {t('tax.net')} <span className="num">{money(f.summary.s23.net)}</span>
                  {f.note && <> · <b>{f.note}</b></>}
                  </span>
                </span>
                <StatusPill ok={f.same}>{f.same ? t('tax.frozen.same') : t('tax.frozen.changed')}</StatusPill>
              </button>
              {unfolded === f.id && (
                <div className="grid gap-2 border-t border-line pt-2">
                  <NoteField kept={f} onSaved={onChanged} onError={setError} />
                  <Confirm label={<><Trash2 size={15} aria-hidden="true" className="mr-1.5 inline" />{t('tax.frozen.delete')}</>}
                    question={t('tax.frozen.deleteConfirm')}
                    onConfirm={() => void api.taxKeptDelete(f.id).then(onChanged, setError)} />
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                {(['pdf', 'xlsx'] as const).map((k) => (
                  <a key={k} href={api.taxKeptFile(f.id, k)} download
                    className="inline-flex items-center gap-1.5 rounded-ctl border border-line px-3 py-2 text-sm text-fg no-underline hover:bg-surface">
                    <Download size={15} aria-hidden="true" />{t(`tax.file.${k}`)}
                  </a>
                ))}
                <Button variant="ghost" aria-pressed={cmp?.key === `${f.id}-now`} onClick={() => open(f.id)}>{t('tax.frozen.vsNow')}</Button>
                {before && (
                  <Button variant="ghost" aria-pressed={cmp?.key === `${before.id}-${f.id}`} onClick={() => open(before.id, f.id)}>
                    {t('tax.frozen.vsBefore')}
                  </Button>
                )}
              </div>
              {cmp && (cmp.key === `${f.id}-now` || (before && cmp.key === `${before.id}-${f.id}`)) && <Diff c={cmp.data} tz={tz} />}
            </li>
          )
        })}
      </ul>
      {kept.some((f) => !f.same) && <p className="m-0 text-xs text-muted">{t('tax.frozen.hint')}</p>}
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
    </Card>
  )
}

/** A comment on a kept version (Vanixxx, 2026-10-13): shown in its first line too. */
function NoteField({ kept, onSaved, onError }: { kept: TaxKept; onSaved: () => void; onError: (e: unknown) => void }) {
  const { t } = useTranslation()
  const [note, setNote] = useState(kept.note ?? '')
  const changed = note.trim() !== (kept.note ?? '')
  return (
    <form className="flex flex-wrap items-center gap-2" onSubmit={(e) => { e.preventDefault(); void api.taxKeptNote(kept.id, note).then(onSaved, onError) }}>
      <input value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} aria-label={t('tax.frozen.note')}
        placeholder={t('tax.frozen.notePlaceholder')}
        className="min-w-0 flex-1 rounded-ctl border border-line bg-surface px-3 py-1.5 text-sm text-fg" />
      {changed && <Button type="submit">{t('tax.frozen.save')}</Button>}
    </form>
  )
}

function Diff({ c, tz }: { c: TaxCompare; tz: string }) {
  const { t } = useTranslation()
  const [shown, setShown] = useState(20)
  const moved = c.figures.filter((f) => f.delta !== null && Number(f.delta) !== 0)
  const then = dateTime(c.old.created_at, tz)
  const now = c.new ? dateTime(c.new, tz) : t('tax.diff.now')
  return (
    <div className="grid gap-3 border-t border-line pt-2">
      <span className="text-xs text-muted">{t('tax.diff.between', { then, now })}</span>
      {moved.length === 0 ? <p className="m-0 text-sm text-muted">{t('tax.diff.sameFigures')}</p> : (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="label text-left">
              <th className="py-1 font-normal" />
              <th className="py-1 text-right font-normal">{then}</th>
              <th className="py-1 text-right font-normal">{now}</th>
              <th className="py-1 text-right font-normal">{t('tax.diff.delta')}</th>
            </tr>
          </thead>
          <tbody>
            {moved.map((f) => (
              <tr key={`${f.pot}${f.key}`} className="border-t border-line">
                <td className="py-1 pr-2">{t(`tax.diff.fig.${f.pot}`)} · {t(`tax.diff.key.${f.key}`)}</td>
                <td className="num py-1 text-right">{money(f.old)}</td>
                <td className="num py-1 text-right">{money(f.new)}</td>
                <td className={cx('num py-1 text-right', trend(f.delta) === 'up' && 'text-up', trend(f.delta) === 'down' && 'text-down')}>
                  {money(f.delta, 'EUR', true)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {!c.lines_known ? <p className="m-0 text-xs text-muted">{t('tax.diff.noLines')}</p>
        : c.changes.length === 0 ? <p className="m-0 text-xs text-muted">{t('tax.diff.sameLines')}</p> : (
          <div className="grid gap-1.5">
            <span className="label">{t('tax.diff.changes', { count: c.changes.length })}</span>
            <ul className="m-0 grid list-none gap-1 p-0">
              {c.changes.slice(0, shown).map((x, i) => (
                <li key={i} className="flex flex-wrap items-baseline justify-between gap-2 rounded-ctl border border-line px-2.5 py-1.5 text-xs">
                  <span className="flex flex-wrap items-baseline gap-2">
                    <span className={cx('rounded-full px-2 py-0.5', x.state === 'added' ? 'bg-up/15 text-up' : x.state === 'removed' ? 'bg-down/15 text-down' : 'bg-surface-2')}>
                      {t(`tax.diff.state.${x.state}`)}
                    </span>
                    <span>{t(`tax.tabs.${x.cat === 'year_end' ? 'yearEnd' : x.cat === 'uncovered' ? 'open' : x.cat}`)}</span>
                    <b>{x.asset}</b>
                    {x.at && x.cat !== 'year_end' && <span className="text-muted">{date(x.at, tz)}</span>}
                  </span>
                  <span className="num">
                    {x.old ? `${quantity(x.old.qty)} · ${money(x.old.amount)}` : '—'} → {x.new ? `${quantity(x.new.qty)} · ${money(x.new.amount)}` : '—'}
                  </span>
                </li>
              ))}
            </ul>
            {c.changes.length > shown && (
              <Button variant="ghost" className="justify-self-start" onClick={() => setShown((n) => n + 100)}>
                {t('tax.diff.more', { count: c.changes.length - shown })}
              </Button>
            )}
          </div>
        )}
    </div>
  )
}
