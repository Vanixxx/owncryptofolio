import { describe, expect, it } from 'vitest'
import de from './locales/de.json'
import en from './locales/en.json'

type Tree = { [k: string]: string | Tree }

function keys(tree: Tree, prefix = ''): string[] {
  return Object.entries(tree).flatMap(([k, v]) =>
    typeof v === 'string' ? [prefix + k] : keys(v, `${prefix}${k}.`),
  )
}

function placeholders(tree: Tree): Record<string, string[]> {
  const out: Record<string, string[]> = {}
  const walk = (t: Tree, p: string) =>
    Object.entries(t).forEach(([k, v]) =>
      typeof v === 'string' ? (out[p + k] = [...v.matchAll(/{{(\w+)}}/g)].map((m) => m[1]).sort()) : walk(v, `${p}${k}.`),
    )
  walk(tree, '')
  return out
}

describe('translations', () => {
  it('every language has exactly the same keys as German', () => {
    const base = new Set(keys(de))
    const other = new Set(keys(en))
    expect([...base].filter((k) => !other.has(k)), 'missing in en').toEqual([])
    expect([...other].filter((k) => !base.has(k)), 'only in en').toEqual([])
  })

  it('placeholders match between languages', () => {
    const a = placeholders(de)
    const b = placeholders(en)
    const diff = Object.keys(a).filter((k) => JSON.stringify(a[k]) !== JSON.stringify(b[k]))
    expect(diff).toEqual([])
  })

  it('no translation is empty', () => {
    // each language checked against itself (review 2026-10-25: English was looked up in German)
    const blank = (tree: Tree) => keys(tree).filter((k) =>
      k.split('.').reduce<Tree | string>((t, p) => (t as Tree)[p], tree) === '')
    const empty = [...blank(de as Tree).map((k) => `de:${k}`), ...blank(en as Tree).map((k) => `en:${k}`)]
    expect(empty).toEqual([])
  })
})
