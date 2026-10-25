import { describe, expect, it, vi } from 'vitest'

vi.mock('../i18n', () => ({ locale: () => 'de-DE' }))
const { amount, axisDate, date, dateTime, html, money, quantity } = await import('./format')

describe('amount', () => {
  it('keeps all digits without float rounding', () => {
    expect(amount('1234567.123456789012345678', 18)).toBe('1.234.567,123456789012345678')
  })
  it('trims trailing zeros and cuts long fractions visibly', () => {
    expect(amount('0.500000')).toBe('0,5')
    expect(amount('0.123456789')).toBe('0,12345678…')
  })
  it('handles negatives and integers', () => {
    expect(amount('-42')).toBe('−42')
    expect(amount(null)).toBe('')
  })
})

describe('dateTime', () => {
  it('shows seconds in the given time zone', () => {
    expect(dateTime('2024-03-15T13:05:07Z', 'Europe/Berlin')).toBe('15.03.2024, 14:05:07')
  })
})

describe('priceText', () => {
  it('two decimals from 1 €, significant digits below, exponent for dust', async () => {
    const { priceText: raw } = await import('./format')
    const priceText = (v: number) => raw(v).replace(/\u00a0/g, ' ')  // Intl puts a no-break space before €
    expect(priceText(75590.1)).toBe('75.590,10 €')
    expect(priceText(0.89071234)).toBe('0,8907 €')
    expect(priceText(0.00000056)).toBe('5.60e-7 €')
  })
})

describe('axisDate', () => {
  it('year, month or day as the tick falls', () => {
    expect(axisDate(new Date(2026, 0, 1).getTime())).toBe('2026')
    expect(axisDate(new Date(2026, 2, 1).getTime())).toMatch(/^M/)
    expect(axisDate(new Date(2026, 2, 15).getTime())).toMatch(/15/)
  })
})

describe('quantity', () => {
  it('few decimals for big amounts, significant digits for small ones', () => {
    expect(quantity('48758.976599607455')).toBe('48.758,98')
    expect(quantity('73.0341583')).toBe('73,0342')
    expect(quantity('0.00000017')).toBe('0,00000017')
    expect(quantity('-5.5')).toBe('−5,5')
    expect(quantity('448065842.11')).toBe('448,07\u00a0Mio.')
  })
})

describe('money', () => {
  it('keeps the sign on the amount so a line cannot break after it', () => {
    expect(money('14596.19', 'EUR', true)).toBe('+\u206014.596,19\u00a0€')
    expect(money('-36024.84', 'EUR')).toBe('-\u206036.024,84\u00a0€')
    expect(money('5', 'EUR')).toBe('5,00\u00a0€')
  })
})

describe('html', () => {
  it('escapes what a token name could smuggle into a chart tooltip', () => {
    expect(html('<img src=x onerror="alert(1)">')).toBe('&lt;img src=x onerror=&quot;alert(1)&quot;&gt;')
    expect(html('BTC')).toBe('BTC')
  })
})

describe('date', () => {
  it('shows a plain day as that day whatever the zone', () => {
    expect(date('2027-03-15', 'America/Los_Angeles')).toBe('15.03.2027')
    expect(date('2027-03-15T05:00:00Z', 'America/Los_Angeles')).toBe('14.03.2027')
  })
})

