import { Download } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from './ui'

/** "Export" with Excel or CSV: plain links, the browser downloads with the session cookie. */
export function ExportMenu({ path, params = {} }: { path: string; params?: Record<string, string | undefined> }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  // open towards the middle of the screen: a button on the left of a phone opened its
  // menu off the left edge (Vanixxx, 2026-10-06)
  const [alignRight, setAlignRight] = useState(true)
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])
  const href = (format: string) => {
    const q = new URLSearchParams({ format })
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') q.set(k, v)
    return `${path}?${q}`
  }
  return (
    <div ref={box} className="relative">
      <Button variant="ghost" aria-expanded={open} onClick={() => {
        const r = box.current?.getBoundingClientRect()
        setAlignRight(!r || r.left + r.width / 2 > window.innerWidth / 2)
        setOpen(!open)
      }}>
        <Download size={16} aria-hidden="true" />
        {/* a phone has room for "Export" next to Filter and Pick (Vanixxx, 2026-10-08) */}
        <span className="md:hidden">{t('export.short')}</span><span className="hidden md:inline">{t('export.button')}</span>
      </Button>
      {open && (
        <div className={`absolute ${alignRight ? 'right-0' : 'left-0'} z-30 mt-1 grid min-w-44 gap-0.5 rounded-ctl border border-line bg-surface p-1.5 shadow-xl`}>
          {(['xlsx', 'csv'] as const).map((f) => (
            <a key={f} href={href(f)} download onClick={() => setOpen(false)}
              className="rounded-ctl px-3 py-2 text-sm text-fg no-underline hover:bg-surface-2">{t(`export.${f}`)}</a>
          ))}
        </div>
      )}
    </div>
  )
}
