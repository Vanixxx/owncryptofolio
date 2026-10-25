import { AlertTriangle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, setRestoring, type BackupFile, type BackupInfo } from '../lib/api'
import { bytes, date, dateTime } from '../lib/format'
import { useErrorText } from '../lib/useErrorText'
import { Button, ErrorText, Field, Segmented } from './ui'

/** Bring a backup back (Vanixxx, 2026-10-21): pick it (folder or upload), see what is inside,
 * read the warning, confirm, restore. In the settings everything now is replaced (after an
 * automatic backup of it); at first start the empty installation is filled. */
export function RestorePanel({ code, onDone }: { code?: string; onDone: () => void }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const setup = code !== undefined
  const [from, setFrom] = useState<'folder' | 'upload'>('folder')
  const [list, setList] = useState<BackupFile[] | null>(null)
  const [name, setName] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [key, setKey] = useState('')
  const [info, setInfo] = useState<BackupInfo | null>(null)
  const [understood, setUnderstood] = useState(false)
  const [busy, setBusy] = useState<'' | 'inspect' | 'restore'>('')
  const [done, setDone] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    void (setup ? api.setupBackups(code!) : api.backupFiles()).then((l) => {
      setList(l)
      if (l[0]) setName(l[0].name)
      if (!l.length) setFrom('upload')
    }, setError)
  }, [setup, code])

  const reset = () => { setInfo(null); setUnderstood(false); setError(null) }
  // an uploaded file is stored next to the others first; its name is used from then on
  const target = async () => {
    if (from === 'folder') return name
    const r = setup ? await api.setupBackupUpload(code!, files) : await api.backupUpload(files)
    setFrom('folder'); setName(r.name)
    setList((l) => [{ name: r.name, size: 0, at: new Date().toISOString(), keys: files.some((f) => f.name.endsWith('.keys.enc')) }, ...(l ?? [])])
    return r.name
  }
  const inspect = async () => {
    setBusy('inspect'); reset()
    try {
      const n = await target()
      setInfo(setup ? await api.setupRestoreInspect(code!, n, key) : await api.backupInspect(n, key))
    } catch (err) { setError(err) } finally { setBusy('') }
  }
  const restore = async () => {
    if (!info) return
    setBusy('restore'); setError(null); setRestoring(true)
    try {
      const r = setup ? await api.setupRestore(code!, info.file, key) : await api.backupRestore(info.file, key)
      setDone(t(setup ? 'restore.doneSetup' : r.keys_restored ? 'restore.done' : 'restore.doneNoKeys', { safety: r.safety ?? '' }))
      setTimeout(onDone, setup ? 1500 : 3500)
    } catch (err) { setError(err) } finally { setBusy(''); setRestoring(false) }
  }

  if (done) return <p role="status" className="m-0 text-sm leading-relaxed text-up">{done}</p>

  return (
    // min-w-0: long file names and keys must not push the card wider than the phone
    <div className="grid min-w-0 gap-3">
      <Segmented label={t('restore.from')} value={from} onChange={(v) => { setFrom(v); reset() }}
        options={[{ value: 'folder', label: t('restore.folder') }, { value: 'upload', label: t('restore.upload') }]} />
      {from === 'folder' ? (
        list && list.length === 0 ? <p className="m-0 text-sm text-muted">{t('restore.none')}</p> : (
          <select aria-label={t('restore.folder')} value={name} onChange={(e) => { setName(e.target.value); reset() }}
            className="w-full min-w-0 rounded-ctl border border-line bg-surface-2 px-3 py-2 text-sm text-fg">
            {list?.map((f) => (
              <option key={f.name} value={f.name}>
                {dateTime(f.at)}{f.size ? ` · ${bytes(f.size)}` : ''}{f.keys ? '' : ` · ${t('restore.oldNoKeys')}`}
              </option>
            ))}
          </select>
        )
      ) : (
        <label className="grid gap-1 text-sm">
          <span className="text-xs text-muted">{t('restore.uploadHint')}</span>
          <input type="file" multiple accept=".enc" onChange={(e) => { setFiles(Array.from(e.target.files ?? [])); reset() }} />
        </label>
      )}
      <Field id={setup ? 'setup-restore-key' : 'restore-key'} label={t(setup ? 'restore.key' : 'restore.keyOptional')}
        value={key} onChange={(e) => { setKey(e.target.value.trim()); reset() }} autoComplete="off" spellCheck={false}
        className="w-full min-w-0 font-mono text-sm" required={setup} />
      {!info && (
        <Button variant="ghost" className="justify-self-start" disabled={!!busy || (from === 'upload' ? !files.length : !name) || (setup && !key)}
          onClick={() => void inspect()}>
          {busy === 'inspect' ? t('restore.inspecting') : t('restore.inspect')}
        </Button>
      )}

      {info && (
        <div className="grid min-w-0 gap-3">
          <dl className="m-0 grid grid-cols-2 gap-x-4 gap-y-1 rounded-ctl bg-surface-2 p-3 text-sm">
            <dt className="text-muted">{t('restore.rows')}</dt><dd className="num m-0 font-semibold">{info.rows}</dd>
            <dt className="text-muted">{t('restore.sources')}</dt><dd className="num m-0 font-semibold">{info.sources}</dd>
            <dt className="text-muted">{t('restore.period')}</dt>
            <dd className="m-0">{info.first ? `${date(info.first)} – ${date(info.last)}` : '–'}</dd>
            <dt className="text-muted">{t('restore.keys')}</dt>
            <dd className={info.keys ? 'm-0 text-up' : 'm-0 text-warn'}>{info.keys ? t('restore.keysYes') : t('restore.keysNo')}</dd>
          </dl>
          {/* the warning, every time (Vanixxx, 2026-10-21) */}
          <div role="alert" className="grid gap-2 rounded-ctl border border-down/60 bg-down/10 p-3 text-sm leading-relaxed">
            <b className="flex items-center gap-2 text-down"><AlertTriangle size={16} aria-hidden="true" />{t(setup ? 'restore.warnTitleSetup' : 'restore.warnTitle')}</b>
            <span>{t(setup ? 'restore.warnSetup' : 'restore.warn')}</span>
            <label className="flex items-start gap-2">
              <input type="checkbox" checked={understood} onChange={(e) => setUnderstood(e.target.checked)} className="mt-1" />
              <span>{t(setup ? 'restore.understoodSetup' : 'restore.understood')}</span>
            </label>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button disabled={!understood || !!busy} onClick={() => void restore()} className="bg-down! text-white!">
              {busy === 'restore' ? t('restore.running') : t('restore.now')}
            </Button>
            <Button variant="ghost" disabled={!!busy} onClick={reset}>{t('common.cancel')}</Button>
          </div>
        </div>
      )}
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
    </div>
  )
}
