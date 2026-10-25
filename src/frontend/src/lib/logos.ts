import { useSyncExternalStore } from 'react'
import { api } from './api'

export type LogoKind = 'wallet' | 'source' | 'coin'

/** Which own logos exist (fetched once, again after an upload): kind/key → version. */
let versions: Record<string, number> = {}
let loaded = false
const listeners = new Set<() => void>()

export function reloadLogos() {
  loaded = true
  api.logos().then((list) => {
    versions = Object.fromEntries(list.map((l) => [`${l.kind}/${l.key}`, l.v]))
    listeners.forEach((l) => l())
  }, () => {})
}

function subscribe(l: () => void) {
  if (!loaded) reloadLogos()
  listeners.add(l)
  return () => { listeners.delete(l) }
}

/** The URL of an own logo, or null: the built-in one is used then. */
export function useLogoUrl(kind: LogoKind, key: string | number | undefined | null): string | null {
  const id = key === undefined || key === null ? null : `${kind}/${kind === 'coin' ? String(key).toUpperCase() : key}`
  const v = useSyncExternalStore(subscribe, () => (id ? versions[id] : undefined))
  return id && v ? `/api/logos/${id}?v=${v}` : null
}
