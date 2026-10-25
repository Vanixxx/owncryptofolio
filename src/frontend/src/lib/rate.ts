import { locale } from '../i18n'

/** Which side of a pair is the price unit: money first, then stablecoins, then the big
 * coins people price in — as exchanges name their pairs (BTC/USDT, ADA/BTC). */
const QUOTES = ['EUR', 'USD', 'USDT', 'USDC', 'FDUSD', 'EURC', 'DAI', 'BUSD', 'BTC', 'ETH', 'BNB']

export type Rate = { base: string; quote: string; price: number; baseSide: 'incoming' | 'outgoing' }

/** The rate of a trade from its two sides: "1 BTC = 25,848 USDT" (Vanixxx, 2026-10-13). */
export function tradeRate(incoming: [string | null, string | null], outgoing: [string | null, string | null]): Rate | null {
  const [ia, iq] = incoming
  const [oa, oq] = outgoing
  if (!ia || !oa || !iq || !oq || ia === oa) return null
  const rank = (a: string) => { const i = QUOTES.indexOf(a); return i < 0 ? QUOTES.length : i }
  const inIsQuote = rank(ia) < rank(oa)
  const [base, baseQty, quote, quoteQty] = inIsQuote ? [oa, oq, ia, iq] : [ia, iq, oa, oq]
  const b = Number(baseQty), q = Number(quoteQty)
  if (!(b > 0) || !(q > 0)) return null
  return { base, quote, price: q / b, baseSide: inIsQuote ? 'outgoing' : 'incoming' }
}

/** A price in coin units: enough digits for 0.0000005 QUBIC and for 25,848 USDT. */
export function rateText(v: number): string {
  const a = Math.abs(v)
  const opts: Intl.NumberFormatOptions = a >= 1000 ? { maximumFractionDigits: 2 } : a >= 1 ? { maximumFractionDigits: 4 } : { maximumSignificantDigits: 4 }
  return v.toLocaleString(locale(), opts)
}
