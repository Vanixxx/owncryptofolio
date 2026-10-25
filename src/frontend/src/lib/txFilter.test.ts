import { describe, expect, it } from 'vitest'
import { expandQuery } from './txFilter'

const de: Record<string, string> = {
  'kinds.send': 'Senden', 'kinds.fee': 'Gebühr', 'merged.transfer': 'Transfer', 'merged.filters.dust': 'Staub?',
  'merged.filters.edited': 'Bearbeitet', 'pages.transactions.spot': 'Spot', 'pages.transactions.futures': 'Futures',
}
const t = (k: string) => de[k] ?? k

describe('expandQuery', () => {
  it('adds the keys of the page words a typed word is part of', () => {
    expect(expandQuery('Staub slp', t)).toBe('staub|dust slp')
    expect(expandQuery('futures 04.10.2026', t)).toBe('futures|futures_position|futures 04.10.2026')
    expect(expandQuery('send', t)).toBe('send|send')
  })
  it('leaves short words and an empty search alone', () => {
    expect(expandQuery('ab', t)).toBe('ab')
    expect(expandQuery('   ', t)).toBeUndefined()
  })
})
