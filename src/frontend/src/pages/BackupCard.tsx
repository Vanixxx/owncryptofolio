import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSettings } from '../app/settings'
import { Button, Card, ErrorText, Segmented, StatusPill } from '../components/ui'
import { useJobs } from '../hooks/useJobs'
import { api, type BackupRun } from '../lib/api'
import { bytes, dateTime } from '../lib/format'
import { useErrorText, useMessageText } from '../lib/useErrorText'
import { KeyBox } from './Settings'
import { RestorePanel } from '../components/RestorePanel'
import { TimeSelect } from './settings/TimeSelect'

export function BackupCard() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const messageText = useMessageText()
  const { settings, update } = useSettings()
  const tz = settings['general.timezone']
  const [runs, setRuns] = useState<BackupRun[]>([])
  const [folder, setFolder] = useState('')
  const [unmounted, setUnmounted] = useState(false)
  const [key, setKey] = useState<string | null>(null)
  const [restoring, setRestoring] = useState(false)
  const [error, setError] = useState<unknown>(null)

  const load = useCallback(() => api.backups().then((b) => { setRuns(b.runs); setFolder(b.folder); setUnmounted(!!b.unmounted) }, setError), [])
  const { jobs, refresh } = useJobs(load)
  useEffect(() => void load(), [load])
  const job = jobs.find((j) => j.kind === 'backup')
  const busy = job && (job.status === 'queued' || job.status === 'running')
  const set = (changes: Parameters<typeof update>[0]) => update(changes).then(() => setError(null), setError)
  const number = (id: string, k: 'backup.keep_daily' | 'backup.keep_monthly', label: string) => (
    <label htmlFor={id} className="grid gap-1.5">
      <span className="label">{label}</span>
      <input id={id} type="number" min={k === 'backup.keep_daily' ? 1 : 0} max={k === 'backup.keep_daily' ? 365 : 120}
        value={settings[k]} onChange={(e) => e.target.value && set({ [k]: Number(e.target.value) })}
        className="num w-28 rounded-ctl border border-line bg-surface-2 px-3 py-2 text-base text-fg" />
    </label>
  )

  return (
    <Card fold="settings-open-backup" title={t('settings.backup.title')}>
      <div className="flex flex-wrap items-center gap-3">
        <Button disabled={!!busy} onClick={() => api.startJob('backup').then(refresh, setError)}>
          {busy ? t('settings.backup.running') : t('settings.backup.now')}
        </Button>
        {job?.status === 'failed' && job.message && <ErrorText>{messageText(job.message)}</ErrorText>}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="grid gap-1.5">
          <span className="label">{t('settings.backup.enabled')}</span>
          <Segmented label={t('settings.backup.enabled')} value={settings['backup.enabled'] ? 'on' : 'off'}
            onChange={(v) => set({ 'backup.enabled': v === 'on' })}
            options={[{ value: 'on', label: t('common.yes') }, { value: 'off', label: t('common.no') }]} />
        </div>
        <TimeSelect id="backup-time" label={t('settings.backup.time')} value={settings['backup.time']}
          onChange={(v) => void set({ 'backup.time': v })} />
        {number('keep-daily', 'backup.keep_daily', t('settings.backup.keepDaily'))}
        {number('keep-monthly', 'backup.keep_monthly', t('settings.backup.keepMonthly'))}
      </div>
      <div className="grid gap-1 text-sm">
        <span className="label">{t('settings.backup.folder')}</span>
        <code className="break-all font-mono text-xs">{folder}</code>
        {/* a backup folder that is no mount lives inside the container (Vanixxx, 2026-10-23) */}
        {unmounted && <p className="m-0 text-sm text-warn">{t('settings.backup.unmounted')}</p>}
        <span className="text-xs leading-relaxed text-warn">{t('settings.backup.external')}</span>
      </div>

      <div className="grid gap-1">
        <span className="label">{t('settings.backup.history')}</span>
        {runs.length === 0 && <p className="m-0 text-sm text-muted">{t('settings.backup.empty')}</p>}
        <ul className="m-0 grid list-none p-0">
          {runs.slice(0, 10).map((r) => (
            <li key={r.id} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-t border-line py-2 text-sm first:border-t-0">
              <span className="text-muted">
                {dateTime(r.started_at, tz)}
                {r.trigger === 'before_restore' && <b className="ml-2 text-xs font-semibold text-warn">{t('settings.backup.beforeRestore')}</b>}
              </span>
              {r.status === 'done' ? (
                <StatusPill ok={!!r.probe_ok}>{r.probe_ok ? t('settings.backup.probeOk') : t('settings.backup.probeFailed')}</StatusPill>
              ) : (
                <StatusPill ok={false}>{t(`settings.backup.status.${r.status}`, { defaultValue: r.status })}</StatusPill>
              )}
              <span className="num text-xs text-muted">
                {r.rows !== null && t('settings.backup.rows', { count: r.rows })} {r.size_bytes !== null && `· ${bytes(r.size_bytes)}`}
              </span>
              {r.message && <span className="w-full break-all text-xs text-down">{r.message}</span>}
            </li>
          ))}
        </ul>
      </div>

      <div className="grid gap-2 border-t border-line pt-3">
        <span className="label">{t('settings.backup.key')}</span>
        <p className="m-0 text-sm leading-relaxed text-muted">{t('settings.backup.keyText')}</p>
        {key && <KeyBox value={key} />}
        <Button variant="ghost" className="justify-self-start"
          onClick={() => (key ? setKey(null) : api.backupKey().then((r) => setKey(r.backup_key), setError))}>
          {key ? t('settings.backup.hide') : t('settings.backup.show')}
        </Button>
      </div>

      <div className="grid gap-2 border-t border-line pt-3">
        <span className="label">{t('restore.title')}</span>
        <p className="m-0 text-sm leading-relaxed text-muted">{t('restore.text')}</p>
        {restoring ? <RestorePanel onDone={() => window.location.reload()} />
          : <Button variant="ghost" className="justify-self-start" onClick={() => setRestoring(true)}>{t('restore.open')}</Button>}
      </div>
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
    </Card>
  )
}
