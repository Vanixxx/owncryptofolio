import { RefreshCw } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useSettings } from '../../app/settings'
import { Button, ErrorText, Field, StatusPill } from '../../components/ui'
import { Confirm } from '../../components/ui/Confirm'
import { Toggle } from '../../components/ui/Toggle'
import { SearchField } from '../../components/ui/SearchField'
import { SourceLogo, WalletLogo } from '../../components/SourceLogo'
import { BetaBadge, BetaNote } from '../../components/Beta'
import { cx } from '../../lib/cx'
import { matches } from '../../lib/search'
import { api, type BalanceEntry, type Job, type Provider, type Source, type Wallet } from '../../lib/api'
import { dateTime, shortAddress } from '../../lib/format'
import { useErrorText, useMessageText } from '../../lib/useErrorText'
import { BalanceBadge, BalanceTable } from './Balance'
import { CollapsibleCard, Fold } from './CollapsibleCard'
import { Runs } from './Runs'
import { LogoUpload } from '../../components/LogoUpload'

const MANUAL = 'manual_network'

/** A wallet (device or app) with its networks underneath (ADR 0034). */
export function WalletCard({ wallet, networks, providers, jobs, balances, onChanged, onJobStarted }: {
  wallet: Wallet; networks: Source[]; providers: Provider[]; jobs: Job[]; balances: BalanceEntry[]
  onChanged: () => void; onJobStarted: () => void
}) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [adding, setAdding] = useState(false)
  const [renaming, setRenaming] = useState(false)
  const [name, setName] = useState(wallet.name)
  const [error, setError] = useState<unknown>(null)
  const tz = useSettings().settings['general.timezone']
  const rows = networks.reduce((n, s) => n + s.rows, 0)
  const last = networks.map((n) => n.last_fetch).filter((x): x is string => !!x).sort().at(-1)
  const busy = (id: number) => jobs.some((j) => j.source_id === id && (j.status === 'queued' || j.status === 'running'))
  const anyBusy = networks.some((n) => busy(n.id))
  // the wallet as a whole: checked if any network is, differences summed
  const mine = balances.filter((b) => networks.some((n) => n.id === b.source_id))
  const overall: BalanceEntry | undefined = mine.some((b) => b.checked)
    ? { source_id: wallet.id, checked: true, at: null, items: [],
        status: mine.some((b) => b.status === 'diff') ? 'diff' : 'ok', differences: mine.reduce((n, b) => n + b.differences, 0),
        unchecked: mine.reduce((n, b) => n + b.unchecked, 0) }
    : undefined

  // a network kept by hand has nothing to fetch (Vanixxx, 2026-10-11)
  const byHand = (n: Source) => n.provider === MANUAL
  const fetchAll = () =>
    Promise.all(networks.filter((n) => !busy(n.id) && !byHand(n)).map((n) => api.startJob('fetch', n.id)))
      .then(() => { setError(null); onJobStarted() }, setError)
  const rename = (e: FormEvent) => {
    e.preventDefault()
    api.renameWallet(wallet.id, name).then(() => { setRenaming(false); onChanged() }, setError)
  }

  return (
    <CollapsibleCard
      storageKey={`wallet-open-${wallet.id}`}
      title={
        <span className="flex items-center gap-2">
          <WalletLogo name={wallet.name} id={wallet.id} size={22} />{wallet.name}
        </span>
      }
      meta={<>{t('pages.sources.networks', { count: networks.length })} · {t('pages.sources.rows', { count: rows })}</>}
      summary={networks.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="basis-full"><BalanceBadge entry={overall} /></span>
          <span className="text-xs text-muted">
            {anyBusy ? t('pages.sources.jobRunning') : last ? t('pages.sources.lastFetch', { at: dateTime(last, tz) }) : t('pages.sources.neverFetched')}
          </span>
          <Button variant="ghost" onClick={() => void fetchAll()} disabled={networks.every((n) => busy(n.id) || byHand(n))}>
            <RefreshCw size={16} aria-hidden="true" className={anyBusy ? 'animate-spin' : ''} />{t('pages.sources.fetchAll')}
          </Button>
        </div>
      )}
    >
      {renaming && (
        <form onSubmit={rename} className="flex flex-wrap items-end gap-2">
          <div className="min-w-0 flex-1"><Field id={`wallet-name-${wallet.id}`} label={t('pages.sources.walletName')}
            value={name} onChange={(e) => setName(e.target.value)} required /></div>
          <Button type="submit">{t('common.save')}</Button>
          <Button type="button" variant="ghost" onClick={() => setRenaming(false)}>{t('common.cancel')}</Button>
        </form>
      )}

      {networks.length === 0 && <p className="m-0 text-sm text-muted">{t('pages.sources.noNetworks')}</p>}
      {/* the balance first, as with exchanges (Vanixxx, 2026-10-07): per network with its logo;
          balance and networks: two parts that fold alike, no line above (Vanixxx, 2026-10-10) */}
      {mine.some((b) => b.items.length > 0) && (
        <Fold storageKey={`wallet-balance-open-${wallet.id}`} defaultOpen line={false} className="pt-3"
          title={<span className="label">{t('balances.title')}</span>}>
          <div className="grid gap-2 pl-6">
            {networks.map((n) => {
              const b = balances.find((x) => x.source_id === n.id)
              // each network folds to its line with the state (Vanixxx, 2026-10-10)
              return b && b.items.length > 0 ? (
                <Fold key={n.id} storageKey={`balance-open-${n.id}`} side={<BalanceBadge entry={b} />} className="first:border-t-0 first:pt-0"
                  title={<span className="flex items-center gap-2 text-sm font-semibold"><SourceLogo source={n} size={18} />
                    {byHand(n) ? n.label : providers.find((p) => p.provider === n.provider)?.name ?? n.provider}</span>}>
                  <BalanceTable entry={b} sourceId={n.id} manual={false} onChanged={onChanged} />
                </Fold>
              ) : null
            })}
          </div>
        </Fold>
      )}
      {/* the networks with their addresses fold away all at once (Vanixxx, 2026-10-10) */}
      {networks.length > 0 && (
        <Fold storageKey={`networks-open-${wallet.id}`} line={false} className="pt-3"
          title={<span className="label">{t('pages.sources.networks', { count: networks.length })}</span>}>
          <ul className="m-0 grid list-none p-0">
            {networks.map((n) => (
              <Network key={n.id} source={n} provider={providers.find((p) => p.provider === n.provider)}
                balance={balances.find((b) => b.source_id === n.id)}
                job={jobs.find((j) => j.source_id === n.id)} onChanged={onChanged} onJobStarted={onJobStarted} />
            ))}
          </ul>
        </Fold>
      )}

      {adding ? (
        <AddNetwork wallet={wallet} networks={networks} providers={providers.filter((p) => p.kind === 'wallet')}
          onDone={() => { setAdding(false); onChanged() }} onCancel={() => setAdding(false)} />
      ) : (
        <div className="flex flex-wrap gap-2 border-t border-line pt-3">
          <Button variant="ghost" onClick={() => setAdding(true)}>{t('pages.sources.addNetwork')}</Button>
        </div>
      )}

      <ErrorText>{error ? errorText(error) : null}</ErrorText>
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
        {!renaming ? (
          <span className="flex flex-wrap gap-2">
            <Button variant="ghost" onClick={() => setRenaming(true)}>{t('pages.sources.rename')}</Button>
            <LogoUpload kind="wallet" id={wallet.id} />
          </span>
        ) : <span />}
        {networks.length > 0 ? (
          <span className="text-xs text-muted">{t('pages.sources.deleteWalletBlocked')}</span>
        ) : (
          <Confirm label={t('pages.sources.deleteWallet')} question={t('pages.sources.deleteWalletConfirm', { name: wallet.name })}
            onConfirm={() => api.deleteWallet(wallet.id).then(onChanged, setError)} />
        )}
      </div>
    </CollapsibleCard>
  )
}

function Network({ source, provider, balance, job, onChanged, onJobStarted }: {
  source: Source; provider?: Provider; balance?: BalanceEntry; job?: Job; onChanged: () => void; onJobStarted: () => void
}) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const messageText = useMessageText()
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const busy = job && (job.status === 'queued' || job.status === 'running')
  const manual = source.provider === MANUAL
  const name = manual ? source.label : provider?.name ?? source.provider

  return (
    <li className="grid gap-2 border-t border-line py-3 first:border-t-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)] items-center gap-x-2.5">
          <SourceLogo source={source} size={24} className="row-span-2" />
          <b className="flex items-center gap-1.5 text-sm">{name}<BetaBadge provider={provider} /></b>
          {manual
            ? <span className="truncate text-xs text-muted">{t('pages.sources.byHand')}{source.address && <> · <code className="font-mono">{shortAddress(source.address)}</code></>}</span>
            : <code className="truncate font-mono text-xs text-muted" title={source.address ?? ''}>{shortAddress(source.address)}</code>}
        </div>
        <div className="flex items-center gap-2">
          <BalanceBadge entry={balance} />
          <span className="num text-xs text-muted">{t('pages.sources.rows', { count: source.rows })}</span>
          {!manual && <Button variant="ghost" aria-label={`${t('pages.sources.fetch')} ${name}`} disabled={!!busy}
            onClick={() => api.startJob('fetch', source.id).then(() => { setError(null); onJobStarted() }, setError)}>
            <RefreshCw size={16} aria-hidden="true" className={busy ? 'animate-spin' : ''} />
          </Button>}
        </div>
      </div>
      {job && <JobStatus job={job} />}
      {job?.status === 'failed' && job.message && <ErrorText>{messageText(job.message)}</ErrorText>}
      {manual
        ? <p className="m-0 text-xs text-muted">{t('pages.sources.byHandHint')}</p>
        : <Toggle id={`auto-${source.id}`} label={t('pages.sources.autoFetch')} checked={source.auto_fetch}
            onChange={(v) => void api.setAutoFetch(source.id, v).then(onChanged, setError)} />}
      <div className="flex flex-wrap items-center gap-2">
        {source.runs.length > 0 && (
          <Button variant="ghost" onClick={() => setOpen(!open)}>
            {open ? t('pages.sources.hideImports') : `${t('pages.sources.showImports')} (${source.runs.length})`}
          </Button>
        )}
        {source.runs.length === 0 && (
          <Confirm label={t('pages.sources.removeNetwork')} question={t('pages.sources.removeNetworkConfirm', { network: name })}
            onConfirm={() => api.deleteSource(source.id).then(onChanged, setError)} />
        )}
      </div>
      {open && <Runs source={source} onChanged={onChanged} />}
      {open && <LogoUpload kind="source" id={source.id} />}
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
    </li>
  )
}

function JobStatus({ job }: { job: Job }) {
  const { t } = useTranslation()
  if (job.status === 'queued') return <span className="text-xs text-muted">{t('pages.sources.jobQueued')}</span>
  if (job.status === 'running') return <span className="text-xs text-muted">{t('pages.sources.jobRunning')}</span>
  if (job.status === 'failed') return <StatusPill ok={false}>{t('pages.sources.jobFailed')}</StatusPill>
  return <StatusPill ok>{t('pages.sources.jobDone', { added: job.result.added ?? 0, duplicates: job.result.duplicates ?? 0 })}</StatusPill>
}

function AddNetwork({ wallet, networks, providers, onDone, onCancel }: {
  wallet: Wallet; networks: Source[]; providers: Provider[]; onDone: () => void; onCancel: () => void
}) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [provider, setProvider] = useState<Provider | null>(null)
  const [address, setAddress] = useState('')
  const [suggestedFrom, setSuggestedFrom] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [query, setQuery] = useState('')
  const shown = providers.filter((p) => matches(query, p.name, p.native_asset))

  const [label, setLabel] = useState('')
  const manual = provider?.provider === MANUAL

  function choose(p: Provider) {
    setProvider(p)
    // EVM networks share one address: suggest the one already in this wallet.
    const evm = p.family === 'evm'
      ? networks.find((n) => providers.find((q) => q.provider === n.provider)?.family === 'evm')
      : undefined
    setAddress(evm?.address ?? '')
    setSuggestedFrom(evm ? providers.find((q) => q.provider === evm.provider)?.name ?? evm.provider : null)
  }
  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!provider) return
    try {
      await api.createSource(provider.provider, manual ? label : provider.name, address || undefined, wallet.id)
      onDone()
    } catch (err) {
      setError(err)
    }
  }
  return (
    <form onSubmit={submit} className="grid gap-3 rounded-ctl bg-surface-2 p-3">
      <span className="label">{t('pages.sources.network')}</span>
      <SearchField value={query} onChange={setQuery} placeholder={t('pages.sources.searchNetwork')} />
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {shown.map((p) => (
          <button key={p.provider} type="button" aria-pressed={provider?.provider === p.provider} onClick={() => choose(p)}
            className={cx('flex items-center gap-2 rounded-ctl border p-2.5 text-left text-sm',
              provider?.provider === p.provider ? 'border-accent ring-2 ring-accent' : 'border-line bg-surface')}>
            <SourceLogo source={{ provider: p.provider, label: p.name, kind: 'wallet' }} size={20} />
            <span className="truncate">{t(`pages.sources.providerNames.${p.provider}`, { defaultValue: p.name })}</span>
            <BetaBadge provider={p} className="ml-auto" />
          </button>
        ))}
        {shown.length === 0 && <p className="col-span-full m-0 text-sm text-muted">{t('common.noMatch')}</p>}
      </div>
      <BetaNote provider={provider} />
      {manual && (
        // a chain without plugin: named freely, the address only as a note (Vanixxx, 2026-10-11)
        <>
          <p className="m-0 text-xs leading-relaxed text-muted">{t('pages.sources.byHandHint')}</p>
          <Field id={`network-name-${wallet.id}`} label={t('pages.sources.networkName')} value={label} required
            onChange={(e) => setLabel(e.target.value)} placeholder="Optimism" />
          <Field id={`network-address-${wallet.id}`} label={`${t('pages.sources.address')} (${t('manual.optional')})`} value={address}
            onChange={(e) => setAddress(e.target.value.trim())} className="font-mono" autoComplete="off" spellCheck={false} />
        </>
      )}
      {provider && !manual && (
        <>
          <Field id={`network-address-${wallet.id}`} label={t('pages.sources.address')} value={address} required
            onChange={(e) => { setAddress(e.target.value.trim()); setSuggestedFrom(null) }}
            className="font-mono" autoComplete="off" spellCheck={false} />
          {suggestedFrom && <p className="m-0 text-xs text-muted">{t('pages.sources.evmSuggested', { network: suggestedFrom })}</p>}
        </>
      )}
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={!provider}>{t('pages.sources.create')}</Button>
        <Button type="button" variant="ghost" onClick={onCancel}>{t('common.cancel')}</Button>
      </div>
    </form>
  )
}
