import { Check, Copy, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useSettings } from '../../app/settings'
import { Button, Card, ErrorText, Segmented } from '../../components/ui'
import { Confirm } from '../../components/ui/Confirm'
import { Toggle } from '../../components/ui/Toggle'
import { api, type McpStatus, type TokenKind, type TokenLevel } from '../../lib/api'
import { copyText } from '../../lib/copy'
import { dateTime } from '../../lib/format'
import { useErrorText } from '../../lib/useErrorText'

/** Claude through MCP (ADR 0049): on/off for all, read or edit per token, and the commands
 * to connect. A token works only here, never for the JSON API (Vanixxx, 2026-10-20). */
export function McpCard() {
  const { t } = useTranslation()
  const origin = `${window.location.protocol}//${window.location.host}`
  return (
    <Access kind="mcp" fold="settings-open-mcp" title={t('mcp.title')} text={t('mcp.text')} setting="mcp.enabled"
      toggle={t('mcp.toggle')}
      help={(token) => {
        const url = `${origin}/mcp`
        const code = `claude mcp add --transport http owncryptofolio ${url} --header "Authorization: Bearer ${token}"`
        const desktop = JSON.stringify({ mcpServers: { owncryptofolio: { command: 'npx',
          args: ['-y', 'mcp-remote', url, '--allow-http', '--header', `Authorization: Bearer ${token}`] } } }, null, 2)
        return (
          <details className="text-sm">
            <summary className="cursor-pointer font-semibold">{t('mcp.connect')}</summary>
            <div className="mt-2 grid gap-3">
              <div className="grid gap-1"><span className="label">Claude Code</span><CopyBox text={code} /></div>
              <div className="grid gap-1">
                <span className="label">Claude Desktop</span>
                <p className="m-0 text-xs text-muted">{t('mcp.desktopHint')}</p>
                <CopyBox text={desktop} />
              </div>
              <p className="m-0 text-xs text-muted">{t('mcp.lanHint')}</p>
            </div>
          </details>
        )
      }} />
  )
}

/** The JSON API (ADR 0050): its own switch and its own tokens, reading only. */
export function ApiCard() {
  const { t } = useTranslation()
  const { settings } = useSettings()
  const origin = `${window.location.protocol}//${window.location.host}`
  return (
    <Access kind="api" fold="settings-open-api" title={t('mcp.apiTitle')} text={t('mcp.apiText')} setting="api.enabled"
      toggle={t('mcp.apiToggle')}
      help={(token) => (
        <details className="text-sm">
          <summary className="cursor-pointer font-semibold">{t('mcp.apiUse')}</summary>
          <div className="mt-2 grid gap-3">
            <div className="grid gap-1">
              <span className="label">{t('mcp.apiList')}</span>
              <CopyBox text={`curl -H "Authorization: Bearer ${token}" ${origin}/api/v1`} />
            </div>
            <div className="grid gap-1">
              <span className="label">{t('mcp.apiValue')}</span>
              <CopyBox text={`curl -H "Authorization: Bearer ${token}" ${origin}/api/v1/portfolio`} />
            </div>
            <div className="grid gap-1">
              <span className="label">Home Assistant (configuration.yaml)</span>
              <CopyBox text={`rest:
  - resource: ${origin}/api/v1/portfolio
    headers:
      Authorization: Bearer ${token}
    scan_interval: 900
    sensor:
      - name: owncryptofolio Wert
        value_template: "{{ value_json.summary.value }}"
        unit_of_measurement: "${settings['general.currency']}"`} />
            </div>
            <p className="m-0 text-xs text-muted">{t('mcp.apiHint')}</p>
          </div>
        </details>
      )} />
  )
}

function Access({ kind, fold, title, text, setting, toggle, help }: {
  kind: TokenKind; fold: string; title: string; text: string; setting: 'mcp.enabled' | 'api.enabled'; toggle: string
  help: (token: string) => ReactNode
}) {
  const { t } = useTranslation()
  const errorText = useErrorText()
  const { settings, update } = useSettings()
  const tz = settings['general.timezone']
  const [status, setStatus] = useState<McpStatus | null>(null)
  const [name, setName] = useState('')
  const [level, setLevel] = useState<TokenLevel>('read')
  const [fresh, setFresh] = useState<{ name: string; token: string } | null>(null)
  const [error, setError] = useState<unknown>(null)
  const load = useCallback(() => api.mcp().then(setStatus, setError), [])
  useEffect(() => void load(), [load])
  const mine = status?.tokens.filter((x) => x.kind === kind) ?? []

  const create = async (e: FormEvent) => {
    e.preventDefault()
    try {
      const r = await api.mcpCreateToken(name, kind, kind === 'mcp' ? level : 'read')
      setFresh({ name: r.name, token: r.token }); setName(''); setError(null); void load()
    } catch (err) { setError(err) }
  }
  const levels = (['read', 'edit'] as const).map((v) => ({ value: v, label: t(`mcp.levels.${v}`) }))

  return (
    <Card fold={fold} title={title}>
      <p className="m-0 text-sm leading-relaxed text-muted">{text}</p>
      <Toggle id={`${kind}-enabled`} label={toggle} checked={settings[setting]}
        onChange={(v) => void update({ [setting]: v }).then(() => setError(null), setError)} />

      <div className="grid gap-2">
        <span className="label">{t('mcp.tokens')}</span>
        {status && mine.length === 0 && <p className="m-0 text-xs text-muted">{t(`mcp.noTokens.${kind}`)}</p>}
        <ul className="m-0 grid list-none gap-1 p-0">
          {mine.map((x) => (
            <li key={x.id} className="flex flex-wrap items-center justify-between gap-2 border-t border-line py-1.5 text-sm first:border-t-0">
              <span className="grid">
                <span>{x.name}</span>
                <span className="text-xs text-muted">{x.last_used_at ? t('mcp.used', { at: dateTime(x.last_used_at, tz) }) : t('mcp.unused')}</span>
              </span>
              <span className="flex flex-wrap items-center gap-2">
                {kind === 'mcp' && (
                  <Segmented label={`${t('mcp.level')} ${x.name}`} value={x.level} options={levels}
                    onChange={(v) => void api.mcpSetLevel(x.id, v).then(load, setError)} />
                )}
                <Confirm label={<><Trash2 size={14} aria-hidden="true" />{t('mcp.revoke')}</>} question={t('mcp.revokeText', { name: x.name })}
                  onConfirm={() => void api.mcpRevokeToken(x.id).then(load, setError)} />
              </span>
            </li>
          ))}
        </ul>
        <form onSubmit={create} className="flex flex-wrap items-center gap-2">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t(`mcp.namePlaceholder.${kind}`)} maxLength={80} required
            aria-label={t('mcp.name')} className="min-w-48 flex-1 rounded-ctl border border-line bg-surface-2 px-3 py-2 text-base text-fg" />
          {kind === 'mcp' && <Segmented label={t('mcp.level')} value={level} onChange={setLevel} options={levels} />}
          <Button type="submit">{t('mcp.create')}</Button>
        </form>
        {kind === 'mcp' && <p className="m-0 text-xs leading-relaxed text-muted">{t('mcp.levelHint')}</p>}
      </div>

      {fresh && (
        <div role="status" className="grid gap-1.5 rounded-ctl border border-up/50 bg-up/5 p-3">
          <b className="text-sm">{t('mcp.freshTitle', { name: fresh.name })}</b>
          <p className="m-0 text-xs text-muted">{t('mcp.freshHint')}</p>
          <CopyBox text={fresh.token} />
        </div>
      )}
      {help(fresh?.token ?? '<TOKEN>')}
      {!fresh && <p className="m-0 text-xs text-muted">{t('mcp.placeholderHint')}</p>}
      {status?.last_call && (
        <p className="m-0 text-xs text-muted">{t('mcp.lastCall', { tool: status.last_call.tool, token: status.last_call.token, at: dateTime(status.last_call.at, tz) })}</p>
      )}
      <ErrorText>{error ? errorText(error) : null}</ErrorText>
    </Card>
  )
}

function CopyBox({ text }: { text: string }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  const copy = () => void copyText(text).then((ok) => { if (ok) { setCopied(true); setTimeout(() => setCopied(false), 1500) } })
  return (
    <div className="relative">
      <pre className="m-0 max-h-56 overflow-auto whitespace-pre-wrap break-all rounded-ctl bg-surface-2 p-2 pr-10 font-mono text-xs">{text}</pre>
      <button type="button" onClick={copy} aria-label={t('mcp.copy')}
        className="absolute right-1.5 top-1.5 rounded-ctl border-0 bg-surface p-1.5 text-muted hover:text-fg">
        {copied ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
      </button>
    </div>
  )
}
