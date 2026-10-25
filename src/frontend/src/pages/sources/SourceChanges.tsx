import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button, Card, ErrorText } from '../../components/ui'
import { api, type SourceChange } from '../../lib/api'
import { dateTime } from '../../lib/format'
import { side } from '../../lib/rows'
import { useErrorText } from '../../lib/useErrorText'

/** Rows a source delivered again with other values (Vanixxx, 2026-10-23): nothing changes
 * on its own; take the new values over or keep the old ones. */
export function SourceChanges({ name, tz, onDecided }: { name: (id: number) => string; tz: string; onDecided: () => void }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [items, setItems] = useState<SourceChange[]>([])
  const [error, setError] = useState<unknown>(null)
  const load = () => api.sourceChanges().then(setItems, setError)
  // load() sets state only after awaiting the server.
  // oxlint-disable-next-line react/set-state-in-effect
  useEffect(() => void load(), [])
  if (items.length === 0 && !error) return null
  const decide = (id: number, take: boolean) =>
    api.decideChange(id, take).then(() => { setError(null); void load(); onDecided() }, setError)
  const sides = (s: SourceChange['old']) =>
    [side(s.incoming, '+'), side(s.outgoing, '−'), s.fee[0] ? `${t('pages.transactions.fee')} ${side(s.fee, '')}` : ''].filter(Boolean).join(' · ')
  return (
    <span id="changes">
      <Card title={t('sourceChanges.title', { count: items.length })}>
        <p className="m-0 text-sm leading-relaxed text-muted">{t('sourceChanges.text')}</p>
        <ErrorText>{error ? errorText(error) : null}</ErrorText>
        <ul className="m-0 grid list-none gap-3 p-0">
          {items.map((c) => (
            <li key={c.id} className="grid gap-2 rounded-ctl border border-line p-3 text-sm">
              <span className="flex flex-wrap justify-between gap-2">
                <b>{name(c.source_id)} · {t(`kinds.${c.old.kind}`, { defaultValue: c.old.kind })}</b>
                <span className="text-xs text-muted">{dateTime(c.old.timestamp, tz)}</span>
              </span>
              <span className="grid gap-1 sm:grid-cols-[6rem_minmax(0,1fr)]">
                <span className="text-muted">{t('sourceChanges.before')}</span><span className="num break-all">{sides(c.old)}</span>
                <span className="text-muted">{t('sourceChanges.after')}</span><span className="num break-all text-warn">{sides(c.new)}</span>
              </span>
              {c.old.external_id && <span className="break-all text-xs text-muted">ID {c.old.external_id}</span>}
              <span className="flex flex-wrap gap-2">
                <Button onClick={() => void decide(c.id, true)}>{t('sourceChanges.take')}</Button>
                <Button variant="ghost" onClick={() => void decide(c.id, false)}>{t('sourceChanges.keep')}</Button>
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </span>
  )
}
