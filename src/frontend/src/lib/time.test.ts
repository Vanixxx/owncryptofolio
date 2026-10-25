import { describe, expect, it } from 'vitest'
import { typedTime } from './time'

describe('typedTime', () => {
  it('puts the colons in while typing forward', () => {
    expect(typedTime('1', '14')).toBe('14:')
    expect(typedTime('14:0', '14:05')).toBe('14:05:')
    expect(typedTime('14:05:3', '14:05:30')).toBe('14:05:30')
    expect(typedTime('', '140530')).toBe('14:05:30')
  })
  it('leaves deleting alone', () => {
    expect(typedTime('14:', '14')).toBe('14')
    expect(typedTime('14:05:', '14:05')).toBe('14:05')
  })
})
