import { LineChart, PieChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { locale } from '../../i18n'
import { axisDate, html, money } from '../../lib/format'
import { rgba, token, useChart, useLooks } from '../../lib/chart'

echarts.use([LineChart, PieChart, GridComponent, TooltipComponent, DataZoomComponent, CanvasRenderer])


export type ChartPoint = { t: number; value: number; deposited?: number; low?: number; high?: number }
/** low/high: the day's lowest and highest value, where 5-minute or hourly values exist
 * (ADR 0043) — drawn as a faint band around the line. */

const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches
const coarse = () => window.matchMedia('(pointer: coarse)').matches

/** The value over time (ADR 0031, "Verlauf"): the net deposit as a dashed step behind it —
 * above it is gain. A faint trace and the area are there at once, the bright line draws
 * itself in (0.7 s, glow in the neon style) when the range changes; live updates do not
 * restart it. Zoom: wheel and drag on a PC, two fingers on a phone (one finger shows the
 * values and the page keeps scrolling), the bar below everywhere. `onWindow` reports the
 * visible stretch, so the header can show its own change. */
export function ValueChart({ points, currency, intraday = false, drawKey, onWindow, window: start }: {
  points: ChartPoint[]; currency: string; intraday?: boolean; drawKey: string; onWindow?: (from: number, to: number) => void
  /** the stretch shown first; the rest is loaded and reachable with the time slider */
  window?: [number, number]
}) {
  const { t } = useTranslation()
  const box = useRef<HTMLDivElement>(null)
  const looks = useLooks()
  const chart = useRef<echarts.ECharts | null>(null)
  const drawn = useRef('')
  const report = useRef(onWindow)
  useEffect(() => { report.current = onWindow }, [onWindow])
  // The draw-in runs once the chart is on screen and laid out (phone, 2026-10-06: it ran
  // while the card was still settling, and the first resize cut it off — it looked as if
  // there were no effect at all).
  const option = useRef<echarts.EChartsCoreOption | null>(null)
  const pending = useRef(false)
  const visible = useRef(false)
  const scheduled = useRef(false)
  const runningUntil = useRef(0)
  const later = useRef(0)
  const prevLast = useRef<number | undefined>(undefined)
  const play = () => {
    const c = chart.current, el = box.current
    if (!c || !el || !pending.current || !visible.current || !el.clientWidth || !option.current || scheduled.current) return
    // on page load the browser is still busy (list, ring, numbers): a 0.7 s animation was
    // over before the first frame on a phone. Start when the page is idle (2026-10-06).
    scheduled.current = true
    const start = () => {
      scheduled.current = false
      const ch = chart.current
      if (!ch || !pending.current || !option.current) return
      pending.current = false
      runningUntil.current = performance.now() + 750
      ch.clear()
      ch.setOption({ ...option.current, animation: true }, { notMerge: true })
    }
    const idle = (window as Window & { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number }).requestIdleCallback
    if (idle) idle(() => requestAnimationFrame(start), { timeout: 800 })
    else window.setTimeout(() => requestAnimationFrame(start), 250)
  }

  useEffect(() => {
    const el = box.current
    if (!el) return
    const c = echarts.init(el, null, { renderer: 'canvas' })
    chart.current = c
    c.on('datazoom', () => {
      const dz = (c.getOption() as { dataZoom?: { startValue?: number; endValue?: number }[] }).dataZoom?.[0]
      if (dz?.startValue !== undefined && dz.endValue !== undefined) report.current?.(dz.startValue, dz.endValue)
    })
    let first = true
    const resize = new ResizeObserver(() => {
      if (first) { first = false; play(); return } // the initial report: nothing to resize yet
      c.resize()
    })
    resize.observe(el)
    const seen = new IntersectionObserver(([e]) => { visible.current = e.isIntersecting; play() }, { threshold: 0.4 })
    seen.observe(el)
    return () => { resize.disconnect(); seen.disconnect(); window.clearTimeout(later.current); c.dispose(); chart.current = null }
    // play reads refs only
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const c = chart.current
    if (!c) return
    const accent = token('--accent'), accent2 = token('--accent-2') || accent
    const muted = token('--muted'), line = token('--line'), fg = token('--fg'), surface = token('--surface-2')
    const width = Number(token('--chart-w')) || 2.4, glow = token('--glow') === '1', font = token('--f-num')
    const day = new Intl.DateTimeFormat(locale(), intraday ? { dateStyle: 'medium', timeStyle: 'short' } : { dateStyle: 'medium', timeZone: 'UTC' })
    const short = (v: number) => new Intl.NumberFormat(locale(), { notation: 'compact', maximumFractionDigits: 1 }).format(v)
    const hasDeposited = points.some((p) => p.deposited !== undefined)
    const byTime = new Map(points.map((p) => [p.t, p]))
    // the refresh every minute keeps where the user zoomed to; a new range starts at its window
    const kept = drawn.current === drawKey
      ? (c.getOption() as { dataZoom?: { startValue?: number; endValue?: number }[] } | undefined)?.dataZoom?.[0]
      : undefined
    const lastT = points.length ? points[points.length - 1].t : undefined
    // standing at the right edge, the window moves along with new values
    const atEnd = kept?.endValue !== undefined && prevLast.current !== undefined && kept.endValue >= prevLast.current
    const zoom = kept?.startValue !== undefined && kept.endValue !== undefined
      ? atEnd && lastT !== undefined
        ? { startValue: kept.startValue + (lastT - kept.endValue), endValue: lastT }
        : { startValue: kept.startValue, endValue: kept.endValue }
      : start ? { startValue: start[0], endValue: start[1] } : {}
    prevLast.current = lastT
    const hasBand = points.some((p) => p.low !== undefined && p.high !== undefined)
    // draw in only for a new range (or style), not for the minute-by-minute refresh
    const draw = drawn.current !== drawKey && !reducedMotion()
    drawn.current = drawKey
    // a later update (the summary arriving, a refresh) must neither cancel a draw-in that
    // waits nor cut off one that runs: on page load that swallowed it (2026-10-06)
    pending.current = pending.current || draw
    const touch = coarse()
    const next: echarts.EChartsCoreOption = {
      animation: false, animationDuration: 700, animationEasing: 'cubicOut', animationDurationUpdate: 0,
      textStyle: { fontFamily: font },
      grid: { left: 4, right: 44, top: 12, bottom: 46 },
      tooltip: {
        trigger: 'axis', confine: true, backgroundColor: surface, borderColor: line,
        textStyle: { color: fg, fontFamily: font, fontSize: 12 },
        axisPointer: { type: 'line', lineStyle: { color: muted, type: 'dashed' } },
        formatter: (ps: { value: [number, number] }[]) => {
          const p = byTime.get(ps[0]?.value[0])
          if (!p) return ''
          let html = `${day.format(new Date(p.t))}<br>${t('dashboard.value')}: <b>${money(String(p.value), currency)}</b>`
          if (p.low !== undefined && p.high !== undefined) {
            html += `<br><span style="color:${muted}">${t('dashboard.dayRange', { low: money(String(p.low), currency), high: money(String(p.high), currency) })}</span>`
          }
          if (p.deposited !== undefined) {
            const diff = p.value - p.deposited
            const pct = p.deposited > 0 ? (diff / p.deposited) * 100 : null
            const color = diff >= 0 ? token('--up') : token('--down')
            html += `<br><span style="color:${muted}">${t('dashboard.deposited')}: ${money(String(p.deposited), currency)}</span>`
            html += `<br><span style="color:${color}">${money(String(diff), currency, true)}${pct === null ? '' : ` · ${pct.toLocaleString(locale(), { maximumFractionDigits: 1 })} %`}</span>`
          }
          return html
        },
      },
      xAxis: {
        type: 'time', boundaryGap: false, axisLine: { lineStyle: { color: line } }, axisTick: { show: false },
        axisLabel: { color: muted, hideOverlap: true, fontSize: 10, formatter: axisDate }, splitLine: { show: false },
      },
      yAxis: {
        // a day moves a few percent: zoom in there, keep zero for the long view
        type: 'value', position: 'right', scale: intraday, min: intraday ? undefined : 0,
        axisLabel: { margin: 10, color: muted, fontSize: 10, formatter: short },
        splitLine: { lineStyle: { color: line } },
      },
      dataZoom: [
        { type: 'inside', ...zoom, zoomOnMouseWheel: true, moveOnMouseWheel: false, moveOnMouseMove: !touch,
          preventDefaultMouseMove: !touch, minValueSpan: intraday ? 3_600_000 : 5 * 86_400_000 },
        { type: 'slider', ...zoom, height: 22, bottom: 6, left: 4, right: 44, showDetail: false, brushSelect: false,
          minValueSpan: intraday ? 3_600_000 : 5 * 86_400_000, borderColor: line, backgroundColor: 'transparent',
          fillerColor: rgba(accent, 0.16), handleStyle: { color: accent, borderColor: accent },
          moveHandleStyle: { color: rgba(accent, 0.5) },
          dataBackground: { lineStyle: { color: muted, opacity: 0.5 }, areaStyle: { color: muted, opacity: 0.12 } },
          selectedDataBackground: { lineStyle: { color: accent }, areaStyle: { color: accent, opacity: 0.18 } } },
      ],
      series: [
        // static trace with the area, there at once; the bright line draws over it
        { name: 'trace', type: 'line', data: points.map((p) => [p.t, p.value]), showSymbol: false, animation: false,
          silent: true, tooltip: { show: false }, emphasis: { disabled: true }, z: 2,
          lineStyle: { width, color: rgba(accent, 0.28) },
          areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: rgba(accent, 0.24) }, { offset: 1, color: rgba(accent, 0) }]) } },
        { name: 'value', type: 'line', data: points.map((p) => [p.t, p.value]), showSymbol: false,
          emphasis: { disabled: true }, z: 3,
          lineStyle: {
            width,
            color: glow ? new echarts.graphic.LinearGradient(0, 0, 1, 0, [{ offset: 0, color: accent }, { offset: 1, color: accent2 }]) : accent,
            shadowBlur: glow ? 12 : 0, shadowColor: rgba(accent2, 0.7),
          } },
        // the day's low and high as a faint band (low invisible, span stacked on it); after the
        // value in the list, so the time slider keeps previewing the value
        ...(hasBand ? [
          { name: 'low', type: 'line', stack: 'band', data: points.map((p) => [p.t, p.low ?? null]), showSymbol: false,
            animation: false, silent: true, tooltip: { show: false }, lineStyle: { opacity: 0 }, emphasis: { disabled: true }, z: 1 },
          { name: 'band', type: 'line', stack: 'band', data: points.map((p) => [p.t, p.low !== undefined && p.high !== undefined ? p.high - p.low : null]),
            showSymbol: false, animation: false, silent: true, tooltip: { show: false }, lineStyle: { opacity: 0 },
            areaStyle: { color: rgba(accent2, 0.18) }, emphasis: { disabled: true }, z: 1 },
        ] : []),
        // last in the list: the time slider below previews the first series, which should be
        // the value, not the deposits (Vanixxx, 2026-10-12); z keeps it drawn underneath
        ...(hasDeposited ? [{ name: 'deposited', type: 'line', step: 'end', data: points.map((p) => [p.t, p.deposited]),
          showSymbol: false, animation: false, silent: true, tooltip: { show: false },
          lineStyle: { width: 1.4, color: muted, type: 'dashed' }, emphasis: { disabled: true }, z: 1 }] : []),
      ],
    }
    option.current = next
    // a draw-in waits for the chart to be on screen; without one the update is instant
    if (pending.current) { play(); return }
    window.clearTimeout(later.current)
    const wait = runningUntil.current - performance.now()
    if (wait > 0) later.current = window.setTimeout(() => chart.current?.setOption(option.current!, { notMerge: true }), wait)
    else c.setOption(next, { notMerge: true })
    // play reads refs only
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [points, currency, intraday, drawKey, t, start, looks])

  return <div ref={box} className="-mx-1 h-64 min-w-0 md:h-80" role="img" aria-label={t('dashboard.chartLabel')} />
}

export type Slice = { asset: string; value: number }

function palette() {
  // the accent first, then hues far from it and from each other; grey is the rest
  return [token('--accent'), '#f5a524', '#a855f7', '#17c964', '#f31260', '#3b82f6', '#eab308', '#94a3b8']
}

/** Share per coin as a ring; the colours run from the accent through the palette. */
export function Allocation({ slices, currency }: { slices: Slice[]; currency: string }) {
  const { t } = useTranslation()
  const box = useChart((chart) => {
    const fg = token('--fg'), line = token('--line'), surface = token('--surface-2'), bg = token('--surface')
    chart.setOption({
      color: palette(),
      tooltip: {
        trigger: 'item', confine: true, backgroundColor: surface, borderColor: line, textStyle: { color: fg, fontSize: 12 },
                // ECharts renders the text as HTML: a token symbol or wallet name from outside is
        // escaped, or `<img onerror=…>` would run (review 2026-10-25)
        formatter: (p: { name: string; value: number; percent: number }) => `${html(p.name)}<br><b>${money(String(p.value), currency)}</b> · ${p.percent.toLocaleString(locale(), { maximumFractionDigits: 1 })} %`,
      },
      series: [{
        type: 'pie', radius: ['58%', '86%'], avoidLabelOverlap: true, label: { show: false },
        itemStyle: { borderColor: bg, borderWidth: 2, borderRadius: 4 },
        data: slices.map((s) => ({ name: s.asset, value: s.value })),
      }],
    })
  }, [slices, currency])
  const colors = palette()
  const total = slices.reduce((n, s) => n + s.value, 0) || 1
  return (
    <div className="flex flex-wrap items-center gap-4">
      <div ref={box} className="h-40 w-40 shrink-0" role="img" aria-label={t('dashboard.allocation')} />
      <ul className="m-0 grid min-w-40 flex-1 list-none gap-1.5 p-0 text-sm">
        {slices.map((s, i) => (
          <li key={s.asset} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: colors[i % colors.length] }} aria-hidden="true" />
            <span className="flex-1 truncate">{s.asset}</span>
            <span className="num text-muted">{((s.value / total) * 100).toLocaleString(locale(), { maximumFractionDigits: 1 })} %</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
