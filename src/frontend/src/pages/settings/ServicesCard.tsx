import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button, Card, ErrorText, Field, StatusPill } from '../../components/ui'
import { Confirm } from '../../components/ui/Confirm'
import { api, type ServiceKey } from '../../lib/api'
import { useErrorText } from '../../lib/useErrorText'

/** Free API keys of blockchain services, shared by several networks (ADR 0035). */
export function ServicesCard() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [services, setServices] = useState<ServiceKey[]>([])
  const [editing, setEditing] = useState<string | null>(null)
  const [value, setValue] = useState('')
  const [error, setError] = useState<unknown>(null)
  const load = useCallback(() => api.serviceKeys().then(setServices, setError), [])
  // load() sets state only after awaiting the server.
  // oxlint-disable-next-line react/set-state-in-effect
  useEffect(() => void load(), [load])

  const save = (service: string) =>
    api.setServiceKey(service, value).then(() => { setEditing(null); setValue(''); setError(null); void load() }, setError)

  return (
    <Card fold="settings-open-services" title={t('settings.services.title')}>
      <p className="m-0 text-sm leading-relaxed text-muted">{t('settings.services.text')}</p>
      <ul className="m-0 grid list-none p-0">
        {services.map((s) => (
          <li key={s.service} className="grid gap-2 border-t border-line py-3 first:border-t-0">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <b className="text-sm">{s.name}</b>
              <StatusPill ok={s.stored}>{s.stored ? t('settings.services.stored') : t('settings.services.missing')}</StatusPill>
            </div>
            <span className="text-xs text-muted">
              {s.used_by.length > 0 ? t('settings.services.usedBy', { networks: s.used_by.join(', ') }) : t('settings.services.notYet')}
            </span>
            <code className="break-all text-xs text-muted select-all">{s.url}</code>
            {editing === s.service ? (
              <div className="grid gap-2">
                <Field id={`service-${s.service}`} label={t('settings.services.key')} type="password" autoComplete="off"
                  value={value} onChange={(e) => setValue(e.target.value)} />
                <div className="flex gap-2">
                  <Button onClick={() => void save(s.service)} disabled={!value.trim()}>{t('common.save')}</Button>
                  <Button variant="ghost" onClick={() => { setEditing(null); setValue('') }}>{t('common.cancel')}</Button>
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                <Button variant="ghost" onClick={() => setEditing(s.service)}>
                  {s.stored ? t('pages.sources.changeCredentials') : t('settings.services.enter')}
                </Button>
                {s.stored && (
                  <Confirm label={t('pages.sources.removeCredentials')} question={t('pages.sources.removeCredentials') + '?'}
                    onConfirm={() => api.deleteServiceKey(s.service).then(load, setError)} />
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
    </Card>
  )
}
