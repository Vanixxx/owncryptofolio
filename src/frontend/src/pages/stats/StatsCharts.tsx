import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { useTranslation } from 'react-i18next'
import { locale } from '../../i18n'
import { axisDate, money } from '../../lib/format'
import { rgba, token, useChart } from '../../lib/chart'

echarts.use([BarChart, LineChart, PieChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

/** "var(--up)" → the colour itself: the canvas cannot read CSS variables. */
const paint = (c?: string) => (c?.startsWith('var(') ? token(c.slice(4, -1)) : c)
const short = (v: number) => new Intl.NumberFormat(locale(), { notation: 'compact', maximumFractionDigits: 1 }).format(v)
function colors() {
  return [token('--accent'), '#f5a524', '#a855f7', '#17c964', '#f31260', '#3b82f6', '#eab308', '#94a3b8']
}

function base(currency: string | null) {
  const muted = token('--muted'), line = token('--line'), fg = token('--fg'), surface = token('--surface-2')
  return {
    textStyle: { fontFamily: token('--f-num') },
    grid: { left: 4, right: 44, top: 28, bottom: 24 },
    legend: { type: 'scroll', top: 0, left: 0, right: 44, pageIconColor: token('--accent'), pageTextStyle: { color: token('--muted') }, textStyle: { color: muted, fontSize: 11 }, itemWidth: 12, itemHeight: 8 },
    tooltip: {
      trigger: 'axis', confine: true, backgroundColor: surface, borderColor: line,
      textStyle: { color: fg, fontSize: 12 },
      valueFormatter: (v: number) => (currency ? money(String(v), currency) : v.toLocaleString(locale())),
    },
    yAxis: { type: 'value', position: 'right', axisLabel: { color: muted, fontSize: 10, formatter: short }, splitLine: { lineStyle: { color: line } } },
    muted, line,
  }
}

/** Bars per category (month, year), stacked by series where `stack` is set. */
export function Bars({ categories, series, currency, label }: {
  categories: string[]; series: { name: string; data: (number | null)[]; stack?: string; color?: string }[]
  /** null: plain counts */
  currency: string | null; label: string
}) {
  const box = useChart((chart) => {
    const b = base(currency)
    const pal = colors()
    chart.setOption({
      ...b, color: pal,
      xAxis: { type: 'category', data: categories, axisLine: { lineStyle: { color: b.line } }, axisTick: { show: false }, axisLabel: { color: b.muted, fontSize: 10 } },
      series: series.map((s) => ({ type: 'bar', name: s.name, data: s.data, stack: s.stack, itemStyle: s.color ? { color: paint(s.color) } : undefined, barMaxWidth: 28, emphasis: { disabled: true } })),
    })
  }, [categories, series, currency])
  return <div ref={box} className="h-56 min-w-0 md:h-64" role="img" aria-label={label} />
}

/** Lines over time: [ms, value] per series; the first is drawn bright with an area. */
export function Lines({ series, currency, label }: {
  series: { name: string; points: [number, number][]; dashed?: boolean; color?: string }[]; currency: string; label: string
}) {
  const { t } = useTranslation()
  const box = useChart((chart) => {
    const b = base(currency)
    const accent = token('--accent')
    chart.setOption({
      ...b,
      xAxis: { type: 'time', axisLine: { lineStyle: { color: b.line } }, axisTick: { show: false }, axisLabel: { color: b.muted, fontSize: 10, hideOverlap: true, formatter: axisDate }, splitLine: { show: false } },
      series: series.map((s, i) => ({
        type: 'line', name: s.name, data: s.points, showSymbol: false, emphasis: { disabled: true }, step: s.dashed ? 'end' : undefined,
        lineStyle: { width: s.dashed ? 1.4 : 2, type: s.dashed ? 'dashed' : 'solid', color: paint(s.color) ?? (i === 0 ? accent : undefined) },
        itemStyle: { color: paint(s.color) ?? (i === 0 ? accent : undefined) },
        areaStyle: i === 0 ? { color: rgba(accent, 0.12) } : undefined,
      })),
    })
  }, [series, currency, t])
  return <div ref={box} className="h-64 min-w-0 md:h-80" role="img" aria-label={label} />
}

/** A ring of counts; empty means all is well and the ring is drawn whole in green. */
export function Ring({ slices, label, className = 'h-36 w-36' }: { slices: { name: string; value: number; color: string }[]; label: string; className?: string }) {
  const box = useChart((chart) => {
    const surface = token('--surface-2'), line = token('--line'), fg = token('--fg'), bg = token('--surface')
    const ok = slices.every((s) => !s.value)
    chart.setOption({
      tooltip: ok ? { show: false } : { trigger: 'item', confine: true, backgroundColor: surface, borderColor: line, textStyle: { color: fg, fontSize: 12 } },
      series: [{
        type: 'pie', radius: ['58%', '86%'], label: { show: false }, silent: ok,
        itemStyle: { borderColor: bg, borderWidth: 2, borderRadius: 4 },
        data: ok ? [{ name: 'ok', value: 1, itemStyle: { color: token('--up') } }]
          : slices.filter((s) => s.value).map((s) => ({ name: s.name, value: s.value, itemStyle: { color: paint(s.color) } })),
      }],
    })
  }, [slices])
  return <div ref={box} className={`${className} shrink-0`} role="img" aria-label={label} />
}
