import { useState } from 'react'
import type { Sort } from '../lib/sort'

/** A sort that stays as it was left (Vanixxx, 2026-10-05): per browser in localStorage, a
 * convenience only. Private mode or blocked storage: the default, nothing breaks. A stored
 * key that no longer exists falls back to the default too. */
export function useStoredSort<K extends string>(key: string, initial: Sort<K>, keys: readonly K[]) {
  const [sort, setSort] = useState<Sort<K>>(() => {
    try {
      const v = JSON.parse(localStorage.getItem(key) ?? 'null') as Sort<K> | null
      if (v && keys.includes(v.key) && typeof v.desc === 'boolean') return v
    } catch { /* unreadable: default */ }
    return initial
  })
  const set = (s: Sort<K>) => {
    setSort(s)
    try { localStorage.setItem(key, JSON.stringify(s)) } catch { /* private mode: fine */ }
  }
  return [sort, set] as const
}
