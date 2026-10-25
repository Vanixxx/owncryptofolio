import { useState } from 'react'
import type { Source } from '../lib/api'
import { cx } from '../lib/cx'
import { CoinIcon } from './CoinIcon'
import { useLogoUrl } from '../lib/logos'

// provider → logo file in public/logos (from @web3icons, offline like the coins)
const EXCHANGES: Record<string, string> = {
  bitget: 'bitget', coinbase: 'coinbase', kraken: 'kraken', kucoin: 'kucoin',
  // ccxt exchanges (ADR 0048) the set has an icon for
  binance: 'binance', binanceus: 'binance', bitstamp: 'bitstamp', bybit: 'bybit', bybiteu: 'bybit', bybitid: 'bybit',
  coinex: 'coinex', cryptocom: 'crypto-com', gate: 'gate-io', gateeu: 'gate-io', gemini: 'gemini', okx: 'okx',
  myokx: 'okx', okxus: 'okx', coinbaseexchange: 'coinbase',
}
// the other ccxt exchanges: their website icon, fetched by this installation itself and kept
// in its data folder (Vanixxx, 2026-10-23) — the project ships no third-party logo
const SITE_ICON = (provider: string) => `/api/logos/site/${encodeURIComponent(provider)}`
const NETWORKS: Record<string, string> = {
  avalanche: 'avalanche', bnb: 'binance-smart-chain', bitcoin: 'bitcoin', cardano: 'cardano', cronos: 'cronos',
  ethereum: 'ethereum', hedera: 'hedera-hashgraph', litecoin: 'litecoin', polkadot: 'polkadot', polygon: 'polygon',
  ronin: 'ronin', solana: 'solana', sonic: 'sonic', stellar: 'stellar', sui: 'sui',
  arbitrum: 'arbitrum-one', optimism: 'optimism', linea: 'linea', mantle: 'mantle', blast: 'blast', zksync: 'zksync',
  celo: 'celo', tron: 'tron', xrp: 'xrp', algorand: 'algorand', ton: 'ton', near: 'near-protocol', cosmos: 'cosmos-hub', osmosis: 'osmosis',
}
// no logo in the set: the coin of the exchange or network stands in
const COINS: Record<string, string> = { mexc: 'MX', kaspa: 'KAS', vechain: 'VET', tezos: 'XTZ', dogecoin: 'DOGE', bitcoincash: 'BCH', celestia: 'TIA' }
// exchanges entered by hand are recognised by their name
const BY_NAME: [RegExp, string][] = [[/gate/i, 'exchanges/gate-io'], [/bitget/i, 'exchanges/bitget'], [/kraken/i, 'exchanges/kraken']]
const WALLETS: [RegExp, string][] = [[/metamask/i, 'metamask'], [/ronin/i, 'ronin'], [/ledger/i, 'ledger'], [/trust/i, 'trust']]

function Logo({ src, label, size, className }: { src: string | null; label: string; size: number; className?: string }) {
  // which src failed, not just "failed": a newly uploaded logo gets its own chance
  const [failed, setFailed] = useState<string | null>(null)
  if (!src || failed === src) {
    return (
      <span aria-hidden="true" style={{ width: size, height: size, fontSize: size * 0.42 }}
        className={cx('inline-grid shrink-0 place-items-center rounded-full bg-surface-2 font-semibold text-muted ring-1 ring-line', className)}>
        {label.replace(/[^\p{L}\p{N}]/gu, '').slice(0, 1).toUpperCase() || '?'}
      </span>
    )
  }
  return <img src={src} alt="" width={size} height={size} onError={() => setFailed(src)} className={cx('shrink-0 rounded-full object-cover', className)} />
}

/** The logo of an exchange or a network; a letter where the icon set has none. */
export function SourceLogo({ source, size = 20, className }: { source: Pick<Source, 'provider' | 'label' | 'kind'> & { id?: number }; size?: number; className?: string }) {
  const own = useLogoUrl('source', source.id)
  const p = source.provider
  if (own) return <Logo src={own} label={source.label} size={size} className={className} />
  if (COINS[p]) return <CoinIcon asset={COINS[p]} size={size} className={className} />
  const file = EXCHANGES[p] ? `exchanges/${EXCHANGES[p]}` : NETWORKS[p] ? `networks/${NETWORKS[p]}`
    : BY_NAME.find(([re]) => re.test(source.label))?.[1] ?? null
  const site = !file && source.kind === 'exchange' && p !== 'manual' ? SITE_ICON(p) : null
  return <Logo src={file ? `/logos/${file}.svg` : site} label={source.label} size={size} className={className} />
}

/** The logo of a wallet (device or app), recognised by its name. */
export function WalletLogo({ name, id, size = 20, className }: { name: string; id?: number; size?: number; className?: string }) {
  const own = useLogoUrl('wallet', id)
  if (own) return <Logo src={own} label={name} size={size} className={className} />
  const hit = WALLETS.find(([re]) => re.test(name))?.[1]
  return <Logo src={hit ? `/logos/wallets/${hit}.svg` : null} label={name} size={size} className={className} />
}

/** A wallet network as the wallet's logo with the network's logo pinned to its corner;
 * an exchange as its own logo. */
export function SourceAvatar({ source, wallet, size = 28 }: { source?: Pick<Source, 'provider' | 'label' | 'kind'> & { id?: number }; wallet?: { name: string; id?: number }; size?: number }) {
  if (!source) return <Logo src={null} label="?" size={size} />
  if (!wallet) return <SourceLogo source={source} size={size} />
  return (
    <span className="relative inline-block shrink-0" style={{ width: size, height: size }}>
      <WalletLogo name={wallet.name} id={wallet.id} size={size} />
      <SourceLogo source={source} size={Math.round(size * 0.55)} className="absolute -bottom-1 -right-1 ring-2 ring-surface-2" />
    </span>
  )
}
