import { locale } from '../i18n'

/** Formats a decimal string without going through float: 18 decimals stay 18 decimals. */
export function amount(value: string | null, maxDecimals = 8): string {
  if (value === null || value === '') return ''
  const negative = value.startsWith('-')
  const [int, frac = ''] = value.replace('-', '').split('.')
  const loc = locale()
  const grouped = new Intl.NumberFormat(loc).format(BigInt(int || '0'))
  const sep = new Intl.NumberFormat(loc).formatToParts(1.1).find((p) => p.type === 'decimal')?.value ?? ','
  let decimals = frac.replace(/0+$/, '')
  if (decimals.length > maxDecimals) decimals = decimals.slice(0, maxDecimals) + '…'
  return `${negative ? '−' : ''}${grouped}${decimals ? sep + decimals : ''}`
}

export function dateTime(iso: string | null, timeZone?: string): string {
  if (!iso) return ''
  return new Intl.DateTimeFormat(locale(), {
    // with seconds: two fills of one order are often seconds apart
    dateStyle: 'medium', timeStyle: 'medium', timeZone,
  }).format(new Date(iso))
}

export function date(iso: string | null, timeZone?: string): string {
  if (!iso) return ''
  // a plain day ("2027-03-15") is that day everywhere: read as UTC midnight, a browser west
  // of UTC would otherwise show the day before — "tax-free on" one day early (review 2026-10-25)
  const day = /^\d{4}-\d{2}-\d{2}$/.test(iso)
  return new Intl.DateTimeFormat(locale(), { dateStyle: 'medium', timeZone: day ? 'UTC' : timeZone }).format(new Date(iso))
}

export function bytes(n: number | null): string {
  if (n === null) return ''
  const units = ['B', 'KB', 'MB', 'GB']
  let v = n, i = 0
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
  return `${new Intl.NumberFormat(locale(), { maximumFractionDigits: 1 }).format(v)} ${units[i]}`
}

export function shortAddress(a: string | null): string {
  return a && a.length > 14 ? `${a.slice(0, 8)}…${a.slice(-6)}` : a ?? ''
}

/** Prices range from 0.0000005 (QUBIC) to six digits (BTC): significant digits, not decimals. */
export function priceText(v: number, currency = 'EUR') {
  if (!Number.isFinite(v)) return ''
  if (v !== 0 && Math.abs(v) < 0.0001) return `${v.toExponential(2)} ${currency === 'EUR' ? '€' : '$'}`
  const digits = Math.abs(v) >= 1 ? { minimumFractionDigits: 2, maximumFractionDigits: 2 } : { maximumSignificantDigits: 4 }
  return new Intl.NumberFormat(locale(), { style: 'currency', currency, ...digits }).format(v)
}

/** Money with two decimals; `signed` puts + before gains (P/L). */
export function money(v: string | null | undefined, currency = 'EUR', signed = false): string {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  const text = new Intl.NumberFormat(locale(), { style: 'currency', currency, minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n)
  // a word joiner keeps the sign on the amount: "+€14,596.19" must not break after "+" or "-"
  // (English puts the symbol first; Vanixxx, 2026-10-24)
  const out = signed && n > 0 ? `+${text}` : text
  return out.replace(/^([+-])/, '$1\u2060')
}

export function percent(v: string | null | undefined, signed = true): string {
  if (v === null || v === undefined || v === '') return ''
  const n = Number(v)
  const text = `${n.toLocaleString(locale(), { maximumFractionDigits: 1, minimumFractionDigits: 1 })} %`
  return signed && n > 0 ? `+${text}` : text
}

/** Up, down or flat for colouring a P/L. */
export function trend(v: string | null | undefined): 'up' | 'down' | 'flat' {
  const n = Number(v ?? 0)
  return n > 0 ? 'up' : n < 0 ? 'down' : 'flat'
}

/** A coin quantity for reading, not for checking: big amounts with few decimals, small ones
 * with four significant digits (0.00000017 BTC stays visible). The exact value is in the
 * transactions. */
export function quantity(v: string | null | undefined): string {
  if (v === null || v === undefined || v === '') return ''
  const n = Number(v)
  const a = Math.abs(n)
  // from a million on short (448,07 Mio. XEN): the exact amount is in the tooltip and the raw data
  const opts: Intl.NumberFormatOptions = a >= 1e6 ? { notation: 'compact', maximumFractionDigits: 2 } : a >= 1000 ? { maximumFractionDigits: 2 } : a >= 1 ? { maximumFractionDigits: 4 } : { maximumSignificantDigits: 4 }
  return n.toLocaleString(locale(), opts).replace('-', '−')
}

/** Time-axis labels in the UI language (ECharts only knows English month names). ECharts
 * puts ticks on boundaries in local time: 1 January → the year, the 1st → the month, else
 * day and month. */
export function axisDate(ms: number): string {
  const d = new Date(ms)
  const fmt = (o: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat(locale(), o).format(d)
  // within a day (the 24-hour view): the clock
  if (d.getHours() || d.getMinutes()) return fmt({ hour: '2-digit', minute: '2-digit' })
  if (d.getDate() !== 1) return fmt({ day: 'numeric', month: 'short' })
  if (d.getMonth() === 0) return String(d.getFullYear())
  return fmt({ month: 'short' }).replace('.', '')
}

export function time(iso: string | null, timeZone?: string): string {
  if (!iso) return ''
  return new Intl.DateTimeFormat(locale(), { timeStyle: 'medium', timeZone }).format(new Date(iso))
}

/** Text for an HTML string (chart tooltips render their formatter output as HTML). */
export function html(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string)
}
