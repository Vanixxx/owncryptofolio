export type Sort<K extends string> = { key: K; desc: boolean }

/** Compares with missing values always last, whatever the direction. */
export function compare(a: number | string | null, b: number | string | null, desc: boolean): number {
  if (a === null && b === null) return 0
  if (a === null) return 1
  if (b === null) return -1
  const r = typeof a === 'string' && typeof b === 'string' ? a.localeCompare(b) : Number(a) - Number(b)
  return desc ? -r : r
}
