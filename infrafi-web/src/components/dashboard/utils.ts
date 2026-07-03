// Format kinds describe what flavor of value a chart is showing so the same
// formatting logic can drive sparklines, big-area charts, axis labels, and
// modal stats consistently.
export type ValueKind = '$K' | '$$' | '%' | '$' | 'ratio' | 'bps'

export function fmtVal(v: number, kind: ValueKind | string = '$K'): string {
  if (!Number.isFinite(v)) return '—'
  switch (kind) {
    case '$K': {
      const abs = Math.abs(v)
      if (abs >= 1000) return `$${(v / 1000).toFixed(2)}M`
      if (abs >= 100) return `$${v.toFixed(0)}K`
      return `$${v.toFixed(1)}K`
    }
    case '$$': {
      const abs = Math.abs(v)
      if (abs >= 1e9) return `$${(v / 1e9).toFixed(2)}B`
      if (abs >= 1e6) return `$${(v / 1e6).toFixed(2)}M`
      if (abs >= 1e3) return `$${(v / 1e3).toFixed(1)}K`
      return `$${v.toFixed(0)}`
    }
    case '%':
      return `${v.toFixed(2)}%`
    case '$':
      return `$${v.toFixed(3)}`
    case 'ratio':
      return `${v.toFixed(0)}%`
    case 'bps':
      return `${v >= 0 ? '+' : ''}${v.toFixed(1)} bps`
    default:
      return v.toFixed(2)
  }
}

// Change of `current` vs the window's starting value, for the "Change" stat and
// the hover "from start" read-out. A relative percent is only meaningful when
// the baseline is non-zero — for a series that starts at 0 (e.g. APY or
// cumulative yield on day one) a "% change" is undefined, so we fall back to the
// absolute delta formatted in the metric's own units. `fmt` formats that delta.
export function changeFromStart(
  current: number,
  start: number,
  fmt: (n: number) => string,
): { label: string; positive: boolean } {
  const delta = current - start
  if (Math.abs(start) > 1e-6) {
    const pct = (delta / Math.abs(start)) * 100
    return { label: `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`, positive: pct >= 0 }
  }
  return { label: `${delta >= 0 ? '+' : '-'}${fmt(Math.abs(delta))}`, positive: delta >= 0 }
}

// "10D AGO" / "TODAY" labels keyed off the relative position in a series.
export function dayLabel(idx: number, len: number): string {
  if (idx === len - 1) return 'Today'
  const daysAgo = len - 1 - idx
  if (daysAgo === 1) return 'Yesterday'
  return `${daysAgo}D ago`
}

// ISO date strings for the last `n` days (ending today). Used when a chart has
// synthetic data but still needs a real time axis.
export function recentDates(n: number): string[] {
  const today = new Date()
  return Array.from({ length: n }, (_, i) => {
    const d = new Date(today)
    d.setDate(today.getDate() - (n - 1 - i))
    return toDateKey(d)
  })
}

// Parse API date strings as local calendar days (avoids UTC off-by-one).
export function parseSeriesDate(dateStr: string): number {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(dateStr)
  if (m) {
    return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])).getTime()
  }
  const d = new Date(dateStr)
  return Number.isNaN(d.getTime()) ? NaN : d.getTime()
}

function toDateKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export type TimeScale = {
  times: number[]
  minT: number
  maxT: number
  span: number
}

export function buildTimeScale(dates: string[]): TimeScale | null {
  if (dates.length < 2) return null
  const times = dates.map(parseSeriesDate)
  if (times.some(Number.isNaN)) return null
  const minT = times[0]
  const maxT = times[times.length - 1]
  const span = maxT - minT
  if (span <= 0) return null
  return { times, minT, maxT, span }
}

export function timeToFraction(t: number, scale: TimeScale): number {
  return (t - scale.minT) / scale.span
}

export type CalendarTick = {
  x: number
  dateStr: string
}

// Evenly spaced calendar ticks across the series span (not data indices).
export function buildCalendarXTicks(scale: TimeScale, count = 6): CalendarTick[] {
  const { minT, span } = scale
  return Array.from({ length: count }, (_, i) => {
    const frac = i / (count - 1)
    const d = new Date(minT + span * frac)
    return { x: frac, dateStr: toDateKey(d) }
  })
}

export function nearestIndexByTime(times: number[], targetT: number): number {
  let best = 0
  let bestDist = Math.abs(times[0] - targetT)
  for (let i = 1; i < times.length; i++) {
    const dist = Math.abs(times[i] - targetT)
    if (dist < bestDist) {
      best = i
      bestDist = dist
    }
  }
  return best
}

// Map a hover x (0 = left inner edge) to the nearest series index. Uses equal
// index bands so every day stays reachable even when the time axis compresses
// or stretches gaps between calendar dates.
export function nearestIndexAtLocalX(
  localX: number,
  innerW: number,
  count: number,
): number {
  if (count <= 1) return 0
  const step = innerW / (count - 1)
  return Math.max(0, Math.min(count - 1, Math.round(localX / step)))
}

function spanNeedsYear(dates: string[]): boolean {
  if (dates.length < 2) return false
  const first = parseSeriesDate(dates[0])
  const last = parseSeriesDate(dates[dates.length - 1])
  if (Number.isNaN(first) || Number.isNaN(last)) return false
  const firstDate = new Date(first)
  const lastDate = new Date(last)
  return (
    firstDate.getFullYear() !== lastDate.getFullYear() ||
    last - first > 90 * 86_400_000
  )
}

export function formatAxisDate(dateStr: string, dates?: string[]): string {
  const t = parseSeriesDate(dateStr)
  if (Number.isNaN(t)) return '—'
  const d = new Date(t)
  const includeYear = dates ? spanNeedsYear(dates) : false
  return d.toLocaleDateString(
    'en-US',
    includeYear
      ? { month: 'short', day: 'numeric', year: '2-digit' }
      : { month: 'short', day: 'numeric' },
  )
}

// Prefer real dates when available; fall back to relative day labels.
export function seriesDateLabel(
  idx: number,
  len: number,
  dates?: string[],
): string {
  if (dates && dates[idx]) return formatAxisDate(dates[idx], dates)
  return dayLabel(idx, len)
}

export const RANGE_DAYS = {
  '7D': 7,
  '30D': 30,
  '90D': 90,
  '1Y': 365,
  All: 730,
} as const
export type RangeKey = keyof typeof RANGE_DAYS

// One cubic-bezier segment of a smoothed series — endpoints `p1`/`p2` plus the
// two control points derived from neighbouring data points.
export type BezierSeg = {
  p1: [number, number]
  c1: [number, number]
  c2: [number, number]
  p2: [number, number]
}

// Control-point tension for the curve. The textbook Catmull-Rom→bezier value
// is 1/6 (≈0.167), which rounds corners heavily and lets peaks overshoot the
// data. We keep a much lighter touch so the lines stay sharp and track the
// points closely (0 would be straight polylines).
const CURVE_TENSION = 0.06

// Catmull-Rom → cubic-bezier segments. Shared by `smoothPath` (drawing) and
// `smoothYAtX` (hover read-out) so the line and the cursor dot use the exact
// same curve.
export function buildSmoothSegments(
  pts: Array<[number, number]>,
  tension = CURVE_TENSION,
): BezierSeg[] {
  const segs: BezierSeg[] = []
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i]
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const p3 = pts[i + 2] || p2
    segs.push({
      p1,
      c1: [p1[0] + (p2[0] - p0[0]) * tension, p1[1] + (p2[1] - p0[1]) * tension],
      c2: [p2[0] - (p3[0] - p1[0]) * tension, p2[1] - (p3[1] - p1[1]) * tension],
      p2,
    })
  }
  return segs
}

// Catmull-Rom → cubic-bezier path. Local copy so the dashboard charts don't
// import the existing primitives barrel just for this helper.
export function smoothPath(pts: Array<[number, number]>): string {
  if (pts.length < 2) return ''
  let d = `M ${pts[0][0]} ${pts[0][1]}`
  for (const s of buildSmoothSegments(pts)) {
    d += ` C ${s.c1[0]} ${s.c1[1]}, ${s.c2[0]} ${s.c2[1]}, ${s.p2[0]} ${s.p2[1]}`
  }
  return d
}

function cubicAt(a: number, b: number, c: number, d: number, u: number): number {
  const m = 1 - u
  return m * m * m * a + 3 * m * m * u * b + 3 * m * u * u * c + u * u * u * d
}

// The y on the smoothed curve at an arbitrary x — lets the hover dot ride the
// drawn line for any pixel, not just at data points. x is monotonic for a time
// series, so we locate the segment then bisect its bezier parameter on x.
export function smoothYAtX(segs: BezierSeg[], x: number): number {
  if (segs.length === 0) return 0
  if (x <= segs[0].p1[0]) return segs[0].p1[1]
  const last = segs[segs.length - 1]
  if (x >= last.p2[0]) return last.p2[1]
  let seg = segs[0]
  for (const s of segs) {
    if (x >= s.p1[0] && x <= s.p2[0]) {
      seg = s
      break
    }
  }
  let lo = 0
  let hi = 1
  for (let k = 0; k < 24; k++) {
    const u = (lo + hi) / 2
    if (cubicAt(seg.p1[0], seg.c1[0], seg.c2[0], seg.p2[0], u) < x) lo = u
    else hi = u
  }
  const u = (lo + hi) / 2
  return cubicAt(seg.p1[1], seg.c1[1], seg.c2[1], seg.p2[1], u)
}

// Format an arbitrary timestamp (from an interpolated hover position) the same
// way axis ticks render — short month/day, with year only for long spans.
export function formatTimestamp(t: number, dates?: string[]): string {
  if (!Number.isFinite(t)) return '—'
  const d = new Date(t)
  const includeYear = dates ? spanNeedsYear(dates) : false
  return d.toLocaleDateString(
    'en-US',
    includeYear
      ? { month: 'short', day: 'numeric', year: '2-digit' }
      : { month: 'short', day: 'numeric' },
  )
}

// Deterministic seeded random walk — used to generate mock chart data that
// stays stable across renders (so a hover doesn't reshuffle the line).
export function walk(seed: number, n: number, base: number, vol = 0.04, drift = 0): number[] {
  let s = seed
  const rand = () => {
    s = (s * 9301 + 49297) % 233280
    return s / 233280
  }
  const out: number[] = []
  let v = base
  for (let i = 0; i < n; i++) {
    v = v * (1 + (rand() - 0.5) * vol + drift)
    out.push(v)
  }
  return out
}
