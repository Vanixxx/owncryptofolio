import { CircleAlert, KeyRound, RefreshCw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { SourceAlert } from '../lib/api'
import { alertText } from '../lib/alerts'
import { useMessageText } from '../lib/useErrorText'

/** `onFetch` puts a small fetch button next to a failed or ageing fetch (Vanixxx, 2026-10-17). */
export function SourceAlerts({ alerts, name, onFetch, busy }: {
  alerts: SourceAlert[]; name: (id: number) => string; onFetch?: (id: number) => void; busy?: (id: number) => boolean
}) {
  const { t } = useTranslation()
  const messageText = useMessageText()
  if (alerts.length === 0) return null
  return (
    <ul className="m-0 grid list-none gap-2 rounded-card border border-warn/40 bg-warn/10 p-3">
      {alerts.map((a) => (
        <li key={`${a.source_id}${a.kind}`} className="grid grid-cols-[auto_minmax(0,1fr)] gap-2 text-sm">
          {a.kind.startsWith('key') ? <KeyRound size={16} aria-hidden="true" className="mt-0.5 text-warn" />
            : <CircleAlert size={16} aria-hidden="true" className="mt-0.5 text-warn" />}
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
            <span className="leading-relaxed">{alertText(t, a, name(a.source_id), a.message ? messageText(a.message) : '')}</span>
            {onFetch && a.kind !== 'key_rejected' && (
              <button type="button" onClick={() => onFetch(a.source_id)} disabled={busy?.(a.source_id)}
                className="inline-flex items-center gap-1.5 rounded-ctl border border-warn/50 px-2.5 py-1 text-xs text-fg hover:bg-warn/15 disabled:opacity-60">
                <RefreshCw size={13} aria-hidden="true" className={busy?.(a.source_id) ? 'animate-spin' : ''} />
                {busy?.(a.source_id) ? t('pages.sources.fetching') : t('pages.sources.fetchAgain')}
              </button>
            )}
          </span>
        </li>
      ))}
    </ul>
  )
}
