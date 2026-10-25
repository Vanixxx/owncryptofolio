import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSettings } from '../../app/settings'
import { ErrorText } from '../../components/ui'
import { Confirm } from '../../components/ui/Confirm'
import { api, type Source } from '../../lib/api'
import { date, dateTime } from '../../lib/format'
import { useErrorText } from '../../lib/useErrorText'

export function Runs({ source, onChanged, plain }: { source: Source; onChanged: () => void; plain?: boolean }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const tz = useSettings().settings['general.timezone']
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)

  return (
    <div className={plain ? 'grid gap-2' : 'grid gap-2 border-t border-line pt-3'}>
      {!plain && <span className="label">{t('pages.sources.runs')}</span>}
      {source.runs.length === 0 && <p className="m-0 text-sm text-muted">{t('pages.sources.noRuns')}</p>}
      <ul className="m-0 grid list-none gap-0 p-0">
        {source.runs.map((r) => (
          <li key={r.id} className="grid gap-1 border-t border-line py-2.5 text-sm first:border-t-0">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="min-w-0 break-all">
                <span className="rounded-full bg-surface-2 px-2 py-0.5 text-xs">{t(`pages.sources.channels.${r.channel}`)}</span>{' '}
                {r.channel === 'file' && r.label}
              </span>
              <span className="text-xs text-muted">{dateTime(r.created_at, tz)}</span>
            </div>
            <span className="num text-xs text-muted">
              +{r.added} {t('pages.sources.new')} · {r.duplicates} {t('pages.sources.duplicates')}
              {r.rejected > 0 && <span className="text-warn"> · {r.rejected} {t('pages.sources.rejected')}</span>}
              {(r.changed ?? 0) > 0 && <span className="text-warn"> · {r.changed} {t('pages.sources.changed')}</span>}
              {r.data_from && <> · {date(r.data_from, tz)} – {date(r.data_to, tz)}</>}
            </span>
            {r.revertible && (
              <div>
                <Confirm label={t('pages.sources.revert')} question={t('pages.sources.revertConfirm', { count: r.added })}
                  onConfirm={() => api.revertRun(r.id).then((res) => {
                    setMessage(t('pages.sources.reverted', { rows: res.rows })); setError(null); onChanged()
                  }, setError)} />
              </div>
            )}
          </li>
        ))}
      </ul>
      {message && <p className="m-0 text-sm text-up">{message}</p>}
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
    </div>
  )
}
