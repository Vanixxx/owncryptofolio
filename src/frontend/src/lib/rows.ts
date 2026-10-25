import type { TFunction } from 'i18next'
import type { RawRow } from './api'
import { amount } from './format'

export function side([asset, value]: [string | null, string | null], sign: string) {
  return asset && value ? `${sign}${amount(value)} ${asset}` : ''
}

export function kindLabel(t: TFunction, r: RawRow) {
  const base = t(`kinds.${r.kind}`, { defaultValue: r.kind })
  // an income says what it was: "Ertrag · Staking" (Vanixxx, 2026-10-08)
  const kind = r.kind === 'income' && r.income_kind ? `${base} · ${t(`manual.income.${r.income_kind}`, { defaultValue: r.income_kind })}` : base
  return r.market === 'futures' ? `${kind} · ${r.instrument ?? 'Futures'}` : kind
}
/** The icon key of a row: an income names its kind. */
export function iconKind(r: { kind: string; income_kind?: string | null }) {
  return r.kind === 'income' ? `income:${r.income_kind ?? ''}` : r.kind
}
