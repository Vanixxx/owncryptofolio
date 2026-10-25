import { CheckCircle2, CircleAlert, KeyRound, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSettings } from '../../app/settings'
import { Button, ErrorText, StatusPill } from '../../components/ui'
import { Confirm } from '../../components/ui/Confirm'
import { Toggle } from '../../components/ui/Toggle'
import { api, type BalanceEntry, type Job, type Provider, type Source } from '../../lib/api'
import { date, dateTime, shortAddress } from '../../lib/format'
import { useErrorText, useMessageText } from '../../lib/useErrorText'
import { ApiAccess } from './ApiAccess'
import { BalanceBadge, BalanceTable } from './Balance'
import { FileImport } from './FileImport'
import { CollapsibleCard, Fold } from './CollapsibleCard'
import { SourceLogo } from '../../components/SourceLogo'
import { LogoUpload } from '../../components/LogoUpload'
import { Runs } from './Runs'
import { BetaBadge, BetaNote, BetaTag } from '../../components/Beta'
import { MappedImport } from './MappedImport'

export function SourceCard({ source, provider, balance, jobs, onChanged, onJobStarted }: {
  source: Source; provider?: Provider; balance?: BalanceEntry; jobs: Job[]; onChanged: () => void; onJobStarted: () => void
}) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const messageText = useMessageText()
  const tz = useSettings().settings['general.timezone']
  const [error, setError] = useState<unknown>(null)
  const channels = new Set(provider?.channels.map((c) => c.channel))
  const fetchable = channels.has('chain') || (channels.has('api') && source.credentials.length > 0)
  const job = jobs[0]
  const busy = job && (job.status === 'queued' || job.status === 'running')

  const startFetch = () =>
    api.startJob('fetch', source.id).then(() => { setError(null); onJobStarted() }, setError)

  // what goes wrong shows on the folded "fetching and import" too (Vanixxx, 2026-10-10)
  const trouble = channels.has('api') && source.last_check?.ok === false ? 'pages.sources.checkFailed'
    : job?.status === 'failed' ? 'pages.sources.fetchFailed' : null

  const providerName = t(`pages.sources.providerNames.${source.provider}`, { defaultValue: provider?.name ?? source.provider })
  return (
    <CollapsibleCard
      storageKey={`source-open-${source.id}`}
      title={
        <span className="flex flex-wrap items-center gap-x-2">
          <SourceLogo source={source} size={22} />
          {source.label}
          <span className="text-xs font-normal text-muted">{providerName} · {t(`pages.sources.kinds.${source.kind}`)}</span>
          <BetaBadge provider={provider} />
        </span>
      }
      meta={t('pages.sources.rows', { count: source.rows })}
      summary={(
        <>
        <BalanceBadge entry={balance} />
        {(channels.has('chain') || channels.has('api')) && (
        <>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs text-muted">
            {source.last_fetch ? t('pages.sources.lastFetch', { at: dateTime(source.last_fetch, tz) }) : t('pages.sources.neverFetched')}
            {job && <> · <JobLine job={job} /></>}
          </span>
          <Button variant="ghost" onClick={startFetch} disabled={!fetchable || !!busy} aria-label={`${t('pages.sources.fetch')} ${source.label}`}>
            <RefreshCw size={16} aria-hidden="true" className={busy ? 'animate-spin' : ''} />{t('pages.sources.fetch')}
          </Button>
        </div>
        {job?.status === 'failed' && job.message && <ErrorText>{messageText(job.message)}</ErrorText>}
        </>
        )}
        </>
      )}
    >
      {/* the balance first: it is what one opens the card for (Vanixxx, 2026-10-06) */}
      {/* folds like in a wallet: heading with its state, coins indented (Vanixxx, 2026-10-10) */}
      <Fold storageKey={`source-balance-open-${source.id}`} defaultOpen line={false} side={<BalanceBadge entry={balance} />}
        title={<span className="label">{t('balances.title')}</span>}>
        <BalanceTable entry={balance} sourceId={source.id} manual={!channels.has('api')} onChanged={onChanged} />
      </Fold>
      {/* the rest folds away as one, its parts once more inside (Vanixxx, 2026-10-10) */}
      <Fold storageKey={`source-access-open-${source.id}`} line={false} title={<span className="label">{t('pages.sources.access')}</span>}
        side={trouble && <Signal kind="bad" text={t(trouble)} />}>
        <div className="grid gap-3 pl-6">
          <BetaNote provider={provider} folded />
          {source.address && (
            <code className="block break-all font-mono text-xs text-muted" title={source.address}>{source.address}</code>
          )}
          {channels.has('api') && channels.has('file') && (
            <p className="m-0 text-xs leading-relaxed text-muted">
              {t('pages.sources.apiFirst')}
              {Object.entries(source.api_coverage).map(([market, from]) => (
                <span key={market} className="block">
                  {t('pages.sources.coveredFrom', { market: t(`pages.transactions.${market}`), date: date(from, tz) })}
                </span>
              ))}
            </p>
          )}
          {(channels.has('chain') || channels.has('api')) && (
            <div className="grid gap-2">
              <Toggle id={`auto-${source.id}`} label={t('pages.sources.autoFetch')} checked={source.auto_fetch}
                onChange={(v) => void api.setAutoFetch(source.id, v).then(onChanged, setError)} />
              {channels.has('api') && source.credentials.length === 0 && (
                <p className="m-0 text-xs text-muted">{t('pages.sources.needKey')}</p>
              )}
              {source.runs.every((r) => r.channel === 'file') && fetchable && (
                <p className="m-0 text-xs text-muted">{t('pages.sources.fetchFirst')}</p>
              )}
            </div>
          )}
          {channels.has('api') && provider?.credentials && (
            <Fold storageKey={`source-api-open-${source.id}`} title={<span className="label">{t('pages.sources.api')}</span>}
              side={source.credentials.length === 0 ? <Signal kind="none" text={t('pages.sources.noKey')} />
                : source.last_check && <Signal kind={source.last_check.ok ? 'ok' : 'bad'} text={t(source.last_check.ok ? 'pages.sources.checkOk' : 'pages.sources.checkFailed')} />}>
              <div className="pl-6"><ApiAccess source={source} fields={provider.credentials} onChanged={onChanged} plain /></div>
            </Fold>
          )}
          {channels.has('file') && (
            <Fold storageKey={`source-file-open-${source.id}`} title={<span className="label">{t('pages.sources.file')}</span>}>
              <div className="pl-6"><FileImport source={source} onImported={onChanged} plain /></div>
            </Fold>
          )}
          {/* any exchange: its own file through a column mapping (ADR 0048) */}
          {source.kind === 'exchange' && (
            <Fold storageKey={`source-mapped-open-${source.id}`}
              title={<span className="label flex items-center gap-2">{t('mapped.title')}<BetaTag /></span>}>
              <div className="pl-6"><MappedImport source={source} onImported={onChanged} /></div>
            </Fold>
          )}
          {(channels.has('file') || channels.has('api') || channels.has('chain') || source.kind === 'exchange') && (
            <Fold storageKey={`source-runs-open-${source.id}`}
              title={<span className="label">{t('pages.sources.runs')}{source.runs.length > 0 && ` (${source.runs.length})`}</span>}>
              <div className="pl-6"><Runs source={source} onChanged={onChanged} plain /></div>
            </Fold>
          )}
          {channels.has('manual') && <p className="m-0 text-sm text-muted">{t('manual.whereNow')}</p>}
          <LogoUpload kind="source" id={source.id} />
        </div>
      </Fold>
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
        {source.address ? <span className="text-xs text-muted">{shortAddress(source.address)}</span> : <span />}
        {source.runs.length > 0 || source.rows > 0 ? (
          <span className="text-xs text-muted">
            {source.runs.length > 0 ? t('pages.sources.deleteBlocked') : t('manual.deleteBlocked')}
          </span>
        ) : (
          <Confirm label={t('pages.sources.deleteSource')} question={t('pages.sources.deleteConfirm', { label: source.label })}
            onConfirm={() => api.deleteSource(source.id).then(onChanged, setError)} />
        )}
      </div>
    </CollapsibleCard>
  )
}

/** The state of a folded part at its right: green when it works, amber when not. */
function Signal({ kind, text }: { kind: 'ok' | 'bad' | 'none'; text: string }) {
  const Icon = kind === 'ok' ? CheckCircle2 : kind === 'bad' ? CircleAlert : KeyRound
  return (
    <span className={`inline-flex items-center gap-1 text-xs ${kind === 'ok' ? 'text-up' : kind === 'bad' ? 'text-warn' : 'text-muted'}`}>
      <Icon size={14} aria-hidden="true" />{text}
    </span>
  )
}

function JobLine({ job }: { job: Job }) {
  const { t } = useTranslation()
  const p = job.progress
  if (job.status === 'queued') return <span className="text-sm text-muted">{t('pages.sources.jobQueued')}</span>
  if (job.status === 'running') {
    return (
      <span className="num text-sm text-muted">
        {p.total ? t('pages.sources.jobProgress', { done: p.done, total: p.total, rows: p.rows ?? 0 }) : t('pages.sources.jobRunning')}
      </span>
    )
  }
  if (job.status === 'failed') return <StatusPill ok={false}>{t('pages.sources.jobFailed')}</StatusPill>
  return (
    <StatusPill ok>
      {t('pages.sources.jobDone', { added: job.result.added ?? 0, duplicates: job.result.duplicates ?? 0 })}
    </StatusPill>
  )
}
