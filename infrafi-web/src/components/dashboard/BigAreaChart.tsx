'use client'

import { useMemo, useRef, useState } from 'react'
import {
  buildCalendarXTicks,
  buildSmoothSegments,
  buildTimeScale,
  changeFromStart,
  dayLabel,
  fmtVal,
  formatAxisDate,
  formatTimestamp,
  seriesDateLabel,
  smoothPath,
  smoothYAtX,
  timeToFraction,
  type ValueKind,
} from './utils'

type Props = {
  data: number[]
  dates?: string[]
  color: string
  kind?: ValueKind | string
  height?: number
  refLine?: number | null
  refLabel?: string
  showAxis?: boolean
}

export function BigAreaChart({
  data,
  dates,
  color,
  kind = '$K',
  height = 320,
  refLine = null,
  refLabel = '',
  showAxis = true,
}: Props) {
  const [hoverX, setHoverX] = useState<number | null>(null)
  const ref = useRef<HTMLDivElement | null>(null)
  const id = useMemo(() => `big-${Math.random().toString(36).slice(2, 8)}`, [])

  const W = 800
  const H = height
  const padL = 56
  const padR = 24
  const padT = 24
  const padB = showAxis ? 32 : 16
  const innerW = W - padL - padR
  const innerH = H - padT - padB

  if (!data || data.length < 2) {
    return <div style={{ height: H }} />
  }

  const refLineList = refLine != null ? [refLine] : []
  const min = Math.min(...data, ...refLineList)
  const max = Math.max(...data, ...refLineList)
  const yPad = (max - min) * 0.08 || 1
  // Don't let the padded floor dip below zero for inherently non-negative
  // series (APY, TVL, price) — a "-0.93%" axis tick reads as a defect.
  const yMin = min >= 0 ? Math.max(0, min - yPad) : min - yPad
  const yMax = max + yPad
  const range = yMax - yMin
  const stepX = innerW / (data.length - 1)
  const timeScale =
    dates && dates.length === data.length ? buildTimeScale(dates) : null
  const xAt = (i: number) =>
    timeScale
      ? padL + timeToFraction(timeScale.times[i], timeScale) * innerW
      : padL + i * stepX
  const pts: Array<[number, number]> = data.map((v, i) => [
    xAt(i),
    padT + innerH * (1 - (v - yMin) / range),
  ])
  const refY = refLine != null ? padT + innerH * (1 - (refLine - yMin) / range) : null

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((p) => ({
    p,
    v: yMin + range * (1 - p),
    y: padT + innerH * p,
  }))
  const xTickCount = 6
  const xTicks = timeScale
    ? buildCalendarXTicks(timeScale, xTickCount).map((tick) => ({
        x: padL + tick.x * innerW,
        label: formatAxisDate(tick.dateStr, dates),
      }))
    : Array.from({ length: xTickCount }, (_, i) => {
        const idx = Math.round((data.length - 1) * (i / (xTickCount - 1)))
        return {
          x: padL + idx * stepX,
          label: seriesDateLabel(idx, data.length, dates),
        }
      })

  const segs = buildSmoothSegments(pts)
  const linePath = smoothPath(pts)

  const onMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!ref.current) return
    const rect = ref.current.getBoundingClientRect()
    // Cursor x in viewBox units, clamped to the plotted range so the read-out
    // tracks the line pixel-by-pixel rather than snapping to the nearest day.
    const vx = ((e.clientX - rect.left) / rect.width) * W
    setHoverX(Math.max(padL, Math.min(W - padR, vx)))
  }

  const start = data[0]

  // Hover read-out: value/time/position interpolated at the exact cursor x.
  // The dot rides the drawn curve (smoothYAtX) and the value is read back off
  // that same y, so dot, crosshair and tooltip always agree.
  const hover =
    hoverX != null
      ? (() => {
          const y = smoothYAtX(segs, hoverX)
          const value = yMin + (1 - (y - padT) / innerH) * range
          const frac = innerW > 0 ? (hoverX - padL) / innerW : 0
          const label = timeScale
            ? formatTimestamp(timeScale.minT + frac * timeScale.span, dates)
            : dayLabel(Math.round(frac * (data.length - 1)), data.length)
          const change = changeFromStart(value, start, (n) => fmtVal(n, kind))
          return { x: hoverX, y, value, label, change }
        })()
      : null

  return (
    <div
      ref={ref}
      style={{ position: 'relative', cursor: 'crosshair', userSelect: 'none' }}
      onMouseMove={onMove}
      onMouseLeave={() => setHoverX(null)}
    >
      <svg
        width='100%'
        height={H}
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio='none'
        style={{ display: 'block' }}
      >
        <defs>
          <linearGradient id={id} x1='0' y1='0' x2='0' y2='1'>
            <stop offset='0%' stopColor={color} stopOpacity='0.34' />
            <stop offset='100%' stopColor={color} stopOpacity='0' />
          </linearGradient>
        </defs>
        {yTicks.map((t, i) => (
          <line
            key={`yt-${i}`}
            x1={padL}
            x2={W - padR}
            y1={t.y}
            y2={t.y}
            stroke='var(--grid)'
            strokeDasharray={i === yTicks.length - 1 ? '0' : '2 4'}
          />
        ))}
        {showAxis &&
          yTicks.map((t, i) => (
            <text
              key={`yl-${i}`}
              x={padL - 10}
              y={t.y + 3}
              textAnchor='end'
              fontFamily='var(--font-mono)'
              fontSize='10'
              fill='var(--fg-4)'
              letterSpacing='0.06em'
            >
              {fmtVal(t.v, kind)}
            </text>
          ))}
        {showAxis &&
          xTicks.map((tick, i) => (
            <text
              key={`xl-${i}`}
              x={tick.x}
              y={H - 12}
              textAnchor='middle'
              fontFamily='var(--font-mono)'
              fontSize='10'
              fill='var(--fg-4)'
              letterSpacing='0.08em'
            >
              {tick.label.toUpperCase()}
            </text>
          ))}
        {refY != null && (
          <g>
            <line
              x1={padL}
              x2={W - padR}
              y1={refY}
              y2={refY}
              stroke='var(--fg-4)'
              strokeWidth='1'
              strokeDasharray='4 4'
            />
            <text
              x={W - padR - 4}
              y={refY - 6}
              textAnchor='end'
              fontFamily='var(--font-mono)'
              fontSize='9'
              fill='var(--fg-4)'
              letterSpacing='0.1em'
            >
              {refLabel}
            </text>
          </g>
        )}
        <path
          d={`${linePath} L ${pts[pts.length - 1][0]} ${padT + innerH} L ${pts[0][0]} ${padT + innerH} Z`}
          fill={`url(#${id})`}
        />
        <path d={linePath} fill='none' stroke={color} strokeWidth='2' />
        {hover && (
          <g>
            <line
              x1={hover.x}
              x2={hover.x}
              y1={padT}
              y2={padT + innerH}
              stroke={color}
              strokeWidth='1.5'
              opacity='0.85'
            />
            <circle cx={hover.x} cy={hover.y} r='14' fill={color} fillOpacity='0.15'>
              <animate
                attributeName='r'
                values='10;16;10'
                dur='1.6s'
                repeatCount='indefinite'
              />
              <animate
                attributeName='fill-opacity'
                values='0.22;0.08;0.22'
                dur='1.6s'
                repeatCount='indefinite'
              />
            </circle>
            <circle cx={hover.x} cy={hover.y} r='7' fill={color} fillOpacity='0.35' />
            <circle
              cx={hover.x}
              cy={hover.y}
              r='4'
              fill={color}
              stroke='var(--bg-1)'
              strokeWidth='2'
            />
          </g>
        )}
        <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r='4' fill={color} />
      </svg>
      {hover && (
        <div
          className='mono'
          style={{
            position: 'absolute',
            left: `${(hover.x / W) * 100}%`,
            top: 8,
            transform:
              hover.x > padL + innerW * 0.6
                ? 'translateX(calc(-100% - 12px))'
                : 'translateX(12px)',
            background: 'var(--bg-3)',
            border: '1px solid var(--line-strong)',
            borderRadius: 8,
            padding: '10px 12px',
            fontSize: 11,
            color: 'var(--fg)',
            whiteSpace: 'nowrap',
            pointerEvents: 'none',
            letterSpacing: '0.04em',
            zIndex: 10,
            boxShadow: '0 8px 24px -8px rgba(0,0,0,0.4)',
          }}
        >
          <div
            style={{
              color: 'var(--fg-3)',
              fontSize: 9,
              letterSpacing: '0.14em',
              marginBottom: 4,
            }}
          >
            {hover.label.toUpperCase()}
          </div>
          <div
            style={{
              color,
              fontSize: 14,
              fontFamily: 'var(--font-display)',
              letterSpacing: '-0.01em',
            }}
          >
            {fmtVal(hover.value, kind)}
          </div>
          <div
            style={{
              color: hover.change.positive ? 'var(--pos)' : 'var(--neg)',
              fontSize: 9,
              marginTop: 4,
            }}
          >
            {hover.change.label} from start
          </div>
        </div>
      )}
    </div>
  )
}
