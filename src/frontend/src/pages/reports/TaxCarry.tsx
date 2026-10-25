import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button, Card, ErrorText, Row } from '../../components/ui'
import { api, type TaxCarryRow } from '../../lib/api'
import { money } from '../../lib/format'
import { useErrorText } from '../../lib/useErrorText'

const some = (v: string | null) => v !== null && Number(v) !== 0

/** The loss carry of § 23 (ADR 0045): computed as a proposal, the tax office's figure from
 * the Feststellungsbescheid wins. Losses and carries are shown as positive amounts. */
export function TaxCarry({ year, rows, opening, onChanged }: {
  year: number; rows: TaxCarryRow[]; opening: { year: number; amount: string; note: string | null } | null; onChanged: () => void
}) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [edit, setEdit] = useState<number | null>(null)
  const [amount, setAmount] = useState('')
  const [note, setNote] = useState('')
  const [all, setAll] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const c = rows.find((r) => r.year === year)
  const before = rows.length > 0 && rows[0].year === year ? year - 1 : null
  const open = (y: number, r?: { assessed: string | null; note: string | null }) => { setEdit(y); setAmount(r?.assessed ?? ''); setNote(r?.note ?? ''); setError(null) }
  const known = edit === null ? false : edit === before ? opening !== null : rows.find((r) => r.year === edit)?.assessed != null
  const save = (value: string | null) => {
    if (edit === null) return
    api.taxSetCarry(edit, value, note).then(() => { setEdit(null); onChanged() }, setError)
  }
  const eur = (v: string | null) => <span className="num">{money(v)}</span>

  return (
    <Card title={t('tax.carry.title')}>
      {!c ? <p className="m-0 text-sm text-muted">{t('tax.carry.none')}</p> : (
        <>
          <div className="grid gap-0.5">
            <span className="label">{t(c.assessed !== null ? 'tax.carry.endAssessed' : 'tax.carry.end')}</span>
            <span className="num text-2xl font-semibold">{money(c.assessed ?? c.end)}</span>
          </div>
          <div className="grid gap-1.5 text-sm">
            <Row label={t('tax.carry.start')}>{eur(c.start)}</Row>
            {some(c.used) && <Row label={t('tax.carry.used')}>{eur(c.used)}</Row>}
            {some(c.back_in) && <Row label={t('tax.carry.backIn')}>{eur(c.back_in)}</Row>}
            {some(c.back_out) && <Row label={t('tax.carry.backOut')}>{eur(c.back_out)}</Row>}
            {some(c.loss) && <Row label={t('tax.carry.loss')}>{eur(c.loss)}</Row>}
            {c.taxable && <Row label={t('tax.carry.remaining')}>{eur(c.remaining)}</Row>}
            {c.assessed !== null && <Row label={t('tax.carry.computed')}>{eur(c.end)}</Row>}
            {c.diff !== null && some(c.diff) && <Row label={t('tax.carry.diff')}><span className="num text-warn">{money(c.diff, 'EUR', true)}</span></Row>}
          </div>
          {c.note && <p className="m-0 text-xs text-muted">{t('tax.carry.noteLabel')}: {c.note}</p>}
          {before !== null && opening && <p className="m-0 text-xs text-muted">{t('tax.carry.opening', { year: opening.year, amount: money(opening.amount) })}{opening.note ? ` · ${opening.note}` : ''}</p>}
          <p className="m-0 text-xs leading-relaxed text-muted">{t(c.running ? 'tax.carry.hintRunning' : 'tax.carry.hint')}</p>
        </>
      )}

      {edit !== null ? (
        <form className="grid gap-2" onSubmit={(e) => { e.preventDefault(); save(amount.trim() ? amount.trim().replace(',', '.') : null) }}>
          <span className="text-sm font-medium">{t(edit === before ? 'tax.carry.formBefore' : 'tax.carry.formYear', { year: edit })}</span>
          <label className="grid gap-1.5 text-sm">
            <span className="label">{t('tax.carry.amount')}</span>
            <input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} required
              className="num rounded-ctl border border-line bg-surface-2 px-3 py-2 text-base text-fg" />
          </label>
          <label className="grid gap-1.5 text-sm">
            <span className="label">{t('tax.carry.noteLabel')}</span>
            <input value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} placeholder={t('tax.carry.notePlaceholder')}
              className="rounded-ctl border border-line bg-surface-2 px-3 py-2 text-base text-fg" />
          </label>
          <ErrorText>{error ? errorText(error) : null}</ErrorText>
          <div className="flex flex-wrap gap-2">
            <Button type="submit">{t('common.save')}</Button>
            {known && (
              <Button type="button" variant="ghost" onClick={() => save(null)}>{t('tax.carry.remove')}</Button>
            )}
            <Button type="button" variant="ghost" onClick={() => setEdit(null)}>{t('common.cancel')}</Button>
          </div>
        </form>
      ) : (
        <div className="flex flex-wrap gap-2">
          {c && !c.running && <Button variant="ghost" onClick={() => open(year, c)}>{t(c.assessed !== null ? 'tax.carry.editAssessed' : 'tax.carry.addAssessed')}</Button>}
          {before !== null && <Button variant="ghost" onClick={() => open(before, opening ? { assessed: opening.amount, note: opening.note } : undefined)}>{t(opening ? 'tax.carry.editBefore' : 'tax.carry.addBefore')}</Button>}
          {rows.length > 1 && <Button variant="ghost" aria-expanded={all} onClick={() => setAll(!all)}>{t('tax.carry.all')}</Button>}
        </div>
      )}

      {all && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse whitespace-nowrap text-xs">
            <thead>
              <tr className="border-b border-line text-left text-muted">
                <th className="py-1.5 pr-2 font-normal">{t('tax.year')}</th>
                <th className="py-1.5 pr-2 text-right font-normal">{t('tax.net')}</th>
                <th className="py-1.5 pr-2 text-right font-normal">{t('tax.carry.colStart')}</th>
                <th className="py-1.5 pr-2 text-right font-normal">{t('tax.carry.colChange')}</th>
                <th className="py-1.5 text-right font-normal">{t('tax.carry.colEnd')}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const change = Number(r.loss) - Number(r.used)
                return (
                  <tr key={r.year} className={r.year === year ? 'font-semibold' : ''}>
                    <td className="num py-1 pr-2">{r.year}{r.running && ' *'}</td>
                    <td className="num py-1 pr-2 text-right">{money(r.net, 'EUR', true)}</td>
                    <td className="num py-1 pr-2 text-right">{money(r.start)}</td>
                    <td className="num py-1 pr-2 text-right">{change ? money(String(change), 'EUR', true) : '—'}</td>
                    <td className="num py-1 text-right">{money(r.assessed ?? r.end)}{r.assessed !== null && ' §'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <p className="m-0 mt-1.5 text-xs text-muted">{t('tax.carry.legend')}</p>
        </div>
      )}
    </Card>
  )
}
