import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router'
import { useSettings } from '../../app/settings'
import { ErrorText, PageHeader, Segmented } from '../../components/ui'
import { api, type Holding, type PortfolioSummary, type Source, type Wallet } from '../../lib/api'
import { sourceLookup, sourceName } from '../../lib/txFilter'
import { useErrorText } from '../../lib/useErrorText'
import { FuturesList } from './FuturesList'
import { GapList } from './GapList'
import { CurrencySwitch } from '../../components/CurrencySwitch'
import { SpotList } from './SpotList'

type Tab = 'spot' | 'futures' | 'gaps'

/** Holdings (ADR 0040): coins with cost and P/L, futures positions, and where data is
 * missing. The tab lives in the URL, so the dashboard can link straight to the gaps. */
export function Holdings() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const tz = useSettings().settings['general.timezone']
  const [params, setParams] = useSearchParams()
  const tab = (['spot', 'futures', 'gaps'].includes(params.get('tab') ?? '') ? params.get('tab') : 'spot') as Tab
  const [data, setData] = useState<{ summary: PortfolioSummary; items: Holding[] } | null>(null)
  const [sources, setSources] = useState<Source[]>([])
  const [wallets, setWallets] = useState<Wallet[]>([])
  const [error, setError] = useState<unknown>(null)
  useEffect(() => {
    api.portfolio().then(setData, setError)
    api.sources().then(setSources, setError)
    api.wallets().then(setWallets, setError)
  }, [])
  const name = sourceName(sources, wallets)
  const lookup = sourceLookup(sources, wallets)

  return (
    <>
      <PageHeader title={t('pages.holdings.title')} subtitle={t('pages.holdings.subtitle')} aside={<CurrencySwitch />} />
      <Segmented label={t('pages.holdings.title')} value={tab} onChange={(v) => setParams(v === 'spot' ? {} : { tab: v }, { replace: true })}
        options={[
          { value: 'spot', label: t('pages.holdings.spot') },
          { value: 'futures', label: t('pages.holdings.futures') },
          { value: 'gaps', label: t('holdings.gaps.tab') },
        ]} />
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
      {data === null ? (
        <p className="text-sm text-muted">{t('common.loading')}</p>
      ) : tab === 'spot' ? (
        <SpotList summary={data.summary} items={data.items} name={name} lookup={lookup} tz={tz} />
      ) : tab === 'futures' ? (
        <FuturesList summary={data.summary} name={name} tz={tz} />
      ) : (
        <GapList name={name} tz={tz} currency={data.summary.currency} />
      )}
    </>
  )
}
