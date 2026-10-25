import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useSettings } from '../../app/settings'
import { Button, ErrorText, Field, StatusPill } from '../../components/ui'
import { Confirm } from '../../components/ui/Confirm'
import { api, type Source } from '../../lib/api'
import { dateTime } from '../../lib/format'
import { useErrorText } from '../../lib/useErrorText'

/** API key form. Stored values are never shown again — only that they exist. */
export function ApiAccess({ source, fields, onChanged, plain }: {
  source: Source; fields: { fields: string[]; secret: string[]; multiline?: string[]; alternatives?: string[][] }; onChanged: () => void
  /** inside a fold that names it: no heading, no line of its own */
  plain?: boolean
}) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const tz = useSettings().settings['general.timezone']
  const stored = source.credentials.length > 0
  const [editing, setEditing] = useState(!stored)
  const [values, setValues] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)

  async function run(fn: () => Promise<unknown>) {
    setBusy(true); setError(null)
    try { await fn(); onChanged() } catch (err) { setError(err) } finally { setBusy(false) }
  }
  const save = (e: FormEvent) => {
    e.preventDefault()
    void run(async () => {
      await api.setCredentials(source.id, values)
      setValues({}); setEditing(false)
      await api.checkSource(source.id)
    })
  }

  return (
    <div className={plain ? 'grid gap-3' : 'grid gap-3 border-t border-line pt-3'}>
      {!plain && <span className="label">{t('pages.sources.api')}</span>}
      {editing ? (
        <form onSubmit={save} className="grid gap-3" autoComplete="off">
          <p className="m-0 text-xs leading-relaxed text-muted">{t('pages.sources.readOnlyHint')}</p>
          {source.provider === 'coinbase' && <p className="m-0 text-xs leading-relaxed text-muted">{t('pages.sources.coinbaseHint')}</p>}
          {(fields.alternatives?.length ? fields.alternatives : [fields.fields]).map((group, gi) => (
            <div key={group.join()} className="grid gap-3">
              {gi > 0 && <span className="label text-center">{t('pages.sources.or')}</span>}
              {group.map((f) => fields.multiline?.includes(f) ? (
                <label key={f} htmlFor={`cred-${source.id}-${f}`} className="grid gap-1.5">
                  <span className="label">{t(`pages.sources.fields.${f}`, { defaultValue: f })}</span>
                  {/* A PEM key or a JSON key file spans several lines; an <input> would drop the line breaks. */}
                  <textarea id={`cred-${source.id}-${f}`} rows={5} spellCheck={false} autoComplete="off"
                    required={!fields.alternatives?.length}
                    value={values[f] ?? ''} onChange={(e) => setValues({ ...values, [f]: e.target.value })}
                    className="w-full rounded-ctl border border-line bg-surface-2 px-3 py-2.5 font-mono text-xs text-fg outline-none focus:border-accent [-webkit-text-security:disc]" />
                  {f === 'key_file' && (
                    <input type="file" accept=".json,application/json" aria-label={t('pages.sources.fields.key_file')}
                      className="text-xs text-muted"
                      onChange={(e) => void e.target.files?.[0]?.text().then((text) => setValues((v) => ({ ...v, key_file: text })))} />
                  )}
                </label>
              ) : (
                <Field key={f} id={`cred-${source.id}-${f}`} label={t(`pages.sources.fields.${f}`, { defaultValue: f })}
                  type={fields.secret.includes(f) ? 'password' : 'text'} autoComplete="off" spellCheck={false}
                  value={values[f] ?? ''} onChange={(e) => setValues({ ...values, [f]: e.target.value })}
                  required={!fields.alternatives?.length} />
              ))}
            </div>
          ))}
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={busy}>{t('pages.sources.saveCredentials')}</Button>
            {stored && <Button type="button" variant="ghost" onClick={() => setEditing(false)}>{t('common.cancel')}</Button>}
          </div>
        </form>
      ) : (
        <div className="grid gap-2">
          <span className="text-sm">{t('pages.sources.credentialsStored')}</span>
          {source.last_check && (
            <div className="grid gap-0.5">
              <StatusPill ok={source.last_check.ok}>
                {source.last_check.ok ? t('pages.sources.checkOk') : t('pages.sources.checkFailed')}
                <span className="text-xs font-normal text-muted">
                  {t('pages.sources.checkedAt', { date: dateTime(source.last_check.at, tz) })}
                </span>
              </StatusPill>
              {source.last_check.message && <span className="text-xs text-muted">{source.last_check.message}</span>}
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" disabled={busy} onClick={() => void run(() => api.checkSource(source.id))}>
              {t('pages.sources.check')}
            </Button>
            <Button variant="ghost" onClick={() => setEditing(true)}>{t('pages.sources.changeCredentials')}</Button>
            <Confirm label={t('pages.sources.removeCredentials')} question={t('pages.sources.removeCredentials') + '?'}
              onConfirm={() => void run(() => api.deleteCredentials(source.id))} />
          </div>
        </div>
      )}
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
    </div>
  )
}
