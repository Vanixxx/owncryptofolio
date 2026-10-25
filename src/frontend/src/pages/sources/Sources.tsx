import { Plus, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Button, Card, ErrorText, Field, PageHeader } from '../../components/ui'
import { useJobs } from '../../hooks/useJobs'
import { api, type BalanceEntry, type Provider, type Source, type SourceAlert, type Wallet } from '../../lib/api'
import { SourceAlerts } from '../../components/SourceAlerts'
import { sourceName } from '../../lib/txFilter'
import { cx } from '../../lib/cx'
import { useErrorText } from '../../lib/useErrorText'
import { SearchField } from '../../components/ui/SearchField'
import { matches } from '../../lib/search'
import { BetaBadge, BetaNote, tested } from '../../components/Beta'
import { SourceCard } from './SourceCard'
import { WalletCard } from './WalletCard'
import { SourceChanges } from './SourceChanges'
import { useSettings } from '../../app/settings'
import { SourceLogo } from '../../components/SourceLogo'

export function Sources() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [providers, setProviders] = useState<Provider[]>([])
  const [sources, setSources] = useState<Source[] | null>(null)
  const [wallets, setWallets] = useState<Wallet[]>([])
  const [balances, setBalances] = useState<BalanceEntry[]>([])
  const [alerts, setAlerts] = useState<SourceAlert[]>([])
  const [adding, setAdding] = useState<'exchange' | 'wallet' | null>(null)
  const [error, setError] = useState<unknown>(null)
  const tz = useSettings().settings['general.timezone']

  const load = useCallback(
    () => Promise.all([api.sources(), api.wallets(), api.balances(), api.sourceAlerts()])
      .then(([s, w, b, a]) => { setSources(s); setWallets(w); setBalances(b); setAlerts(a) }, setError),
    [],
  )
  const { jobs, refresh: refreshJobs } = useJobs(load)
  useEffect(() => {
    void load()
    api.plugins().then((p) => setProviders(p.providers), setError)
  }, [load])
  const exchanges = sources?.filter((s) => s.kind === 'exchange') ?? []
  const done = () => { setAdding(null); void load() }
  const busy = (id: number) => jobs.some((j) => j.source_id === id && (j.status === 'queued' || j.status === 'running'))
  // everything that can be fetched: wallet networks, and exchanges with an API key
  const fetchable = (sources ?? []).filter((s) => {
    const channels = providers.find((p) => p.provider === s.provider)?.channels.map((c) => c.channel) ?? []
    return channels.includes('chain') || (channels.includes('api') && s.credentials.length > 0)
  })
  const fetchAll = () =>
    Promise.all(fetchable.filter((s) => !busy(s.id)).map((s) => api.startJob('fetch', s.id)))
      .then(() => { setError(null); refreshJobs() }, setError)

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageHeader title={t('pages.sources.title')} subtitle={t('pages.sources.subtitle')} />
        {fetchable.length > 0 && (
          <Button onClick={() => void fetchAll()} disabled={fetchable.every((s) => busy(s.id))}>
            <RefreshCw size={16} aria-hidden="true" className={fetchable.some((s) => busy(s.id)) ? 'animate-spin' : ''} />
            {t('pages.sources.fetchEverything', { count: fetchable.length })}
          </Button>
        )}
      </div>
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
      <SourceAlerts alerts={alerts} name={sourceName(sources ?? [], wallets)} busy={busy}
        onFetch={(id) => void api.startJob('fetch', id).then(() => { setError(null); refreshJobs() }, setError)} />
      <SourceChanges name={sourceName(sources ?? [], wallets)} tz={tz} onDecided={() => void load()} />

      <section className="grid gap-4 md:gap-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="m-0 text-lg font-semibold">{t('pages.sources.exchanges')}</h2>
          {adding !== 'exchange' && (
            <Button variant="ghost" onClick={() => setAdding('exchange')}><Plus size={16} aria-hidden="true" />{t('pages.sources.addExchange')}</Button>
          )}
        </div>
        {adding === 'exchange' && (
          <AddExchange providers={providers.filter((p) => p.kind === 'exchange')} onCancel={() => setAdding(null)} onCreated={done} />
        )}
        {sources && exchanges.length === 0 && adding !== 'exchange' && (
          <p className="m-0 text-sm text-muted">{t('pages.sources.noExchanges')}</p>
        )}
        {exchanges.map((s) => (
          <SourceCard key={s.id} source={s} provider={providers.find((p) => p.provider === s.provider)}
            balance={balances.find((b) => b.source_id === s.id)}
            jobs={jobs.filter((j) => j.source_id === s.id)} onChanged={load} onJobStarted={refreshJobs} />
        ))}
      </section>

      <section className="grid gap-4 md:gap-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="m-0 text-lg font-semibold">{t('pages.sources.wallets')}</h2>
          {adding !== 'wallet' && (
            <Button variant="ghost" onClick={() => setAdding('wallet')}><Plus size={16} aria-hidden="true" />{t('pages.sources.addWallet')}</Button>
          )}
        </div>
        {adding === 'wallet' && <AddWallet onCancel={() => setAdding(null)} onCreated={done} />}
        {sources && wallets.length === 0 && adding !== 'wallet' && (
          <p className="m-0 text-sm text-muted">{t('pages.sources.noWallets')}</p>
        )}
        {wallets.map((w) => (
          <WalletCard key={w.id} wallet={w} networks={sources?.filter((s) => s.wallet_id === w.id) ?? []}
            providers={providers} jobs={jobs} balances={balances} onChanged={load} onJobStarted={refreshJobs} />
        ))}
      </section>
    </>
  )
}

function AddExchange({ providers, onCancel, onCreated }: {
  providers: Provider[]; onCancel: () => void; onCreated: () => void
}) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [provider, setProvider] = useState<Provider | null>(null)
  const [label, setLabel] = useState('')
  const [error, setError] = useState<unknown>(null)

  const [query, setQuery] = useState('')
  // the tested ones and the one without connection; every other exchange through the
  // search (Vanixxx, 2026-10-18: ccxt brings dozens)
  const shown = query.trim()
    ? providers.filter((p) => matches(query, p.name, t(`pages.sources.providerNames.${p.provider}`, { defaultValue: p.name })))
    : providers.filter((p) => tested(p)).sort((a, b) => Number(a.provider === 'manual') - Number(b.provider === 'manual'))
  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!provider) return
    try {
      await api.createSource(provider.provider, label)
      onCreated()
    } catch (err) {
      setError(err)
    }
  }
  return (
    <Card title={t('pages.sources.addExchange')}>
      <form onSubmit={submit} className="grid gap-4">
        <span className="label">{t('pages.sources.provider')}</span>
        <SearchField value={query} onChange={setQuery} placeholder={t('pages.sources.searchExchange')} />
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {shown.map((p) => (
            <button key={p.provider} type="button" aria-pressed={provider?.provider === p.provider}
              onClick={() => { setProvider(p); setLabel(p.provider === 'manual' ? '' : p.name) }}
              className={cx('rounded-ctl border p-3 text-left text-sm font-semibold',
                provider?.provider === p.provider ? 'border-accent ring-2 ring-accent' : 'border-line bg-surface-2')}>
              <span className="flex items-center gap-2"><SourceLogo source={{ provider: p.provider, label: p.name, kind: 'exchange' }} size={20} />
                <span className="min-w-0 truncate">{t(`pages.sources.providerNames.${p.provider}`, { defaultValue: p.name })}</span>
                {!tested(p) && <BetaBadge provider={p} className="ml-auto" />}</span>
            </button>
          ))}
          {shown.length === 0 && <p className="col-span-full m-0 text-sm text-muted">{t('common.noMatch')}</p>}
        </div>
        {!query.trim() && <p className="m-0 text-xs text-muted">{t('pages.sources.moreBySearch', { count: providers.length - shown.length })}</p>}
        <BetaNote provider={provider} />
        {provider?.provider === 'manual' && <p className="m-0 text-sm leading-relaxed text-muted">{t('manual.exchangeHint')}</p>}
        {provider && (
          <Field id="source-label" label={provider.provider === 'manual' ? t('manual.exchangeName') : t('pages.sources.label')}
            placeholder={provider.provider === 'manual' ? t('manual.exchangeNamePlaceholder') : t('pages.sources.labelPlaceholder')}
            value={label} onChange={(e) => setLabel(e.target.value)} required />
        )}
        <ErrorText>{error ? errorText(error) : null}</ErrorText>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={!provider}>{t('pages.sources.create')}</Button>
          <Button type="button" variant="ghost" onClick={onCancel}>{t('common.cancel')}</Button>
        </div>
      </form>
    </Card>
  )
}

function AddWallet({ onCancel, onCreated }: { onCancel: () => void; onCreated: () => void }) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [name, setName] = useState('')
  const [error, setError] = useState<unknown>(null)
  async function submit(e: FormEvent) {
    e.preventDefault()
    try {
      await api.createWallet(name)
      onCreated()
    } catch (err) {
      setError(err)
    }
  }
  return (
    <Card title={t('pages.sources.addWallet')}>
      <form onSubmit={submit} className="grid gap-4">
        <p className="m-0 text-sm leading-relaxed text-muted">{t('pages.sources.walletHint')}</p>
        <Field id="wallet-name" label={t('pages.sources.walletName')} placeholder={t('pages.sources.walletNamePlaceholder')}
          value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
        <ErrorText>{error ? errorText(error) : null}</ErrorText>
        <div className="flex flex-wrap gap-2">
          <Button type="submit">{t('pages.sources.create')}</Button>
          <Button type="button" variant="ghost" onClick={onCancel}>{t('common.cancel')}</Button>
        </div>
      </form>
    </Card>
  )
}
