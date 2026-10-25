import { LineChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import type { PricePoint } from '../../lib/api'
import { locale } from '../../i18n'
import { axisDate, priceText } from '../../lib/format'
import { useLooks } from '../../lib/chart'

echarts.use([LineChart, GridComponent, TooltipComponent, DataZoomComponent, CanvasRenderer])

const DAY = 86_400_000

function token(name: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

function rgba(color: string, alpha: number) {
  if (!color.startsWith('#')) return color
  const n = parseInt(color.slice(1), 16)
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`
}

/** The design-draft chart (2026-10-02): faint trace with area at once, the bright line
 * draws itself in over 0.7 s (glow in the neon style), daily high/low as a band behind it
 * (without it a day with 31 % swing looks flat), zoom and a slider. Display only. */
export function PriceChart({ points, currency, steps }: {
  points: PricePoint[]; currency: 'EUR' | 'USD'
  /** a dashed step line, e.g. the average buying price as it changed with every buy
   * (holdings page, Vanixxx 2026-10-08); a null value while none was held */
  steps?: { label: string; points: { day: string; value: string | null }[] }
}) {
  const { t } = useTranslation()
  const box = useRef<HTMLDivElement>(null)

  const looks = useLooks()  // new colours after a style or light/dark change
  useEffect(() => {
    const el = box.current
    if (!el || points.length === 0) return
    const chart = echarts.init(el, null, { renderer: 'canvas' })
    const accent = token('--accent'), accent2 = token('--accent-2') || accent
    const muted = token('--muted'), line = token('--line'), fg = token('--fg'), surface = token('--surface-2')
    const width = Number(token('--chart-w')) || 2.4, glow = token('--glow') === '1'
    const font = token('--f-num')
    const time = (p: PricePoint) => new Date(`${p.day}T00:00:00Z`).getTime()
    const close = points.map((p) => [time(p), Number(p.close)])
    const low = points.map((p) => [time(p), Number(p.low ?? p.close)])
    const spread = points.map((p) => [time(p), Number(p.high ?? p.close) - Number(p.low ?? p.close)])
    const day = new Intl.DateTimeFormat(locale(), { dateStyle: 'medium', timeZone: 'UTC' })
    const bySource = new Map(points.map((p) => [time(p), p]))
    // the step value valid on each price day: the latest change up to that day
    const changes = (steps?.points ?? []).map((s) => [new Date(`${s.day}T00:00:00Z`).getTime(), s.value === null ? null : Number(s.value)] as const)
    const stepAt = (at: number) => {
      let v: number | null = null
      for (const [t0, x] of changes) { if (t0 <= at) v = x; else break }
      return v
    }
    const stepLine = steps ? points.map((p) => [time(p), stepAt(time(p))]) : []
    const stepValues = stepLine.map(([, v]) => v).filter((v): v is number => v !== null)
    chart.setOption({
      animationDuration: 700, animationEasing: 'cubicOut', animationDurationUpdate: 300,
      textStyle: { fontFamily: font },
      grid: { left: 4, right: 40, top: 14, bottom: 46 },
      tooltip: {
        trigger: 'axis', confine: true, backgroundColor: surface, borderColor: line,
        textStyle: { color: fg, fontFamily: font, fontSize: 12 },
        axisPointer: { type: 'line', lineStyle: { color: muted, type: 'dashed' } },
        formatter: (ps: { value: [number, number] }[]) => {
          const at = ps[0]?.value[0]
          const p = bySource.get(at)
          if (!p) return ''
          const range = p.high && p.low ? `<br><span style="color:${muted}">${t('prices.range')} ${priceText(Number(p.low), currency)} – ${priceText(Number(p.high), currency)}</span>` : ''
          const step = steps ? stepAt(at) : null
          const stepRow = step !== null && steps ? `<br>${steps.label} ${priceText(step, currency)}` : ''
          return `${day.format(new Date(at))}<br><b>${priceText(Number(p.close), currency)}</b>${range}${stepRow}<br><span style="color:${muted}">${t(`prices.sources.${p.source}`, { defaultValue: p.source })}</span>`
        },
      },
      xAxis: {
        type: 'time', boundaryGap: false, axisLine: { lineStyle: { color: line } }, axisTick: { show: false },
        axisLabel: { color: muted, hideOverlap: true, fontSize: 10, formatter: axisDate }, splitLine: { show: false },
      },
      yAxis: {
        type: 'value', position: 'right', scale: true,
        // the level stays in view even when the price ran far away from it
        ...(stepValues.length ? { min: (v: { min: number }) => Math.min(v.min, ...stepValues), max: (v: { max: number }) => Math.max(v.max, ...stepValues) } : {}),
        axisLabel: { margin: 10, color: muted, fontSize: 10, formatter: (v: number) => (Math.abs(v) >= 1000
          // big prices: whole numbers on the axis, "110.000" not "110.000,00" (2026-10-12)
          ? new Intl.NumberFormat(locale(), { maximumFractionDigits: 0 }).format(v)
          : priceText(v, currency).replace(/\s?€|\s?\$/, '')) },
        splitLine: { lineStyle: { color: line } },
      },
      dataZoom: [
        { type: 'inside', zoomOnMouseWheel: true, moveOnMouseWheel: false, minValueSpan: 5 * DAY },
        {
          type: 'slider', height: 22, bottom: 6, left: 4, right: 40, minValueSpan: 5 * DAY, showDetail: false,
          brushSelect: false, borderColor: line, backgroundColor: 'transparent', fillerColor: rgba(accent, 0.16),
          handleStyle: { color: accent, borderColor: accent }, moveHandleStyle: { color: rgba(accent, 0.5) },
          dataBackground: { lineStyle: { color: muted, opacity: 0.5 }, areaStyle: { color: muted, opacity: 0.12 } },
          selectedDataBackground: { lineStyle: { color: accent }, areaStyle: { color: accent, opacity: 0.18 } },
        },
      ],
      series: [
        // band: low (invisible) + spread stacked on it, filled — drawn behind everything
        { name: 'low', type: 'line', data: low, stack: 'band', showSymbol: false, silent: true, animation: false,
          lineStyle: { opacity: 0 }, tooltip: { show: false }, emphasis: { disabled: true }, z: 0 },
        { name: 'band', type: 'line', data: spread, stack: 'band', showSymbol: false, silent: true, animation: false,
          lineStyle: { opacity: 0 }, areaStyle: { color: rgba(muted, 0.14) }, tooltip: { show: false }, emphasis: { disabled: true }, z: 0 },
        // static ghost: faint line plus area at once; the bright line draws over it
        { name: 'trace', type: 'line', data: close, showSymbol: false, animation: false, silent: true, tooltip: { show: false },
          lineStyle: { width, color: rgba(accent, 0.28) },
          areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: rgba(accent, 0.22) }, { offset: 1, color: rgba(accent, 0) }]) },
          emphasis: { disabled: true }, z: 1 },
        { name: 'close', type: 'line', data: close, showSymbol: false, emphasis: { disabled: true }, z: 3,

          lineStyle: {
            width,
            color: glow ? new echarts.graphic.LinearGradient(0, 0, 1, 0, [{ offset: 0, color: accent }, { offset: 1, color: accent2 }]) : accent,
            shadowBlur: glow ? 12 : 0, shadowColor: rgba(accent2, 0.7),
          } },
        ...(steps ? [{
          name: 'steps', type: 'line', step: 'end', data: stepLine, showSymbol: false, animation: false, silent: true, z: 2,
          tooltip: { show: false }, emphasis: { disabled: true }, connectNulls: false,
          lineStyle: { color: fg, type: 'dashed', width: 1.2, opacity: 0.75 },
          endLabel: { show: stepLine.at(-1)?.[1] != null, color: fg, fontSize: 10, offset: [-4, -10], align: 'right',
            formatter: () => `${steps.label} ${priceText(Number(stepLine.at(-1)?.[1]), currency)}` },
        }] : []),
      ],
    })
    const resize = new ResizeObserver(() => chart.resize())
    resize.observe(el)
    return () => { resize.disconnect(); chart.dispose() }
    // the steps' content decides, not the object made anew on every render
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [points, currency, JSON.stringify(steps), t, looks])

  // min-width 0 and a slight negative margin: the chart reaches into the card padding
  // instead of looking indented, and still shrinks with its grid (webui pitfall 2026-10-02)
  return <div ref={box} className="-mx-2.5 h-64 min-w-0 md:h-72" role="img" aria-label={t('prices.chartLabel')} />
}
