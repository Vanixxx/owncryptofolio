import type { Source, Wallet } from './api'

export type TxFilter = { source: string; market: '' | 'spot' | 'futures'; from: string; to: string; kind: string; asset: string; q: string; show: string; origin: string }
export const NO_FILTER: TxFilter = { source: '', market: '', from: '', to: '', kind: '', asset: '', q: '', show: 'normal', origin: '' }

export const KINDS = ['trade', 'send', 'receive', 'fiat_deposit', 'fiat_withdrawal', 'income', 'internal_transfer',
  'migration', 'fee', 'realized_pnl', 'funding', 'futures_position', 'other']

/** A wallet network reads "Tangem – Ethereum": the network alone does not say whose it is. */
export function sourceName(sources: Source[], wallets: Wallet[]) {
  return (id: number) => {
    const s = sources.find((x) => x.id === id)
    if (!s) return `#${id}`
    const w = wallets.find((x) => x.id === s.wallet_id)
    return w ? `${w.name} – ${s.label}` : s.label
  }
}

/** Query parameters for /api/raw and /api/merged; dates are days in the user's zone. */
export function filterParams(f: TxFilter, tz: string) {
  // several sources and whole wallets at once: "s:3,w:1,s:7" (Vanixxx, 2026-10-07)
  const picks = f.source.split(',').filter(Boolean).map((p) => p.split(':'))
  const ids = (type: string) => picks.filter(([t]) => t === type).map(([, id]) => id).join(',') || undefined
  return {
    source_id: ids('s'),
    wallet_id: ids('w'),
    market: f.market || undefined,
    date_from: f.from || undefined,
    date_to: f.to || undefined,
    tz: f.from || f.to ? tz : undefined,
    kind: f.kind || undefined,
    asset: f.asset || undefined,
    q: f.q.trim() || undefined,
    show: f.show !== 'normal' ? f.show : undefined,
    origin: f.origin || undefined,
  }
}

/** Words of the page (kinds, notices, markets) the user may type, with the keys the server
 * knows them by: a typed word becomes "word|key|key", any of which may match. */
export function expandQuery(q: string, t: (k: string) => string): string | undefined {
  const words = q.trim().toLowerCase().split(/\s+/).filter(Boolean)
  if (words.length === 0) return undefined
  const labels: [string, string][] = [
    ...KINDS.map((k) => [t(`kinds.${k}`), k] as [string, string]),
    [t('merged.transfer'), 'transfer'],
    ...['open', 'ambiguous', 'dust', 'spam', 'edited', 'noted', 'marked'].map((n) => [t(`merged.filters.${n}`), n] as [string, string]),
    [t('pages.transactions.spot'), 'spot'], [t('pages.transactions.futures'), 'futures'],
  ]
  return words.map((w) => {
    const keys = w.length < 3 ? [] : labels.filter(([label]) => label.toLowerCase().includes(w)).map(([, key]) => key)
    return [w, ...new Set(keys)].join('|')
  }).join(' ')
}

export type SourceRef = { source?: Source; wallet?: Wallet }

/** The source and, for a network, its wallet: for logos and two-line names. */
export function sourceLookup(sources: Source[], wallets: Wallet[]) {
  return (id: number): SourceRef => {
    const source = sources.find((x) => x.id === id)
    return { source, wallet: wallets.find((w) => w.id === source?.wallet_id) }
  }
}
