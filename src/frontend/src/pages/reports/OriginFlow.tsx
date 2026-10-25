import { SankeyChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { SVGRenderer } from 'echarts/renderers'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { OriginFlowData, OriginFlowNode } from '../../lib/api'
import { token, useChart } from '../../lib/chart'
import { date, money, quantity } from '../../lib/format'

echarts.use([SankeyChart, TooltipComponent, SVGRenderer])

const LEAF_COLOR: Record<string, string> = {
  bank: '--accent', card: '#8b7cf6', gain: '--up', income: '#e0a33a', futures: '#3aa7e0',
  unknown: '--warn', money_unknown: '--down', loss: '--down',
}

/** The chain as a flow (ADR 0046): origins left, the step right, losses flowing out. The
 * full flow draws every step; it grows tall, so the box scrolls. */
export function OriginFlow({ data, full, tz }: { data: OriginFlowData; full: boolean; tz: string }) {
  const { t } = useTranslation()
  const color = (k: string) => {
    const c = LEAF_COLOR[k]
    return c?.startsWith('--') ? token(c) : c ?? token('--muted')
  }
  const name = (n: OriginFlowNode): string => {
    if (n.kind === 'root') return t('origin.flow.root')
    if (n.detail === 'small') return t('origin.flow.small', { kind: t(`origin.leaf.${n.kind}`) })
    if (n.detail === 'until_transfer') return t(n.kind === 'gain' ? 'origin.gainUntilTransfer' : 'origin.lossUntilTransfer')
    if (n.kind in LEAF_COLOR && !full) return t(`origin.leaf.${n.kind}`)
    if (!full) return `${n.place ?? t('holdings.outside')}`
    const kind = n.detail === 'direct' ? t(`origin.direct.${n.kind}`) : t(`origin.leaf.${n.kind}`, { defaultValue: t(`origin.kinds.${n.kind}`, { defaultValue: n.kind }) })
    return n.qty && Number(n.qty) && n.kind !== 'gain' && n.kind !== 'loss' ? `${kind} ${quantity(n.qty)} ${n.asset}` : kind
  }
  const sub = (n: OriginFlowNode): string => {
    if (!full) {
      if (n.kind === 'stay') return `${date(n.from ?? null, tz)}${n.from?.slice(0, 10) !== n.to?.slice(0, 10) ? ` – ${date(n.to ?? null, tz)}` : ''} · ${t('origin.steps', { count: n.count ?? 0 })}`
      return ''
    }
    return `${n.place ?? ''}${n.at ? ` · ${date(n.at, tz)}` : ''}`
  }
  // the column of each box set here, not left to ECharts (Vanixxx, 2026-10-18: a price gain
  // drawn far left ran through every other step): steps by their longest way from the
  // start, an origin right before the step it feeds, a loss right after its step
  const { depth, columns, rows } = useMemo(() => {
    const kind = new Map(data.nodes.map((n) => [n.id, n.kind]))
    const leaf = (id: string) => (kind.get(id) ?? '') in LEAF_COLOR
    const ins = new Map<string, string[]>(), outs = new Map<string, string[]>()
    for (const l of data.links) {
      ins.set(l.target, [...(ins.get(l.target) ?? []), l.source])
      outs.set(l.source, [...(outs.get(l.source) ?? []), l.target])
    }
    const depth = new Map<string, number>()
    const walk = (id: string, seen: Set<string>): number => {
      const known = depth.get(id)
      if (known !== undefined) return known
      if (seen.has(id)) return 1
      seen.add(id)
      const d = Math.max(0, ...(ins.get(id) ?? []).filter((p) => !leaf(p)).map((p) => walk(p, seen))) + 1
      depth.set(id, d)
      return d
    }
    for (const n of data.nodes) if (!leaf(n.id)) walk(n.id, new Set())
    for (const n of data.nodes) {
      if (!leaf(n.id)) continue
      const after = (ins.get(n.id) ?? []).map((p) => depth.get(p) ?? 1)
      const before = (outs.get(n.id) ?? []).map((c) => depth.get(c) ?? 1)
      // a box without any link stays in the first column (it once got column 1e9: a page
      // 33 million pixels wide that no phone draws)
      depth.set(n.id, after.length ? Math.max(...after) + 1 : before.length ? Math.max(0, Math.min(...before) - 1) : 0)
    }
    const per = new Map<number, number>()
    for (const d of depth.values()) per.set(d, (per.get(d) ?? 0) + 1)
    return { depth, columns: Math.max(1, ...depth.values()) + 1, rows: Math.max(1, ...per.values()) }
  }, [data])
  // ECharts packs columns its own way: by the fullest column and by all boxes together
  const height = Math.max(320, rows * (full ? 40 : 64) + 40, data.nodes.length * (full ? 14 : 34))
  // the full flow keeps room for its labels; the simple one needs less and fits a PC screen,
  // on a phone it scrolls sideways (Vanixxx, 2026-10-18)
  // on a phone the simple flow gets narrow columns and short labels: most of it in view
  // without scrolling (Vanixxx, 2026-10-18: the start showed only the inflows)
  // the full one too, a bit wider: its labels name each step (tap shows all of it)
  const phone = typeof window !== 'undefined' && window.innerWidth < 640
  const width = full ? (phone ? columns * 110 + 110 : columns * 230 + 200) : phone ? columns * 75 + 40 : columns * 170 + 140
  const [tip, setTip] = useState<{ x: number; y: number; lines: string[] } | null>(null)
  const box = useChart((chart) => {
    const fg = token('--fg'), muted = token('--muted')
    const byId = new Map(data.nodes.map((n) => [n.id, n]))
    chart.setOption({
      animation: false,
      // our own tooltip below: ECharts' one was cut off by the scrolling box, and laid onto the
      // page it landed hundreds of px off on a phone (the app scrolls in an inner box)
      tooltip: { show: false },
      series: [{
        type: 'sankey',
        left: 4, right: full ? (phone ? 100 : 200) : phone ? 64 : 130, top: 12, bottom: 12,
        nodeWidth: phone ? 8 : 12, nodeGap: full ? (phone ? 10 : 12) : 22, layoutIterations: 64,
        // a box in the way can be dragged aside
        draggable: true,
        emphasis: { focus: 'adjacency' },
        data: data.nodes.map((n) => ({
          name: n.id, id: n.id, depth: depth.get(n.id) ?? 0,
          // the goal in the text colour: it must not look like a bank deposit (Vanixxx, 2026-10-18)
          itemStyle: { color: n.kind === 'root' || n.goal ? fg : n.kind in LEAF_COLOR ? color(n.kind) : muted, borderWidth: 0 },
          label: {
            color: fg, fontSize: phone ? (full ? 9 : 10) : full ? 11 : 12, width: phone ? (full ? 95 : 70) : 190, overflow: 'truncate',
            // readable over the flows running behind it
            textBorderColor: token('--surface'), textBorderWidth: 3,
            formatter: () => (full ? name(n) : phone ? `{p|${name(n)}}` : `{b|${name(n)}}\n{s|${sub(n)}}`),
            rich: {
              b: { color: fg, fontSize: 12, fontWeight: 600, textBorderColor: token('--surface'), textBorderWidth: 3 },
              s: { color: muted, fontSize: 10, textBorderColor: token('--surface'), textBorderWidth: 3 },
              p: { color: fg, fontSize: 10, fontWeight: 600, width: 70, overflow: 'truncate', textBorderColor: token('--surface'), textBorderWidth: 3 },
            },
          },
        })),
        links: data.links.map((l) => ({
          source: l.source, target: l.target, value: Number(l.value),
          lineStyle: { color: l.loss ? token('--down') : 'gradient', opacity: l.loss ? 0.45 : 0.3, curveness: 0.5 },
        })),
      }],
    })
    const show = (e: unknown) => {
      const p = e as { dataType?: string; data: { source?: string; target?: string; value?: number; id?: string }; event?: { event?: Event } }
      const ev = p.event?.event as (MouseEvent & TouchEvent) | undefined
      const touch = ev?.changedTouches?.[0]
      const x = touch?.clientX ?? ev?.clientX, y = touch?.clientY ?? ev?.clientY
      if (x === undefined || y === undefined) return
      let lines: string[] = []
      if (p.dataType === 'edge') {
        const a = byId.get(p.data.source ?? ''), b = byId.get(p.data.target ?? '')
        lines = [`${a ? name(a) : ''} → ${b ? name(b) : ''}`, money(String(p.data.value))]
      } else {
        const n = byId.get(p.data.id ?? '')
        if (n) lines = [name(n), sub(n)].filter(Boolean)
      }
      setTip(lines.length ? { x, y, lines } : null)
    }
    chart.on('mouseover', show)
    chart.on('click', show)
    chart.on('mouseout', () => setTip(null))
    chart.on('globalout', () => setTip(null))
  }, [data, full, tz, height, depth, phone], 'svg')
  return (
    // the simple flow fits the width; only the full one may scroll
    <div className={full ? 'max-h-[75vh] overflow-auto rounded-ctl bg-surface-2/40' : 'overflow-x-auto'} onScroll={() => setTip(null)}>
      <div ref={box} style={{ height, minWidth: width }} className="w-full" />
      {tip && (
        // where the finger or mouse is, kept on the screen
        <div role="tooltip" className="pointer-events-none fixed z-50 grid gap-0.5 rounded-ctl border border-line bg-surface px-2 py-1 text-fg shadow-lg"
          style={{
            left: Math.max(8, Math.min(tip.x + 12, window.innerWidth - (phone ? 228 : 348))),
            top: tip.y > 90 ? tip.y - 12 : tip.y + 18,
            transform: tip.y > 90 ? 'translateY(-100%)' : undefined,
            maxWidth: phone ? 220 : 340, fontSize: phone ? 11 : 13,
          }}>
          {tip.lines.map((l, i) => <span key={i} className={i === 0 ? 'font-semibold' : 'text-muted'}>{l}</span>)}
        </div>
      )}
    </div>
  )
}
