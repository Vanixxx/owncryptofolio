/** Every typed word must occur somewhere in the texts ("tangem eth" finds "Tangem – Ethereum"). */
export function matches(query: string, ...texts: (string | null | undefined)[]): boolean {
  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean)
  if (words.length === 0) return true
  const text = texts.filter(Boolean).join(' ').toLowerCase()
  return words.every((w) => text.includes(w))
}
