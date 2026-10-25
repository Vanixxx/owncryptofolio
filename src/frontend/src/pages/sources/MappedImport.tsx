import { Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSettings } from '../../app/settings'
import { Button, ErrorText, Segmented } from '../../components/ui'
import { api, type MappedInfo, type MappedPreview, type MappedSide, type Mapping, type MappingForm, type Source } from '../../lib/api'
import { cx } from '../../lib/cx'
import { date, dateTime, quantity } from '../../lib/format'
import { useErrorText } from '../../lib/useErrorText'

const ROLES: Record<MappingForm, string[]> = {
  movement: ['date', 'time', 'type', 'asset', 'amount', 'counter_asset', 'counter_amount', 'fee_amount', 'fee_asset', 'id', 'comment'],
  trade: ['date', 'time', 'pair', 'base', 'quote', 'side', 'amount', 'price', 'total', 'fee_amount', 'fee_asset', 'id', 'comment'],
}
const REQUIRED: Record<MappingForm, string[]> = { movement: ['date', 'type', 'amount'], trade: ['date', 'side', 'amount'] }
// buy/sell: a whole trade in one row with its counter value; trade: one of two rows with one id
const KINDS = ['buy', 'sell', 'convert', 'trade', 'deposit', 'withdrawal', 'income', 'internal', 'fee', 'ignore']
const SIDES = ['buy', 'sell', 'ignore']
const DELIMITERS = [';', ',', '\t', '|']
const SELECT = 'w-full min-w-0 rounded-ctl border border-line bg-surface px-2 py-1.5 text-sm text-fg'

/** An exchange's own file through a column mapping (ADR 0048): choose the file, check the
 * recognised columns and words, look at the rows as they would be booked, import. The
 * mapping is kept for the next file of this source. */
export function MappedImport({ source, onImported }: { source: Pick<Source, 'id'>; onImported: () => void }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const tz = useSettings().settings['general.timezone']
  const input = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [info, setInfo] = useState<MappedInfo | null>(null)
  const [mapping, setMappingState] = useState<Mapping | null>(null)
  const [preview, setPreview] = useState<MappedPreview | null>(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)

  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setError(null)
    try { await fn() } catch (err) { setError(err) } finally { setBusy(false) }
  }
  const inspect = (f: File, opts: Parameters<typeof api.mappedInspect>[2] = {}) => run(async () => {
    const i = await api.mappedInspect(source.id, f, opts)
    setInfo(i); setMappingState(i.mapping); setPreview(null)
  })
  const choose = (list: FileList | null) => {
    const f = list?.[0]
    if (!f) return
    setFile(f); setDone(null)
    void inspect(f)
  }
  // any change makes the preview stale
  const setMapping = (m: Mapping) => { setMappingState(m); setPreview(null) }
  const reset = () => {
    setFile(null); setInfo(null); setMappingState(null); setPreview(null)
    if (input.current) input.current.value = ''
  }
  const commit = () => run(async () => {
    if (!file || !mapping) return
    const r = await api.mappedImport(source.id, file, mapping)
    setDone(t('pages.sources.imported', { added: r.added, duplicates: r.duplicates }))
    reset(); onImported()
  })

  const problem = (message: string) => {
    const [code, ...rest] = message.split(':')
    return t(`mapped.problems.${code}`, { v: rest.join(':'), defaultValue: message })
  }

  return (
    <div className="grid gap-3">
      <p className="m-0 text-xs leading-relaxed text-muted">{t('mapped.intro')}</p>
      <input ref={input} id={`mapped-${source.id}`} type="file" accept=".csv,.txt,.tsv,.xlsx,.xlsm" className="sr-only"
        onChange={(e) => choose(e.target.files)} />
      {!info && (
        <label htmlFor={`mapped-${source.id}`} className="inline-flex w-fit cursor-pointer items-center gap-2 rounded-ctl border border-line px-4 py-2.5 text-sm font-semibold hover:bg-surface-2">
          <Upload size={16} aria-hidden="true" />{busy ? t('common.loading') : t('pages.sources.chooseFile')}
        </label>
      )}
      {info && mapping && file && (
        <div className="grid gap-4 rounded-ctl bg-surface-2 p-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <b className="break-all text-sm">{file.name}</b>
            <span className="text-xs text-muted">
              {t('mapped.rows', { count: info.rows })}{info.saved && <> · {t('mapped.saved')}</>}
            </span>
          </div>
          <FileLook info={info} mapping={mapping} />
          <FileSettings info={info} mapping={mapping} tz={tz} busy={busy}
            onReread={(opts) => void inspect(file, opts)} onChange={setMapping} />
          <Columns info={info} mapping={mapping} onChange={setMapping} />
          <Values info={info} mapping={mapping} onChange={setMapping} />
          {preview && <PreviewBox preview={preview} tz={tz} problem={problem} />}
          <div className="flex flex-wrap gap-2">
            {!preview
              ? <Button onClick={() => void run(async () => setPreview(await api.mappedPreview(source.id, file, mapping)))} disabled={busy}>{t('mapped.preview')}</Button>
              : <Button onClick={() => void commit()} disabled={busy || preview.new <= 0}>{t('pages.sources.importNow')}</Button>}
            <Button variant="ghost" onClick={reset}>{t('common.cancel')}</Button>
          </div>
          {preview && <p className="m-0 text-xs text-muted">{t('mapped.keep')}</p>}
        </div>
      )}
      {done && <p className="m-0 text-sm text-up">{done}</p>}
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
    </div>
  )
}

/** The file as it is, folded: its first rows with the heading row marked and, above each
 * column, the field it is mapped to (Vanixxx, 2026-10-18: easier to map). */
function FileLook({ info, mapping }: { info: MappedInfo; mapping: Mapping }) {
  const { t } = useTranslation()
  const role = Object.fromEntries(Object.entries(mapping.columns).map(([r, c]) => [c, r]))
  const width = Math.max(...info.top.map((r) => r.length), info.columns.length)
  return (
    <details className="rounded-ctl border border-line bg-surface text-xs">
      <summary className="cursor-pointer px-3 py-2 font-semibold">{t('mapped.look', { count: info.top.length })}</summary>
      <div className="max-h-80 overflow-auto border-t border-line">
        <table className="w-full border-collapse font-mono text-[0.7rem]">
          <thead className="sticky top-0 bg-surface">
            <tr>
              <th className="px-1.5 py-1" />
              {Array.from({ length: width }, (_, j) => {
                const r = role[info.columns[j]]
                return (
                  <th key={j} className={cx('whitespace-nowrap px-1.5 py-1 text-left font-sans font-semibold', r ? 'text-accent' : 'text-muted')}>
                    {r ? t(`mapped.roles.${r}`) : '–'}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {info.top.map((r, i) => (
              <tr key={i} className={cx('border-t border-line/50', i === mapping.header_row && 'bg-accent/10 font-semibold', i < mapping.header_row && 'text-muted')}>
                <td className="num px-1.5 py-0.5 text-muted">{i + 1}</td>
                {Array.from({ length: width }, (_, j) => <td key={j} className="whitespace-nowrap px-1.5 py-0.5">{r[j] ?? ''}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}

function FileSettings({ info, mapping, tz, busy, onReread, onChange }: {
  info: MappedInfo; mapping: Mapping; tz: string; busy: boolean
  onReread: (opts: { sheet?: string | null; header_row?: number; delimiter?: string | null }) => void
  onChange: (m: Mapping) => void
}) {
  const { t } = useTranslation()
  const zones = [...new Set([tz, 'UTC', mapping.timezone])]
  const field = (label: string, el: React.ReactNode) => (
    <label className="grid min-w-0 gap-1"><span className="text-xs text-muted">{label}</span>{el}</label>
  )
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
      {info.sheets.length > 1 && field(t('mapped.sheet'), (
        <select className={SELECT} value={mapping.sheet ?? ''} disabled={busy} onChange={(e) => onReread({ sheet: e.target.value })}>
          {info.sheets.map((s) => <option key={s}>{s}</option>)}
        </select>
      ))}
      {field(t('mapped.headerRow'), (
        <input type="number" min={1} max={info.top.length} className={SELECT} value={mapping.header_row + 1} disabled={busy}
          onChange={(e) => onReread({ sheet: mapping.sheet, delimiter: mapping.delimiter, header_row: Math.max(0, Number(e.target.value) - 1) })} />
      ))}
      {mapping.delimiter !== null && field(t('mapped.delimiter'), (
        <select className={SELECT} value={mapping.delimiter} disabled={busy}
          onChange={(e) => onReread({ delimiter: e.target.value, header_row: mapping.header_row })}>
          {DELIMITERS.map((d) => <option key={d} value={d}>{t(`mapped.delimiters.${d === '\t' ? 'tab' : d}`, { defaultValue: d })}</option>)}
        </select>
      ))}
      {field(t('mapped.decimal'), (
        <select className={SELECT} value={mapping.decimal} onChange={(e) => onChange({ ...mapping, decimal: e.target.value as Mapping['decimal'] })}>
          <option value=".">1,234.56</option>
          <option value=",">1.234,56</option>
        </select>
      ))}
      {field(t('mapped.dateFormat'), (
        <input className={SELECT} value={mapping.date_format ?? ''} placeholder={t('mapped.auto')}
          onChange={(e) => onChange({ ...mapping, date_format: e.target.value || null })} />
      ))}
      {field(t('mapped.timezone'), (
        <select className={SELECT} value={mapping.timezone} onChange={(e) => onChange({ ...mapping, timezone: e.target.value })}>
          {zones.map((z) => <option key={z}>{z}</option>)}
        </select>
      ))}
    </div>
  )
}

function Columns({ info, mapping, onChange }: { info: MappedInfo; mapping: Mapping; onChange: (m: Mapping) => void }) {
  const { t } = useTranslation()
  const first = info.sample[0] ?? {}
  const set = (role: string, column: string) => {
    const columns = { ...mapping.columns }
    if (column) columns[role] = column
    else delete columns[role]
    onChange({ ...mapping, columns })
  }
  const roles = ROLES[mapping.form]
  return (
    <div className="grid gap-2">
      <Segmented label={t('mapped.form')} value={mapping.form}
        onChange={(form) => onChange({ ...mapping, form, values: {} })}
        options={(['movement', 'trade'] as const).map((f) => ({ value: f, label: t(`mapped.forms.${f}`) }))} />
      <p className="m-0 text-xs text-muted">{t(`mapped.formHint.${mapping.form}`)}</p>
      <div className="grid gap-x-4 gap-y-2 sm:grid-cols-2">
        {roles.map((role) => {
          const col = mapping.columns[role]
          const need = REQUIRED[mapping.form].includes(role) && !(role === 'type' && mapping.kind)
          return (
            <label key={role} className="grid grid-cols-[8.5rem_minmax(0,1fr)] items-center gap-2 text-sm">
              <span className={cx('text-xs', need && !col ? 'font-semibold text-down' : 'text-muted')}>
                {t(`mapped.roles.${role}`)}{need && ' *'}
              </span>
              <span className="grid min-w-0 gap-0.5">
                <select className={SELECT} value={col ?? ''} onChange={(e) => set(role, e.target.value)}>
                  <option value="">—</option>
                  {info.columns.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
                {col && first[col] && <span className="truncate font-mono text-[0.68rem] text-muted">{first[col]}</span>}
              </span>
            </label>
          )
        })}
      </div>
      {mapping.form === 'trade' && <p className="m-0 text-xs text-muted">{t('mapped.tradeNeeds')}</p>}
    </div>
  )
}

function Values({ info, mapping, onChange }: { info: MappedInfo; mapping: Mapping; onChange: (m: Mapping) => void }) {
  const { t } = useTranslation()
  const column = mapping.columns[mapping.form === 'trade' ? 'side' : 'type']
  const words = column ? info.distinct[column] ?? [] : []
  const choices = mapping.form === 'trade' ? SIDES : KINDS
  if (!column) {
    // a list of one kind, e.g. a deposit history without a type column
    if (mapping.form === 'trade') return null
    return (
      <label className="grid grid-cols-[minmax(0,1fr)_10rem] items-center gap-2 text-sm">
        <span className={cx('text-xs', mapping.kind ? 'text-muted' : 'font-semibold text-down')}>{t('mapped.allRows')}</span>
        <select className={SELECT} value={mapping.kind ?? ''} onChange={(e) => onChange({ ...mapping, kind: e.target.value || null })}>
          <option value="">{t('mapped.choose')}</option>
          {KINDS.filter((k) => !['trade', 'ignore', 'convert', 'buy', 'sell'].includes(k)).map((c) => <option key={c} value={c}>{t(`mapped.kinds.${c}`)}</option>)}
        </select>
      </label>
    )
  }
  const set = (word: string, v: string) => {
    const values = { ...mapping.values }
    if (v) values[word] = v
    else delete values[word]
    onChange({ ...mapping, values })
  }
  return (
    <div className="grid gap-2">
      <span className="label">{t('mapped.valuesTitle', { column })}</span>
      {words.length === 0 && <p className="m-0 text-xs text-muted">{t('mapped.noWords')}</p>}
      <div className="grid gap-x-4 gap-y-1.5 sm:grid-cols-2">
        {words.map((w) => (
          <label key={w} className="grid grid-cols-[minmax(0,1fr)_10rem] items-center gap-2 text-sm">
            <span className={cx('truncate font-mono text-xs', !mapping.values[w] && 'font-semibold text-down')} title={w}>{w}</span>
            <select className={SELECT} value={mapping.values[w] ?? ''} onChange={(e) => set(w, e.target.value)}>
              <option value="">{t('mapped.choose')}</option>
              {choices.map((c) => <option key={c} value={c}>{t(`mapped.kinds.${c}`)}</option>)}
            </select>
          </label>
        ))}
      </div>
      {(Object.values(mapping.values).includes('income') || mapping.kind === 'income') && (
        <label className="grid grid-cols-[minmax(0,1fr)_10rem] items-center gap-2 text-sm">
          <span className="text-xs text-muted">{t('mapped.incomeKind')}</span>
          <select className={SELECT} value={mapping.income_kind}
            onChange={(e) => onChange({ ...mapping, income_kind: e.target.value as Mapping['income_kind'] })}>
            {(['reward', 'staking', 'interest', 'airdrop'] as const).map((k) => <option key={k} value={k}>{t(`mapped.income.${k}`)}</option>)}
          </select>
        </label>
      )}
    </div>
  )
}

function PreviewBox({ preview, tz, problem }: { preview: MappedPreview; tz: string; problem: (m: string) => string }) {
  const { t } = useTranslation()
  const side = ([asset, amount]: MappedSide) => (asset && amount ? `${quantity(amount)} ${asset}` : '')
  return (
    <div className="grid gap-3 border-t border-line pt-3">
      <dl className="m-0 grid grid-cols-3 gap-x-4 gap-y-2 text-sm sm:grid-cols-5">
        {(['read', 'new', 'duplicates', 'skipped', 'rejected'] as const).map((k) => (
          <div key={k} className="grid">
            <dt className="text-xs text-muted">{t(`mapped.count.${k}`)}</dt>
            <dd className={cx('num m-0 font-semibold', k === 'rejected' && preview.rejected > 0 && 'text-down', k === 'new' && 'text-up')}>{preview[k]}</dd>
          </div>
        ))}
      </dl>
      {preview.data_from && (
        <span className="text-xs text-muted">
          {t('pages.sources.period')}: {date(preview.data_from, tz)} – {date(preview.data_to, tz)}
          {preview.date_format && <> · {t('mapped.dateRead', { format: preview.date_format })}</>}
        </span>
      )}
      {preview.problems.length > 0 && (
        <div className="grid gap-1 rounded-ctl border border-down/40 p-2 text-xs">
          <b className="text-down">{t('mapped.problemsTitle', { count: preview.rejected })}</b>
          <ul className="m-0 max-h-40 overflow-auto pl-4">
            {preview.problems.map((p, i) => <li key={i}>{t('mapped.row', { row: p.row })}: {problem(p.message)}</li>)}
          </ul>
        </div>
      )}
      <div className="max-h-80 overflow-auto rounded-ctl bg-surface">
        <table className="w-full border-collapse text-xs">
          <thead className="sticky top-0 bg-surface text-left text-muted">
            <tr>{(['row', 'at', 'kind', 'incoming', 'outgoing', 'fee'] as const).map((h) => <th key={h} className="px-2 py-1 font-normal">{t(`mapped.cols.${h}`)}</th>)}</tr>
          </thead>
          <tbody>
            {preview.rows.map((r) => (
              <tr key={`${r.row}-${r.at}`} className={cx('border-t border-line/60', r.duplicate && 'text-muted')}>
                <td className="num px-2 py-1">{r.row}</td>
                <td className="whitespace-nowrap px-2 py-1">{dateTime(r.at, tz)}</td>
                <td className="px-2 py-1">{t(`kinds.${r.kind}`, { defaultValue: r.kind })}{r.duplicate && <> · {t('mapped.known')}</>}</td>
                <td className="num whitespace-nowrap px-2 py-1 text-up">{side(r.incoming)}</td>
                <td className="num whitespace-nowrap px-2 py-1 text-down">{side(r.outgoing)}</td>
                <td className="num whitespace-nowrap px-2 py-1 text-muted">{side(r.fee)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
