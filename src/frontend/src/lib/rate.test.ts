import { describe, expect, it } from 'vitest'
import { tradeRate } from './rate'

describe('tradeRate', () => {
  it('prices the coin in the money side, whichever way the trade went', () => {
    expect(tradeRate(['BTC', '0.01'], ['USDT', '258.48'])).toMatchObject({ base: 'BTC', quote: 'USDT', baseSide: 'incoming' })
    expect(tradeRate(['BTC', '0.01'], ['USDT', '258.48'])!.price).toBeCloseTo(25848)
    expect(tradeRate(['EUR', '100'], ['ETH', '0.05'])).toMatchObject({ base: 'ETH', quote: 'EUR', baseSide: 'outgoing', price: 2000 })
    expect(tradeRate(['ADA', '1000'], ['BTC', '0.01'])).toMatchObject({ base: 'ADA', quote: 'BTC' })
    expect(tradeRate(['BTC', null], ['USDT', '1'])).toBeNull()
  })
})
