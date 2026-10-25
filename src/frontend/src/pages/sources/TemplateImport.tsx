import { Download, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button, ErrorText, Segmented } from '../../components/ui'
import { BetaTag } from '../../components/Beta'
import { MappedImport } from './MappedImport'
import { api, ApiError, type TemplatePreview } from '../../lib/api'
import { date } from '../../lib/format'
import { useErrorText } from '../../lib/useErrorText'
import type { SourceChoice } from './EntryForm'

/** Many entries at once: our template (ADR 0036) for any exchange or network, or an
 * exchange's own file through a column mapping (ADR 0048, Vanixxx 2026-10-18) — both with a
 * preview first. */
export function TemplateImport({ choices, exchanges, tz, onImported, onClose }: {
  choices: SourceChoice[]; exchanges: number[]; tz: string; onImported: () => void; onClose: () => void
}) {
  const { t, i18n } = useTranslation()
  const [mode, setMode] = useState<'template' | 'own'>('template')
  const errorText = useErrorText()
  const input = useRef<HTMLInputElement>(null)
  const [target, setTarget] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<TemplatePreview | null>(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)

  async function choose(list: FileList | null) {
    const chosen = list?.[0]
    if (!chosen) return
    setFile(chosen); setPreview(null); setDone(null); setError(null); setBusy(true)
    try { setPreview(await api.previewTemplate(Number(target), chosen)) } catch (err) { setError(err) } finally { setBusy(false) }
  }
  const reset = () => { setPreview(null); setFile(null); if (input.current) input.current.value = '' }
  async function commit() {
    if (!file) return
    setBusy(true)
    try {
      const r = await api.importTemplate(Number(target), file)
      setDone(t('pages.sources.imported', { added: r.added, duplicates: r.duplicates }))
      reset(); onImported()
    } catch (err) { setError(err) } finally { setBusy(false) }
  }
  const problem = (p: TemplatePreview['problems'][number]) =>
    t('manual.row', { row: p.row }) + ': ' + errorText(new ApiError(400, p.code, p.params))

  return (
    <div className="grid gap-3 rounded-ctl bg-surface-2 p-3">
      <b className="text-sm">{t('manual.template')}</b>
      <Segmented label={t('manual.importHow')} value={mode} onChange={(m) => { setMode(m); setTarget(''); reset() }}
        options={[
          { value: 'template', label: t('manual.ourTemplate') },
          { value: 'own', label: <span className="inline-flex items-center gap-1.5">{t('mapped.title')}<BetaTag /></span> },
        ]} />
      {mode === 'template' && <p className="m-0 text-xs leading-relaxed text-muted">{t('manual.templateHint')}</p>}
      <label htmlFor="template-source" className="grid gap-1.5">
        <span className="label">{t('manual.source')}</span>
        <select id="template-source" value={target} onChange={(e) => { setTarget(e.target.value); reset() }}
          className="rounded-ctl border border-line bg-surface px-3 py-2.5 text-base text-fg">
          <option value="" disabled>{t('manual.chooseSource')}</option>
          {choices.map((c) => {
            // an own file is an exchange's export: only exchanges to choose from
            const options = mode === 'own' ? c.options.filter((o) => exchanges.includes(o.id)) : c.options
            return options.length > 0 && (
              <optgroup key={c.group} label={c.group}>
                {options.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
              </optgroup>
            )
          })}
        </select>
      </label>
      {mode === 'own' && (
        <>
          {target ? <MappedImport key={target} source={{ id: Number(target) }} onImported={onImported} />
            : <p className="m-0 text-xs leading-relaxed text-muted">{t('mapped.intro')}</p>}
          <Button variant="ghost" className="justify-self-start" onClick={onClose}>{t('common.close')}</Button>
        </>
      )}
      {mode === 'template' && <>
      <input ref={input} id="template-file" type="file" accept=".xlsx" className="sr-only"
        onChange={(e) => void choose(e.target.files)} />
      {!preview && (
        <div className="flex flex-wrap gap-2">
          <a href={api.templateUrl(i18n.language)} download
            className="inline-flex items-center gap-2 rounded-ctl border border-line px-4 py-2.5 text-sm font-semibold hover:bg-surface-2">
            <Download size={16} aria-hidden="true" />{t('manual.downloadTemplate')}
          </a>
          <label htmlFor="template-file" aria-disabled={!target} className="inline-flex cursor-pointer aria-disabled:pointer-events-none aria-disabled:opacity-50 items-center gap-2 rounded-ctl border border-line px-4 py-2.5 text-sm font-semibold hover:bg-surface-2">
            <Upload size={16} aria-hidden="true" />{busy ? t('common.loading') : t('manual.uploadTemplate')}
          </label>
        </div>
      )}
      {preview && (
        <div className="grid gap-3 rounded-ctl bg-surface-2 p-3">
          <b className="break-all text-sm">{t('pages.sources.previewTitle', { file: preview.file })}</b>
          <dl className="m-0 grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-4">
            {([['read', preview.read], ['new', preview.new], ['duplicates', preview.duplicates], ['rejected', preview.rejected]] as const).map(([k, n]) => (
              <div key={k} className="grid">
                <dt className="text-xs text-muted">{t(`pages.sources.${k}`)}</dt>
                <dd className="num m-0 font-semibold">{n}</dd>
              </div>
            ))}
          </dl>
          {preview.data_from && (
            <span className="text-xs text-muted">{t('pages.sources.period')}: {date(preview.data_from, tz)} – {date(preview.data_to, tz)}</span>
          )}
          <ul className="m-0 flex list-none flex-wrap gap-1.5 p-0">
            {Object.entries(preview.kinds).map(([k, n]) => (
              <li key={k} className="rounded-full border border-line px-2 py-0.5 text-xs">{t(`manual.kinds.${k}`)} <span className="num">{n}</span></li>
            ))}
          </ul>
          {preview.problems.length > 0 && (
            <ul className="m-0 grid gap-1 pl-4 text-xs text-down">
              {preview.problems.map((p) => <li key={p.row}>{problem(p)}</li>)}
            </ul>
          )}
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void commit()} disabled={busy || preview.new === 0}>{t('pages.sources.importNow')}</Button>
            <Button variant="ghost" onClick={reset}>{t('common.cancel')}</Button>
          </div>
        </div>
      )}
      {done && <p className="m-0 text-sm text-up">{done}</p>}
      {!preview && <Button variant="ghost" className="justify-self-start" onClick={onClose}>{t('common.close')}</Button>}
      </>}
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
    </div>
  )
}
