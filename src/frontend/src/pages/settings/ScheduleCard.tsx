import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSettings } from '../../app/settings'
import { Card, ErrorText } from '../../components/ui'
import { Toggle } from '../../components/ui/Toggle'
import { useErrorText } from '../../lib/useErrorText'
import { TimeSelect } from './TimeSelect'

/** Daily fetch of all sources (ADR 0035). */
export function ScheduleCard() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const { settings, update } = useSettings()
  const [error, setError] = useState<unknown>(null)
  const set = (c: Parameters<typeof update>[0]) => update(c).then(() => setError(null), setError)
  return (
    <Card fold="settings-open-schedules" title={t('settings.schedules.title')}>
      <p className="m-0 text-sm leading-relaxed text-muted">{t('settings.schedules.text')}</p>
      <Toggle id="fetch-enabled" label={t('settings.schedules.enabled')} checked={settings['fetch.enabled']}
        onChange={(v) => void set({ 'fetch.enabled': v })} />
      <TimeSelect id="fetch-time" label={t('settings.schedules.time')} value={settings['fetch.time']}
        onChange={(v) => void set({ 'fetch.time': v })} />
      <p className="m-0 text-xs text-muted">{t('settings.schedules.perSource')}</p>
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
    </Card>
  )
}
