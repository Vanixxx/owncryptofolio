/** A curve without axes (ADR 0019 / webui): the shape gives a mixed-up coin away faster
 * than any number. Plain SVG — no chart library for a thumbnail. */
/** `up` overrides the colour: the list colours by the change shown next to it. */
export function Sparkline({ values, width = 96, height = 32, up: given }: { values: string[]; width?: number; height?: number; up?: boolean }) {
  const nums = values.map(Number).filter((n) => Number.isFinite(n))
  if (nums.length < 2) return <span style={{ width, height }} className="inline-block" />
  const lo = Math.min(...nums), hi = Math.max(...nums), span = hi - lo || 1
  const pts = nums.map((v, i) => `${(i / (nums.length - 1)) * width},${height - 2 - ((v - lo) / span) * (height - 4)}`)
  const up = given ?? nums[nums.length - 1] >= nums[0]
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true" className="shrink-0 overflow-visible">
      <polyline points={pts.join(' ')} fill="none" strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round"
        stroke={up ? 'var(--up)' : 'var(--down)'} />
    </svg>
  )
}
