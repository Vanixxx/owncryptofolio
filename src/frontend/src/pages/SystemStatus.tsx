import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button, Card, ErrorText, PageHeader, Row, StatusPill } from '../components/ui'
import { useJobs } from '../hooks/useJobs'
import { useSettings } from '../app/settings'
import { dateTime } from '../lib/format'
import { locale } from '../i18n'
import { api, type McpStatus, type Source, type SystemStatus as Status, type Wallet } from '../lib/api'
import { sourceName } from '../lib/txFilter'
import { useErrorText, useMessageText } from '../lib/useErrorText'
import { LogsCard } from './system/LogsCard'
import { LicensesCard } from './system/LicensesCard'

function duration(seconds: number, loc: string) {
  const d = Math.floor(seconds / 86400), h = Math.floor((seconds % 86400) / 3600), m = Math.floor((seconds % 3600) / 60)
  const f = (v: number, unit: 'day' | 'hour' | 'minute') =>
    new Intl.NumberFormat(loc, { style: 'unit', unit, unitDisplay: 'short' }).format(v)
  return [d && f(d, 'day'), (d || h) && f(h, 'hour'), f(m, 'minute')].filter(Boolean).join(' ')
}

export function SystemStatus() {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const [status, setStatus] = useState<Status | null>(null)
  const [error, setError] = useState<unknown>(null)

  const fetchStatus = useCallback(() => api.systemStatus().then(setStatus, setError), [])
  useEffect(() => void fetchStatus(), [fetchStatus])
  const retry = () => {
    setError(null)
    void fetchStatus()
  }

  return (
    <>
      <PageHeader title={t('system.title')} subtitle={t('system.subtitle')} />
      {error ? (
        <Card>
          <ErrorText>{errorText(error)}</ErrorText>
          <Button variant="ghost" onClick={retry} className="justify-self-start">{t('common.retry')}</Button>
        </Card>
      ) : !status ? (
        <p className="text-muted">{t('common.loading')}</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 md:gap-5">
          <Card title={t('system.database')}>
            <div>
              <Row label={t('system.database')}>
                <StatusPill ok={status.database.connected}>{t('system.connected')}</StatusPill>
              </Row>
              <Row label={t('system.server')}><span className="num">PostgreSQL {status.database.server_version}</span></Row>
              <Row label={t('system.migration')}>
                <StatusPill ok={status.migration.up_to_date}>
                  {status.migration.up_to_date ? t('system.upToDate') : t('system.outdated')}
                  <span className="num text-muted">{status.migration.current}</span>
                </StatusPill>
              </Row>
              {status.database.created_on_start && <Row label={status.database.name}>{t('system.createdOnStart')}</Row>}
            </div>
          </Card>
          <Card title={t('app.name')}>
            <div>
              <Row label={t('system.version')}><span className="num">{status.version}</span></Row>
              <Row label={t('system.uptime')}><span className="num">{duration(status.uptime_seconds, locale())}</span></Row>
              <Row label={t('system.dataDir')}><span className="num">{status.data_dir}</span></Row>
              <McpRow />
              {Object.entries(status.keys).map(([k, src]) => (
                <Row key={k} label={`${t('system.keys')}: ${t(`system.keyNames.${k}`)}`}>{t(`system.keySource.${src}`)}</Row>
              ))}
            </div>
          </Card>
          <OperationsCard ops={status.operations} />
          <JobsCard />
          <LogsCard />
          <LicensesCard />
        </div>
      )}
    </>
  )
}

/** Is Claude connected through MCP, and when did it last ask (ADR 0049)? */
function McpRow() {
  const { t } = useTranslation()
  const tz = useSettings().settings['general.timezone']
  const [mcp, setMcp] = useState<McpStatus | null>(null)
  useEffect(() => void api.mcp().then(setMcp, () => {}), [])
  if (!mcp) return null
  return (
    <Row label={t('system.access')}>
      <span className="grid justify-items-end gap-0.5 text-right">
        <span className="text-sm">
          Claude {t(mcp.enabled ? 'system.on' : 'system.off')} · API {t(mcp.api_enabled ? 'system.on' : 'system.off')} · {t('system.mcpTokens', { count: mcp.tokens.length })}
        </span>
        {mcp.last_call && <span className="text-xs text-muted">{t('mcp.lastCall', { tool: mcp.last_call.tool, token: mcp.last_call.token, at: dateTime(mcp.last_call.at, tz) })}</span>}
      </span>
    </Row>
  )
}

function gb(bytes: number, loc: string) {
  // a big share reads better in TB: "1,1 TB frei von 8,6 TB" (phone, 2026-10-12)
  const [v, unit] = bytes >= 1024 ** 4 ? [bytes / 1024 ** 4, 'TB'] : [bytes / 1024 ** 3, 'GB']
  return new Intl.NumberFormat(loc, { maximumFractionDigits: 1 }).format(v) + ' ' + unit
}

/** A size the way people read it: KB, MB or GB. */
function size(bytes: number, loc: string) {
  const [v, unit] = bytes >= 1024 ** 3 ? [bytes / 1024 ** 3, 'GB'] : bytes >= 1024 ** 2 ? [bytes / 1024 ** 2, 'MB'] : [bytes / 1024, 'KB']
  return new Intl.NumberFormat(loc, { maximumFractionDigits: 1 }).format(v) + ' ' + unit
}

/** Does it all run on its own? Backup, fetch, prices, tools, disk (M8, 2026-10-12). */
function OperationsCard({ ops }: { ops: Status['operations'] }) {
  const { t } = useTranslation()
  const tz = useSettings().settings['general.timezone']
  const when = (v: string | null) => (v ? dateTime(v, tz) : t('system.ops.never'))
  const line = (key: 'backup' | 'fetch' | 'prices' | 'fine', ok: boolean, extra?: string) => {
    const o = ops[key]
    if (!o) return null
    return (
      <Row label={t(`system.ops.${key}`)}>
        <span className="grid justify-items-end gap-0.5 text-right">
          {o.enabled
            ? <StatusPill ok={ok}>{o.last_at ? when(o.last_at) : t('system.ops.never')}</StatusPill>
            : <span className="text-sm text-muted">{t('system.ops.off')}</span>}
          {extra && <span className="text-xs text-down">{extra}</span>}
          {o.next_at && <span className="text-xs text-muted">{t('system.ops.next', { at: dateTime(o.next_at, tz) })}</span>}
        </span>
      </Row>
    )
  }
  const b = ops.backup
  const backupOk = b.status === 'done' && b.probe_ok !== false
  // what owncryptofolio itself takes, then what the disk still has (Vanixxx, 2026-10-12)
  const disk = (d: Status['operations']['disk']['data'], label: string) => d && (
    <Row label={label}>
      <span className="grid justify-items-end gap-0.5 text-right">
        <span className="num text-sm">{t('system.ops.used', { used: size(d.used, locale()) })}</span>
        <StatusPill ok={d.free / d.total > 0.05}>{t('system.ops.free', { free: gb(d.free, locale()), total: gb(d.total, locale()) })}</StatusPill>
      </span>
    </Row>
  )
  const total = ops.disk.database + (ops.disk.data?.used ?? 0) + (ops.disk.backups?.used ?? 0)
  return (
    <Card title={t('system.ops.title')} className="md:col-span-2">
      <div>
        {line('backup', backupOk, b.status === 'failed' ? b.message ?? undefined : b.probe_ok === false ? t('system.ops.probeFailed') : undefined)}
        {line('fetch', ops.fetch.status !== 'failed' && ops.fetch.failed === 0, ops.fetch.failed ? t('system.ops.failed', { count: ops.fetch.failed }) : undefined)}
        {line('prices', ops.prices.status !== 'failed', undefined)}
        <Row label={t('system.ops.live')}><span className="num text-sm">{when(ops.prices.live_at)}</span></Row>
        {line('fine', ops.fine?.status !== 'failed', undefined)}
        <Row label={t('system.ops.tools')}>
          <StatusPill ok={ops.tools.ok}>
            {ops.tools.pg_dump ? `pg_dump ${ops.tools.pg_dump}` : t('system.ops.toolsMissing')}
            {!ops.tools.ok && ops.tools.pg_dump && <span className="text-xs"> · {t('system.ops.toolsOld', { server: ops.tools.server })}</span>}
          </StatusPill>
        </Row>
        <Row label={t('system.ops.diskDatabase')}><span className="num text-sm">{size(ops.disk.database, locale())}</span></Row>
        {disk(ops.disk.data, t('system.ops.diskData'))}
        {disk(ops.disk.backups, t('system.ops.diskBackups'))}
        <Row label={t('system.ops.diskTotal')}><b className="num text-sm">{size(total, locale())}</b></Row>
      </div>
    </Card>
  )
}

function JobsCard() {
  const { t } = useTranslation()
  const messageText = useMessageText()
  const tz = useSettings().settings['general.timezone']
  const { jobs } = useJobs()
  // which source a fetch was for: "Abruf · Tangem – Ethereum" says more than "#86"
  const [names, setNames] = useState<{ sources: Source[]; wallets: Wallet[] }>({ sources: [], wallets: [] })
  useEffect(() => {
    Promise.all([api.sources(), api.wallets()]).then(([sources, wallets]) => setNames({ sources, wallets }), () => {})
  }, [])
  const name = sourceName(names.sources, names.wallets)
  return (
    <Card title={t('system.jobs')} className="md:col-span-2">
      {jobs.length === 0 && <p className="m-0 text-sm text-muted">{t('system.jobsEmpty')}</p>}
      <ul className="m-0 grid list-none p-0">
        {jobs.slice(0, 15).map((j) => (
          <li key={j.id} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-t border-line py-2 text-sm first:border-t-0">
            <span>
              {t(`system.jobKinds.${j.kind}`)}
              {j.source_id !== null && names.sources.length > 0 && <> · {name(j.source_id)}</>}
              <span className="num ml-1.5 text-xs text-muted">#{j.id}</span>
            </span>
            <span className="text-xs text-muted">{dateTime(j.finished_at ?? j.started_at ?? j.created_at, tz)}</span>
            <StatusPill ok={j.status !== 'failed'}>{t(`system.jobStatus.${j.status}`)}</StatusPill>
            {j.message && <span className="w-full break-all text-xs text-down">{messageText(j.message)}</span>}
          </li>
        ))}
      </ul>
    </Card>
  )
}
