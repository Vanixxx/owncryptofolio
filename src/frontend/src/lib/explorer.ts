/** Block explorer pages per network (Vanixxx, 2026-10-14): the transaction ID of a chain row
 * becomes a link. IDs carry readers' suffixes ("sig:rn", "digest:SUI", "assethub:hash:3"). */
const TX: Record<string, string> = {
  bitcoin: 'https://mempool.space/tx/{id}',
  litecoin: 'https://litecoinspace.org/tx/{id}',
  ethereum: 'https://etherscan.io/tx/{id}',
  bnb: 'https://bscscan.com/tx/{id}',
  polygon: 'https://polygonscan.com/tx/{id}',
  avalanche: 'https://snowtrace.io/tx/{id}',
  sonic: 'https://sonicscan.org/tx/{id}',
  cronos: 'https://explorer.cronos.org/tx/{id}',
  ronin: 'https://app.roninchain.com/tx/{id}',
  solana: 'https://solscan.io/tx/{id}',
  cardano: 'https://cardanoscan.io/transaction/{id}',
  hedera: 'https://hashscan.io/mainnet/transactionsById/{id}',
  kaspa: 'https://explorer.kaspa.org/txs/{id}',
  polkadot: 'https://polkadot.subscan.io/extrinsic/{id}',
  stellar: 'https://stellar.expert/explorer/public/tx/{id}',
  sui: 'https://suiscan.xyz/mainnet/tx/{id}',
  vechain: 'https://vechainstats.com/transaction/{id}',
  xrp: 'https://livenet.xrpl.org/transactions/{id}',
  tezos: 'https://tzkt.io/{id}',
  algorand: 'https://allo.info/tx/{id}',
  tron: 'https://tronscan.org/#/transaction/{id}',
  ton: 'https://tonviewer.com/transaction/{id}',
  dogecoin: 'https://blockchair.com/dogecoin/transaction/{id}',
  bitcoincash: 'https://blockchair.com/bitcoin-cash/transaction/{id}',
  near: 'https://nearblocks.io/txns/{id}',
  cosmos: 'https://www.mintscan.io/cosmos/tx/{id}',
  osmosis: 'https://www.mintscan.io/osmosis/tx/{id}',
  celestia: 'https://www.mintscan.io/celestia/tx/{id}',
}

export function explorerUrl(provider: string | undefined, externalId: string | null): string | null {
  if (!provider || !externalId || /^(form|accrual):/.test(externalId)) return null
  let id = externalId
  let template = TX[provider]
  if (provider === 'polkadot' && id.startsWith('assethub:')) {
    id = id.split(':')[1]
    template = 'https://assethub-polkadot.subscan.io/extrinsic/{id}'
  } else if (provider !== 'hedera') {
    id = id.split(':')[0]
  }
  // a Tezos token transfer names its operation by number only; TON hashes come as base64
  if (provider === 'tezos' && id.startsWith('op')) return null
  if (provider === 'ton') {
    try { id = Array.from(atob(id.replace(/-/g, '+').replace(/_/g, '/')), (c) => c.charCodeAt(0).toString(16).padStart(2, '0')).join('') } catch { return null }
  }
  return template ? template.replace('{id}', encodeURIComponent(id)) : null
}

/** A transfer's exchange side often carries the chain's hash too: it links to the
 * explorer of the chain side when the IDs match. */
export function sameTx(a: string | null, b: string | null): boolean {
  const norm = (x: string) => x.toLowerCase().replace(/^0x/, '').split(':')[0]
  return !!a && !!b && norm(a) === norm(b)
}
