import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'
import { PageHeader, Segmented } from '../components/ui'
import { Origin } from './reports/Origin'
import { CurrencySwitch } from '../components/CurrencySwitch'
import { Tax } from './reports/Tax'

/** Reports: the tax report and the source of funds (ADR 0046); the view sits in the URL so a
 * transaction can link straight to its source of funds. */
export function Reports() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const view = params.get('view') === 'origin' ? 'origin' : 'tax'
  const pick = (v: 'tax' | 'origin') => setParams(v === 'tax' ? {} : { view: v }, { replace: true })
  return (
    <>
      <PageHeader title={t('pages.reports.title')} subtitle={t('pages.reports.subtitle')} aside={<CurrencySwitch />} />
      <div className="mb-4">
        <Segmented label={t('pages.reports.view')} value={view} onChange={pick}
          options={[{ value: 'tax', label: t('pages.reports.tax') }, { value: 'origin', label: t('pages.reports.origin') }]} />
      </div>
      {view === 'origin' ? <Origin /> : <Tax />}
    </>
  )
}
