'use client'

import type { ReactNode } from 'react'
import { useId, useRef, useState } from 'react'
import {
  buildSmoothSegments,
  changeFromStart,
  formatTimestamp,
  parseSeriesDate,
  RANGE_DAYS,
  type RangeKey,
  smoothPath,
  smoothYAtX,
} from '@/components/dashboard/utils'
import { SegmentedToggle } from '@/components/ui/SegmentedToggle'
import { useExpanded } from './ui'
// useId is used by AreaSpark (gradient ids) and Donut (gradient id).

// ── Shared axis primitives (expanded charts only) ────────────────
// Gutter (px) reserved on the left of expanded charts for y-scale labels.
const AXIS_GUTTER = 56

function YAxisLabel({ frac, children }: { frac: number; children: string }) {
  return (
    <span
      className='tabular'
      style={{
        position: 'absolute',
        right: '100%',
        marginRight: 8,
        top: `${frac * 100}%`,
        transform: 'translateY(-50%)',
        width: 44,
        textAlign: 'right',
        fontSize: 10,
        color: 'var(--d-ink-60)',
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </span>
  )
}

function XAxisLabels({ labels, gap }: { labels: string[]; gap?: number }) {
  return (
    <div style={{ display: 'flex', gap, justifyContent: gap ? undefined : 'space-between', marginTop: 10 }}>
      {labels.map((l, i) => (
        <span
          key={i}
          className='tabular'
          style={{ flex: gap ? 1 : undefined, textAlign: 'center', fontSize: 10, letterSpacing: '0.04em', color: 'var(--d-ink-60)' }}
        >
          {l}
        </span>
      ))}
    </div>
  )
}

// ── Detail-panel chrome (expand modal) ───────────────────────────
// Range order matches the reference modal (7D · 30D · 90D · 1Y · All).
export const DETAIL_RANGES: readonly RangeKey[] = ['7D', '30D', '90D', '1Y', 'All'] as const

// Slice the already-loaded series to a range window (no refetch — UI only).
// `dates` is the per-point label source, kept in step with the data slice.
// Windowed by actual calendar date (last N days), not point count: NAV history
// is sparse/irregular, so slicing by index made 7D/30D/90D return the same few
// points. Falls back to the full series when dates are unusable or the window
// would leave fewer than two points.
export function sliceByRange<T>(data: T[], dates: string[], range: RangeKey): { data: T[]; dates: string[] } {
  if (range === 'All' || dates.length !== data.length || dates.length < 2) {
    return { data, dates }
  }
  const lastT = parseSeriesDate(dates[dates.length - 1])
  if (!Number.isFinite(lastT)) return { data, dates }
  const cutoff = lastT - RANGE_DAYS[range] * 86_400_000
  const startIdx = dates.findIndex((d) => parseSeriesDate(d) >= cutoff)
  if (startIdx <= 0 || startIdx > data.length - 2) return { data, dates }
  return { data: data.slice(startIdx), dates: dates.slice(startIdx) }
}

// Pick `count` evenly-spaced, short-formatted date labels from an ISO series.
export function pickAxisDates(dates: string[], count = 5): string[] {
  if (dates.length < 2) return []
  const fmt = (s: string) => new Date(s).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  return Array.from({ length: count }, (_, i) => fmt(dates[Math.round((dates.length - 1) * (i / (count - 1)))]))
}

export function DetailHeader({ kicker, title }: { kicker: string; title: string }) {
  return (
    <div>
      <div style={{ fontSize: 11, letterSpacing: '0.14em', color: 'var(--d-ink-60)', textTransform: 'uppercase' }}>{kicker}</div>
      <div style={{ fontFamily: 'var(--font-sans)', fontWeight: 500, fontSize: 22, letterSpacing: '-0.02em', color: 'var(--d-text)', marginTop: 4 }}>
        {title}
      </div>
    </div>
  )
}

export function DetailStat({ label, value, tone }: { label: string; value: string; tone?: 'pos' | 'neg' }) {
  return (
    <div>
      <div style={{ fontSize: 11, letterSpacing: '0.14em', color: 'var(--d-ink-60)', textTransform: 'uppercase', marginBottom: 6 }}>{label}</div>
      <div
        className='tabular'
        style={{
          fontFamily: 'var(--font-sans)',
          fontWeight: 500,
          fontSize: 20,
          letterSpacing: '-0.02em',
          color: tone === 'pos' ? 'var(--d-pos)' : tone === 'neg' ? 'var(--d-neg)' : 'var(--d-text)',
        }}
      >
        {value}
      </div>
    </div>
  )
}

export function DetailRangeTabs({ value, onChange }: { value: RangeKey; onChange: (next: RangeKey) => void }) {
  return (
    <SegmentedToggle value={value} onChange={onChange} options={DETAIL_RANGES.map((r) => ({ value: r, label: r }))} />
  )
}

// Bordered stat tile with an optional sub-line (used by the NAV / utilization
// / composition detail grids).
export function DetailStatPanel({ label, value, sub, subTone }: { label: string; value: string; sub?: string; subTone?: 'pos' }) {
  return (
    <div className='dash-detail-stat-tile' style={{ padding: 16, borderRadius: 12, border: '1px solid var(--d-line)', background: 'var(--d-bg)' }}>
      <div style={{ fontSize: 11, letterSpacing: '0.14em', color: 'var(--d-ink-60)', textTransform: 'uppercase', marginBottom: 8 }}>{label}</div>
      <div className='tabular' style={{ fontFamily: 'var(--font-sans)', fontWeight: 500, fontSize: 24, letterSpacing: '-0.02em' }}>{value}</div>
      {sub && (
        <div style={{ fontSize: 10, letterSpacing: '0.1em', color: subTone === 'pos' ? 'var(--d-pos)' : 'var(--d-ink-60)', marginTop: 6, textTransform: 'uppercase' }}>{sub}</div>
      )}
    </div>
  )
}

// ISO date strings for the last `n` days (ending today). Used to label the
// synthetic over-time charts whose backend has no historical feed yet.
export function recentDates(n: number): string[] {
  const today = new Date()
  return Array.from({ length: n }, (_, i) => {
    const d = new Date(today)
    d.setDate(today.getDate() - (n - 1 - i))
    return d.toISOString()
  })
}

export function DetailFooter({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div
      className='dash-detail-footer'
      style={{
        display: 'flex',
        gap: 18,
        alignItems: 'center',
        padding: 16,
        borderRadius: 12,
        border: '1px solid var(--d-line)',
        background: 'var(--d-bg)',
      }}
    >
      <div
        className='dash-detail-footer-label'
        style={{ flex: '0 0 120px', fontSize: 11, letterSpacing: '0.14em', color: 'var(--d-ink-60)', textTransform: 'uppercase' }}
      >
        {label}
      </div>
      <div style={{ fontSize: 13, color: 'var(--d-ink-80)', lineHeight: 1.6 }}>{children}</div>
    </div>
  )
}

// ── Area sparkline ───────────────────────────────────────────────
// Smooth area chart used by KPI cards and the cumulative-yield card.
// Renders nothing meaningful when the series is empty (caller guards).
export function AreaSpark({
  data,
  color = '#f3a24a',
  width = 390,
  height = 53,
  strokeWidth = 2,
  pad = 6,
  formatValue,
  xLabels,
  pointDates,
  refLine,
  refLabel,
}: {
  data: number[]
  color?: string
  width?: number
  height?: number
  strokeWidth?: number
  pad?: number
  formatValue?: (n: number) => string
  xLabels?: string[]
  // Per-point ISO dates aligned with `data`, used for the expanded hover
  // read-out (the sparse `xLabels` only label a few axis ticks).
  pointDates?: string[]
  refLine?: number
  refLabel?: string
}) {
  const id = useId()
  const expanded = useExpanded()
  if (!data || data.length < 2) {
    return <svg width='100%' height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio='none' />
  }
  if (expanded) {
    return <ExpandedArea data={data} color={color} formatValue={formatValue} xLabels={xLabels} pointDates={pointDates} refLine={refLine} refLabel={refLabel} />
  }
  const min = Math.min(...data)
  const max = Math.max(...data)
  const span = max - min || 1
  const innerH = height - pad * 2
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width
    const y = pad + innerH - ((v - min) / span) * innerH
    return [x, y] as [number, number]
  })
  const line = smoothPath(pts)
  const area = `${line} L ${width} ${height} L 0 ${height} Z`
  return (
    <svg width='100%' height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio='none'>
      <defs>
        <linearGradient id={`fill-${id}`} x1='0' y1='0' x2='0' y2='1'>
          <stop offset='0%' stopColor={color} stopOpacity='0.28' />
          <stop offset='100%' stopColor={color} stopOpacity='0' />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#fill-${id})`} stroke='none' />
      <path d={line} fill='none' stroke={color} strokeWidth={strokeWidth} vectorEffect='non-scaling-stroke' />
    </svg>
  )
}

// Expanded (modal) area chart — adds a y-scale gutter, horizontal gridlines,
// x-axis labels and an end-point marker. Same smooth line as the sparkline.
function ExpandedArea({
  data,
  color,
  formatValue,
  xLabels,
  pointDates,
  refLine,
  refLabel,
}: {
  data: number[]
  color: string
  formatValue?: (n: number) => string
  xLabels?: string[]
  pointDates?: string[]
  refLine?: number
  refLabel?: string
}) {
  const id = useId()
  const W = 600
  const H = 300
  const min = Math.min(...data)
  const max = Math.max(...data)
  const padV = (max - min) * 0.08 || 1
  // Match BigAreaChart: never let the padded floor dip below zero for an
  // inherently non-negative series.
  const yMin = min >= 0 ? Math.max(0, min - padV) : min - padV
  const yMax = max + padV
  const range = yMax - yMin
  const pts = data.map((v, i) => [(i / (data.length - 1)) * W, H * (1 - (v - yMin) / range)] as [number, number])
  const segs = buildSmoothSegments(pts)
  const line = smoothPath(pts)
  const area = `${line} L ${W} ${H} L 0 ${H} Z`
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((p) => ({ p, v: yMax - range * p }))
  const lastFrac = 1 - (data[data.length - 1] - yMin) / range
  const fmt = formatValue ?? ((n: number) => n.toFixed(2))

  // Per-pixel hover: track the cursor x and read the curve at that exact point
  // (dot rides the line, value/time interpolated) rather than snapping to a day.
  const plotRef = useRef<HTMLDivElement | null>(null)
  const [hoverX, setHoverX] = useState<number | null>(null)
  const onMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!plotRef.current) return
    const rect = plotRef.current.getBoundingClientRect()
    const vx = ((e.clientX - rect.left) / rect.width) * W
    setHoverX(Math.max(0, Math.min(W, vx)))
  }
  const hover =
    hoverX != null
      ? (() => {
          const hy = smoothYAtX(segs, hoverX)
          const value = yMin + (1 - hy / H) * range
          const frac = hoverX / W
          let label = ''
          if (pointDates && pointDates.length >= 2) {
            const fi = frac * (pointDates.length - 1)
            const loI = Math.floor(fi)
            const hiI = Math.min(loI + 1, pointDates.length - 1)
            const t0 = parseSeriesDate(pointDates[loI])
            const t1 = parseSeriesDate(pointDates[hiI])
            label = formatTimestamp(t0 + (t1 - t0) * (fi - loI), pointDates)
          }
          const change = changeFromStart(value, data[0], fmt)
          return { leftPct: frac * 100, topPct: (hy / H) * 100, value, label, change }
        })()
      : null

  return (
    <div style={{ position: 'relative', paddingLeft: AXIS_GUTTER }}>
      <div
        ref={plotRef}
        style={{ position: 'relative', height: H, cursor: 'crosshair' }}
        onMouseMove={onMove}
        onMouseLeave={() => setHoverX(null)}
      >
        <svg width='100%' height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio='none' style={{ display: 'block' }}>
          <defs>
            <linearGradient id={`xfill-${id}`} x1='0' y1='0' x2='0' y2='1'>
              <stop offset='0%' stopColor={color} stopOpacity='0.28' />
              <stop offset='100%' stopColor={color} stopOpacity='0' />
            </linearGradient>
          </defs>
          {ticks.map((t, i) => (
            <line
              key={i}
              x1={0}
              x2={W}
              y1={t.p * H}
              y2={t.p * H}
              stroke='var(--d-line)'
              strokeWidth='1'
              strokeDasharray={i === ticks.length - 1 ? '0' : '2 4'}
              vectorEffect='non-scaling-stroke'
            />
          ))}
          <path d={area} fill={`url(#xfill-${id})`} stroke='none' />
          <path d={line} fill='none' stroke={color} strokeWidth='2' vectorEffect='non-scaling-stroke' />
          {refLine != null && refLine >= yMin && refLine <= yMax && (
            <line
              x1={0}
              x2={W}
              y1={H * (1 - (refLine - yMin) / range)}
              y2={H * (1 - (refLine - yMin) / range)}
              stroke='var(--d-ink-40)'
              strokeWidth='1'
              strokeDasharray='4 4'
              vectorEffect='non-scaling-stroke'
            />
          )}
        </svg>
        {ticks.map((t, i) => (
          <YAxisLabel key={i} frac={t.p}>
            {fmt(t.v)}
          </YAxisLabel>
        ))}
        {refLine != null && refLabel && refLine >= yMin && refLine <= yMax && (
          <span
            className='tabular'
            style={{
              position: 'absolute',
              right: 0,
              top: `${(1 - (refLine - yMin) / range) * 100}%`,
              transform: 'translateY(-130%)',
              fontSize: 9,
              letterSpacing: '0.1em',
              color: 'var(--d-ink-60)',
            }}
          >
            {refLabel}
          </span>
        )}
        <span
          style={{
            position: 'absolute',
            left: '100%',
            top: `${lastFrac * 100}%`,
            transform: 'translate(-50%, -50%)',
            width: 9,
            height: 9,
            borderRadius: '50%',
            background: color,
          }}
        />
        {hover && (
          <>
            <div
              style={{
                position: 'absolute',
                left: `${hover.leftPct}%`,
                top: 0,
                width: 1,
                height: '100%',
                background: color,
                opacity: 0.85,
                pointerEvents: 'none',
              }}
            />
            <div
              style={{
                position: 'absolute',
                left: `${hover.leftPct}%`,
                top: `${hover.topPct}%`,
                transform: 'translate(-50%, -50%)',
                width: 10,
                height: 10,
                borderRadius: '50%',
                background: color,
                boxShadow: `0 0 0 4px color-mix(in srgb, ${color} 22%, transparent)`,
                pointerEvents: 'none',
              }}
            />
            <div
              className='tabular'
              style={{
                position: 'absolute',
                left: `${hover.leftPct}%`,
                top: 8,
                transform: hover.leftPct > 60 ? 'translateX(calc(-100% - 12px))' : 'translateX(12px)',
                background: 'var(--d-surface, var(--d-bg))',
                border: '1px solid var(--d-line)',
                borderRadius: 8,
                padding: '8px 10px',
                fontSize: 11,
                whiteSpace: 'nowrap',
                pointerEvents: 'none',
                boxShadow: '0 8px 24px -8px rgba(0,0,0,0.4)',
                zIndex: 5,
              }}
            >
              {hover.label && (
                <div style={{ fontSize: 9, letterSpacing: '0.14em', color: 'var(--d-ink-60)', textTransform: 'uppercase', marginBottom: 4 }}>
                  {hover.label}
                </div>
              )}
              <div style={{ color, fontSize: 14, fontWeight: 500, letterSpacing: '-0.01em' }}>{fmt(hover.value)}</div>
              <div style={{ fontSize: 9, marginTop: 4, color: hover.change.positive ? 'var(--d-pos)' : 'var(--d-neg)' }}>
                {hover.change.label} from start
              </div>
            </div>
          </>
        )}
      </div>
      {xLabels && xLabels.length > 0 && <XAxisLabels labels={xLabels} />}
    </div>
  )
}

// ── Monthly bar chart ────────────────────────────────────────────
// Lerp between two hex colors (#rrggbb).
function lerpHex(a: string, b: string, t: number): string {
  const pa = [parseInt(a.slice(1, 3), 16), parseInt(a.slice(3, 5), 16), parseInt(a.slice(5, 7), 16)]
  const pb = [parseInt(b.slice(1, 3), 16), parseInt(b.slice(3, 5), 16), parseInt(b.slice(5, 7), 16)]
  const c = pa.map((v, i) => Math.round(v + (pb[i] - v) * t))
  return `#${c.map((v) => v.toString(16).padStart(2, '0')).join('')}`
}

export function BarChart({
  data,
  labels,
  height = 180,
  gap = 13,
  formatValue,
}: {
  data: number[]
  labels?: string[]
  height?: number
  gap?: number
  formatValue?: (n: number) => string
}) {
  const expanded = useExpanded()
  const max = data.length ? Math.max(...data, 1) : 1
  const n = data.length
  const H = expanded ? 240 : height
  const plotRef = useRef<HTMLDivElement | null>(null)
  const [hoverIdx, setHoverIdx] = useState<number | null>(null)
  // `activeIdx` highlights the hovered column and dims the rest (expanded only).
  const renderBars = (activeIdx: number | null) => (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap, height: H }}>
      {data.map((v, i) => {
        // Warm-amber bars shading subtly left→right, last bar accented coral.
        const isLast = i === n - 1
        const color = isLast ? '#c3683f' : lerpHex('#d18d44', '#d0764e', n > 1 ? i / (n - 1) : 0)
        return (
          <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', height: '100%' }}>
            <div
              style={{
                height: `${Math.max((v / max) * 100, 2)}%`,
                borderRadius: '4px 4px 0 0',
                background: color,
                opacity: activeIdx == null || activeIdx === i ? 1 : 0.45,
                transition: 'opacity 120ms ease',
              }}
            />
          </div>
        )
      })}
    </div>
  )

  if (expanded) {
    const ticks = [0, 0.25, 0.5, 0.75, 1].map((p) => ({ p, v: max * (1 - p) }))
    const fmt = formatValue ?? ((v: number) => String(Math.round(v)))
    const onMove = (e: React.MouseEvent<HTMLDivElement>) => {
      if (!plotRef.current || n === 0) return
      const rect = plotRef.current.getBoundingClientRect()
      const frac = (e.clientX - rect.left) / rect.width
      setHoverIdx(Math.max(0, Math.min(n - 1, Math.floor(frac * n))))
    }
    const hoverLeftPct = hoverIdx != null ? ((hoverIdx + 0.5) / n) * 100 : 0
    return (
      <div style={{ position: 'relative', paddingLeft: AXIS_GUTTER }}>
        <div
          ref={plotRef}
          style={{ position: 'relative', height: H, cursor: 'crosshair' }}
          onMouseMove={onMove}
          onMouseLeave={() => setHoverIdx(null)}
        >
          {ticks.map((t, i) => (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: 0,
                right: 0,
                top: `${t.p * 100}%`,
                borderTop: `1px ${i === ticks.length - 1 ? 'solid' : 'dashed'} var(--d-line)`,
              }}
            />
          ))}
          {ticks.map((t, i) => (
            <YAxisLabel key={i} frac={t.p}>
              {fmt(t.v)}
            </YAxisLabel>
          ))}
          <div style={{ position: 'absolute', inset: 0 }}>{renderBars(hoverIdx)}</div>
          {hoverIdx != null && (
            <div
              className='tabular'
              style={{
                position: 'absolute',
                left: `${hoverLeftPct}%`,
                top: 8,
                transform: hoverLeftPct > 60 ? 'translateX(calc(-100% - 10px))' : 'translateX(10px)',
                background: 'var(--d-surface, var(--d-bg))',
                border: '1px solid var(--d-line)',
                borderRadius: 8,
                padding: '8px 10px',
                fontSize: 11,
                whiteSpace: 'nowrap',
                pointerEvents: 'none',
                boxShadow: '0 8px 24px -8px rgba(0,0,0,0.4)',
                zIndex: 5,
              }}
            >
              {labels && labels[hoverIdx] && (
                <div style={{ fontSize: 9, letterSpacing: '0.14em', color: 'var(--d-ink-60)', textTransform: 'uppercase', marginBottom: 4 }}>
                  {labels[hoverIdx]}
                </div>
              )}
              <div style={{ color: 'var(--d-text)', fontSize: 14, fontWeight: 500, letterSpacing: '-0.01em' }}>{fmt(data[hoverIdx])}</div>
            </div>
          )}
        </div>
        {labels && <XAxisLabels labels={labels} gap={gap} />}
      </div>
    )
  }

  return (
    <div>
      {renderBars(null)}
      {labels && (
        <div style={{ display: 'flex', gap, marginTop: 10 }}>
          {labels.map((l, i) => (
            <div key={i} style={{ flex: 1, textAlign: 'center', fontSize: 9, color: 'var(--d-ink-60)' }}>
              {l}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Donut (utilization) ──────────────────────────────────────────
export function Donut({
  pct,
  size = 196,
  thickness = 16,
}: {
  pct: number
  size?: number
  thickness?: number
}) {
  const id = useId()
  const r = (size - thickness) / 2
  const c = 2 * Math.PI * r
  const clamped = Math.max(0, Math.min(100, pct))
  // leave a small gap at the bottom for an "open gauge" look (270° sweep feel
  // is avoided — full ring with rounded cap matches the Figma donut).
  const dash = (clamped / 100) * c
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <defs>
        <linearGradient id={`donut-${id}`} x1='0' y1='0' x2='1' y2='1'>
          <stop offset='0%' stopColor='#f3a24a' />
          <stop offset='100%' stopColor='#e84066' />
        </linearGradient>
      </defs>
      <circle cx={size / 2} cy={size / 2} r={r} fill='none' stroke='rgba(140,138,132,0.16)' strokeWidth={thickness} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill='none'
        stroke={`url(#donut-${id})`}
        strokeWidth={thickness}
        strokeLinecap='round'
        strokeDasharray={`${dash} ${c - dash}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
    </svg>
  )
}

// ── Up / down delta arrow ────────────────────────────────────────
export function DeltaArrow({ up }: { up: boolean }) {
  return (
    <svg viewBox='0 0 9 9' fill='none' style={{ transform: up ? 'none' : 'scaleY(-1)' }}>
      <path d='M4.5 1.5 L7.5 6 L1.5 6 Z' fill='currentColor' />
    </svg>
  )
}
