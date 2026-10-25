/** Time as typed, with the colons put in (Vanixxx, 2026-10-08): "14" → "14:", "14:05" →
 * "14:05:"; only when typing forward, so deleting a colon still works. */
export function typedTime(before: string, now: string): string {
  const clean = now.replace(/[^\d:]/g, '').slice(0, 8)
  if (clean.length <= before.length) return clean
  const digits = clean.replace(/:/g, '')
  const parts = [digits.slice(0, 2), digits.slice(2, 4), digits.slice(4, 6)].filter(Boolean)
  let out = parts.join(':')
  if ((digits.length === 2 || digits.length === 4) && digits.length < 6) out += ':'
  return out
}
