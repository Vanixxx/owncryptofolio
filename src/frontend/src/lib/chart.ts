import * as echarts from 'echarts/core'
import { useEffect, useRef, useState } from 'react'

/** Shared helpers of the ECharts charts (dashboard, statistics). */
export function token(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

export function rgba(color: string, alpha: number) {
  if (!color.startsWith('#')) return color
  const n = parseInt(color.slice(1), 16)
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`
}

/** `renderer: "svg"` for large charts: a canvas beyond ~16 million pixels stays blank on an
 * iPhone (a full source of funds flow at 3x pixel density, 2026-10-18). */
export function useChart(build: (chart: echarts.ECharts) => void, deps: unknown[], renderer: 'canvas' | 'svg' = 'canvas') {
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = box.current
    if (!el) return
    const chart = echarts.init(el, null, { renderer })
    build(chart)
    const resize = new ResizeObserver(() => chart.resize())
    resize.observe(el)
    // style or light/dark changed (also by the system): the colours are read from the CSS
    // tokens, so draw again (review 2026-10-25)
    const looks = new MutationObserver(() => requestAnimationFrame(() => { chart.clear(); build(chart) }))
    looks.observe(document.documentElement, { attributeFilter: ['data-style', 'data-mode', 'data-accent'] })
    return () => { resize.disconnect(); looks.disconnect(); chart.dispose() }
    // build is recreated each render; the data in deps decides
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return box
}

/** Counts changes of style, accent and light/dark (also by the system): a chart that draws
 * itself puts it in its deps to pick up the new colours (review 2026-10-25). */
export function useLooks(): number {
  const [n, setN] = useState(0)
  useEffect(() => {
    const looks = new MutationObserver(() => setN((x) => x + 1))
    looks.observe(document.documentElement, { attributeFilter: ['data-style', 'data-mode', 'data-accent'] })
    return () => looks.disconnect()
  }, [])
  return n
}

