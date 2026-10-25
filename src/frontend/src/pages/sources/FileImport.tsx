import { Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSettings } from '../../app/settings'
import { Button, ErrorText } from '../../components/ui'
import { api, type Preview, type Source } from '../../lib/api'
import { date } from '../../lib/format'
import { useErrorText } from '../../lib/useErrorText'

/** Choose a file -> preview (writes nothing) -> import. */
export function FileImport({ source, onImported, plain }: { source: Source; onImported: () => void; plain?: boolean }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const tz = useSettings().settings['general.timezone']
  const input = useRef<HTMLInputElement>(null)
  const [files, setFiles] = useState<File[]>([])
  const [preview, setPreview] = useState<Preview | null>(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)

  async function choose(list: FileList | null) {
    const chosen = list ? Array.from(list) : []
    if (chosen.length === 0) return
    setFiles(chosen); setPreview(null); setDone(null); setError(null); setBusy(true)
    try { setPreview(await api.previewImport(source.id, chosen)) } catch (err) { setError(err) } finally { setBusy(false) }
  }
  async function commit() {
    if (files.length === 0) return
    setBusy(true)
    try {
      const run = await api.importFile(source.id, files)
      setDone(t('pages.sources.imported', { added: run.added, duplicates: run.duplicates }))
      setPreview(null); setFiles([]); onImported()
    } catch (err) { setError(err) } finally { setBusy(false) }
  }
  const reset = () => { setPreview(null); setFiles([]); if (input.current) input.current.value = '' }

  return (
    <div className={plain ? 'grid gap-3' : 'grid gap-3 border-t border-line pt-3'}>
      {!plain && <span className="label">{t('pages.sources.file')}</span>}
      <input ref={input} id={`file-${source.id}`} type="file" multiple accept=".zip,.csv,.xlsx,.xls,.htm,.html" className="sr-only"
        onChange={(e) => void choose(e.target.files)} />
      {!preview && (
        <label htmlFor={`file-${source.id}`} className="inline-flex w-fit cursor-pointer items-center gap-2 rounded-ctl border border-line px-4 py-2.5 text-sm font-semibold hover:bg-surface-2">
          <Upload size={16} aria-hidden="true" />{busy ? t('common.loading') : t('pages.sources.chooseFile')}
        </label>
      )}
      {preview && (
        <div className="grid gap-3 rounded-ctl bg-surface-2 p-3">
          <b className="break-all text-sm">{t('pages.sources.previewTitle', { file: preview.file })}</b>
          <dl className="m-0 grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-4">
            {([
              ['read', preview.read],
              ['duplicates', preview.duplicates],
              ['covered', preview.covered_by_api],
              ['rejected', preview.rejected],
            ] as const).map(([k, n]) => (
              <div key={k} className="grid">
                <dt className="text-xs text-muted">{t(`pages.sources.${k}`)}</dt>
                <dd className="num m-0 font-semibold">{n}</dd>
              </div>
            ))}
          </dl>
          <p className="m-0 text-sm">
            <b className="num text-up">{preview.new - preview.covered_by_api}</b> {t('pages.sources.counting')}
          </p>
          {preview.data_from && (
            <span className="text-xs text-muted">
              {t('pages.sources.period')}: {date(preview.data_from, tz)} – {date(preview.data_to, tz)}
            </span>
          )}
          <ul className="m-0 flex list-none flex-wrap gap-1.5 p-0">
            {Object.entries(preview.kinds).map(([k, n]) => {
              const [market, kind] = k.split(':')
              return (
                <li key={k} className="rounded-full border border-line px-2 py-0.5 text-xs">
                  {market === 'futures' ? 'Futures · ' : ''}{t(`kinds.${kind}`, { defaultValue: kind })} <span className="num">{n}</span>
                </li>
              )
            })}
          </ul>
          {Object.keys(preview.skipped).length > 0 && (
            <details className="text-xs text-muted">
              <summary>{t('pages.sources.skippedFiles', { count: Object.keys(preview.skipped).length })}</summary>
              <ul className="m-0 mt-1 pl-4">
                {Object.entries(preview.skipped).map(([name, n]) => <li key={name} className="break-all">{name} ({n})</li>)}
              </ul>
            </details>
          )}
          {preview.problems.length > 0 && (
            <details className="text-xs text-muted">
              <summary>{t('pages.sources.problems')} ({preview.problems.length})</summary>
              <ul className="m-0 mt-1 pl-4">{preview.problems.map((p) => <li key={p} className="break-all">{p}</li>)}</ul>
            </details>
          )}
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void commit()} disabled={busy || preview.new === 0}>{t('pages.sources.importNow')}</Button>
            <Button variant="ghost" onClick={reset}>{t('common.cancel')}</Button>
          </div>
        </div>
      )}
      {done && <p className="m-0 text-sm text-up">{done}</p>}
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
    </div>
  )
}
