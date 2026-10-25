import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSettings } from '../../app/settings'
import { Card, ErrorText, Segmented } from '../../components/ui'
import { Toggle } from '../../components/ui/Toggle'
import { useErrorText } from '../../lib/useErrorText'

/** The tax rules that are a choice (ADR 0042): the method and airdrops. The limits are law
 * and stand in the report. Below, the head of the reports. */
export function TaxCard() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const { settings, update } = useSettings()
  const [error, setError] = useState<unknown>(null)
  const set = (c: Parameters<typeof update>[0]) => update(c).then(() => setError(null), setError)
  return (
    <Card fold="settings-open-tax" title={t('settings.tax.title')}>
      <p className="m-0 text-sm leading-relaxed text-muted">{t('settings.tax.text')}</p>
      <div className="grid gap-1.5">
        <span className="label">{t('settings.tax.method')}</span>
        <Segmented label={t('settings.tax.method')} value={settings['tax.method']}
          onChange={(v) => void set({ 'tax.method': v })}
          options={[{ value: 'fifo', label: t('settings.tax.fifo') }, { value: 'lifo', label: t('settings.tax.lifo') }]} />
      </div>
      <Toggle id="tax-airdrop" label={t('settings.tax.airdrop')} checked={settings['tax.airdrop_taxable']}
        onChange={(v) => void set({ 'tax.airdrop_taxable': v })} />
      {/* head of the reports (ADR 0046): optional; the tax number only on the tax report */}
      <div className="grid gap-1.5">
        <span className="label">{t('settings.tax.holder')}</span>
        <p className="m-0 text-xs text-muted">{t('settings.tax.holderHint')}</p>
        {/* a small label over each field: once filled in, the placeholder is gone (Vanixxx, 2026-10-24) */}
        {([['report.name', 'name', 120], ['report.address', 'address', 300], ['report.tax_number', 'taxNumber', 40]] as const).map(([key, label, max]) => {
          const field = {
            id: `tax-${label}`, placeholder: t(`settings.tax.${label}`), defaultValue: settings[key], maxLength: max,
            onBlur: (e: { target: { value: string } }) => { if (e.target.value !== settings[key]) void set({ [key]: e.target.value }) },
            className: 'rounded-ctl border border-line bg-surface-2 px-3 py-2 text-base text-fg',
          }
          return (
            <div key={key} className="grid gap-1">
              <label htmlFor={field.id} className="text-xs text-muted">{t(`settings.tax.${label}`)}</label>
              {key === 'report.address' ? <textarea rows={2} {...field} /> : <input {...field} />}
            </div>
          )
        })}
      </div>
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
    </Card>
  )
}
