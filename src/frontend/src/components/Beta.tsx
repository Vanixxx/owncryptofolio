import { FlaskConical } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { Provider } from '../lib/api'
import { cx } from '../lib/cx'

/** The ways in that nobody checked against a real account yet (ADR 0048). */
export function betaChannels(p?: Provider | null) {
  return p?.channels.filter((c) => c.status === 'beta') ?? []
}

/** Tested if at least one way in is: those make up the short list when adding. */
export function tested(p: Provider) {
  return p.channels.some((c) => c.status === 'tested')
}

export function BetaBadge({ provider, className }: { provider?: Provider | null; className?: string }) {
  const { t } = useTranslation()
  const beta = betaChannels(provider)
  if (!provider || !beta.length) return null
  // Kraken: the file is tested, the API not — the badge says which
  const which = tested(provider) ? ` · ${beta.map((c) => t(`pages.sources.channels.${c.channel}`)).join(', ')}` : ''

  return <BetaTag className={className} text={`${t('beta.badge')}${which}`} />
}

export function BetaTag({ className, text }: { className?: string; text?: string }) {
  const { t } = useTranslation()
  return (
    <span title={t('beta.badgeTitle')}
      className={cx('inline-flex items-center gap-1 rounded-full border border-warn/50 px-1.5 py-px text-[0.68rem] font-semibold text-warn', className)}>
      <FlaskConical size={11} aria-hidden="true" />{text ?? t('beta.badge')}
    </span>
  )
}

/** What may go wrong with an untested way in, said before adding and kept on the card.
 * Gathered from what went wrong with the tested ones (Vanixxx, 2026-10-18). */
export function BetaNote({ provider, folded }: { provider?: Provider | null; folded?: boolean }) {
  const { t } = useTranslation()
  const beta = betaChannels(provider)
  if (!provider || !beta.length) return null
  const exchange = provider.kind === 'exchange'
  const which = beta.map((c) => t(`pages.sources.channels.${c.channel}`)).join(', ')
  const risks = exchange ? ['fees', 'history', 'pairs', 'notRead', 'limits', 'names'] : ['chain', 'names']
  const body = (
    <div className="grid gap-2 text-xs leading-relaxed">
      <p className="m-0">{t(exchange ? 'beta.intro' : 'beta.introChain', { name: provider.name, which })}</p>
      <ul className="m-0 grid gap-1 pl-4">
        {risks.map((r) => <li key={r}>{t(`beta.risks.${r}`)}</li>)}
      </ul>
      <p className="m-0">{t('beta.check')}</p>
      <p className="m-0 text-muted">{t('beta.tests')}</p>
    </div>
  )
  const box = 'rounded-ctl border border-warn/40 bg-warn/5 p-3 text-fg'
  if (folded) {
    return (
      <details className={box}>
        <summary className="cursor-pointer text-xs font-semibold text-warn">{t('beta.title', { which })}</summary>
        <div className="mt-2">{body}</div>
      </details>
    )
  }
  return (
    <div role="note" className={cx(box, 'grid gap-2')}>
      <b className="flex items-center gap-1.5 text-xs text-warn"><FlaskConical size={14} aria-hidden="true" />{t('beta.title', { which })}</b>
      {body}
    </div>
  )
}
