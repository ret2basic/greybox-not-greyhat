'use client'

import Image from 'next/image'
import { useEffect, useId, useState, type CSSProperties, type ReactNode } from 'react'
import usdtelIcon from '@/assets/tokens/USD.tel_token_icon/USD.tel_token_icon.svg'
import susdtelIcon from '@/assets/tokens/sUSD.tel_token_icon/sUSD.tel_token_icon.svg'
import usdcIcon from '@/assets/tokens/usdc.svg'

// Deterministic seeded walk for sparklines / mock charts.
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

// Catmull-Rom → cubic bezier path. Light control-point tension (vs the
// textbook 1/6) keeps lines sharp and close to the data rather than rounded.
const CURVE_TENSION = 0.06
export function smoothPath(pts: Array<[number, number]>): string {
  if (pts.length < 2) return ''
  let d = `M ${pts[0][0]} ${pts[0][1]}`
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i]
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const p3 = pts[i + 2] || p2
    const c1x = p1[0] + (p2[0] - p0[0]) * CURVE_TENSION
    const c1y = p1[1] + (p2[1] - p0[1]) * CURVE_TENSION
    const c2x = p2[0] - (p3[0] - p1[0]) * CURVE_TENSION
    const c2y = p2[1] - (p3[1] - p1[1]) * CURVE_TENSION
    d += ` C ${c1x} ${c1y}, ${c2x} ${c2y}, ${p2[0]} ${p2[1]}`
  }
  return d
}

// Formatters
export const fmt$ = (v: number, d = 0): string => {
  if (!Number.isFinite(v)) return '$0'
  const abs = Math.abs(v)
  if (abs >= 1e9) return '$' + (v / 1e9).toFixed(2) + 'B'
  if (abs >= 1e6) return '$' + (v / 1e6).toFixed(2) + 'M'
  if (abs >= 1e3) return '$' + (v / 1e3).toFixed(1) + 'K'
  return '$' + v.toFixed(d)
}
export const fmtN = (v: number): string => v.toLocaleString()
export const fmtPct = (v: number, d = 2): string => v.toFixed(d) + '%'

type MiniSparkProps = {
  data: number[]
  color?: string
  width?: number
  height?: number
  fill?: boolean
}

export function MiniSpark({
  data,
  color = 'var(--dawn-coral)',
  width = 100,
  height = 28,
  fill = true,
}: MiniSparkProps) {
  // Use useId() so the gradient's <linearGradient id> matches across
  // SSR and client hydration. Math.random() previously generated a
  // fresh value on each side, triggering React's hydration mismatch
  // warning. useId returns the same string in both render passes.
  const reactId = useId()
  const id = `mini-${reactId.replace(/:/g, '')}`
  if (!data || data.length < 2) {
    return <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} />
  }
  const pad = 2
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const stepX = (width - pad * 2) / (data.length - 1)
  const pts: Array<[number, number]> = data.map((v, i) => [
    pad + i * stepX,
    pad + (height - pad * 2) * (1 - (v - min) / range),
  ])
  const linePath = smoothPath(pts)
  const last = pts[pts.length - 1]
  const areaPath = `${linePath} L ${last[0]} ${height} L ${pts[0][0]} ${height} Z`
  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      style={{ display: 'block', overflow: 'visible' }}
    >
      <defs>
        <linearGradient id={id} x1='0' y1='0' x2='0' y2='1'>
          <stop offset='0%' stopColor={color} stopOpacity='0.32' />
          <stop offset='100%' stopColor={color} stopOpacity='0' />
        </linearGradient>
      </defs>
      {fill && <path d={areaPath} fill={`url(#${id})`} />}
      <path
        d={linePath}
        fill='none'
        stroke={color}
        strokeWidth='1.4'
        strokeLinecap='round'
        strokeLinejoin='round'
      />
      <circle cx={last[0]} cy={last[1]} r='2' fill={color} />
    </svg>
  )
}

type LiveBadgeProps = { label?: string; tone?: 'pos' | 'neg' | 'amber' }
export function LiveBadge({ label = 'HEALTHY', tone = 'pos' }: LiveBadgeProps) {
  const color =
    tone === 'pos' ? 'var(--pos)' : tone === 'neg' ? 'var(--neg)' : 'var(--dawn-amber)'
  const bg = tone === 'pos' ? 'var(--pos-bg)' : 'rgba(243,162,74,0.10)'
  const border = tone === 'pos' ? 'var(--pos-line)' : 'rgba(243,162,74,0.22)'
  return (
    <span
      className='mono'
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 7,
        padding: '5px 10px',
        borderRadius: 999,
        background: bg,
        border: `1px solid ${border}`,
        fontSize: 10,
        letterSpacing: '0.14em',
        color,
        textTransform: 'uppercase',
        fontWeight: 500,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: color,
          boxShadow: `0 0 8px ${color}`,
          animation: 'dawn-pulse 1.8s ease-in-out infinite',
        }}
      />
      {label}
    </span>
  )
}

export function EpochTicker() {
  const [epoch, setEpoch] = useState(4827)
  const [secs, setSecs] = useState(184)
  useEffect(() => {
    const id = setInterval(() => {
      setSecs((s) => {
        if (s <= 1) {
          setEpoch((e) => e + 1)
          return 600
        }
        return s - 1
      })
    }, 1000)
    return () => clearInterval(id)
  }, [])
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return (
    <span
      className='mono tabular'
      style={{
        color: 'var(--fg-3)',
        fontSize: 11,
        letterSpacing: '0.14em',
        textTransform: 'uppercase',
      }}
    >
      EPOCH {epoch.toLocaleString()} · NEXT IN {m}:{s.toString().padStart(2, '0')}
    </span>
  )
}

type CoinProps = { size?: number; sub?: boolean }
export function UsdTelCoin({ size = 24, sub = false }: CoinProps) {
  return (
    <Image
      src={sub ? susdtelIcon : usdtelIcon}
      alt={sub ? 'sUSD.tel' : 'USD.tel'}
      width={size}
      height={size}
      style={{ width: size, height: size, display: 'block', flexShrink: 0 }}
    />
  )
}

export function UsdcCoin({ size = 24 }: { size?: number }) {
  return (
    <Image
      src={usdcIcon}
      alt='USDC'
      width={size}
      height={size}
      style={{ width: size, height: size, display: 'block', flexShrink: 0 }}
    />
  )
}

type PillProps = {
  children: ReactNode
  tone?: 'default' | 'pos' | 'neg' | 'accent'
  className?: string
  style?: CSSProperties
}
export function Pill({ children, tone = 'default', className = '', style }: PillProps) {
  const cls =
    tone === 'pos'
      ? 'pill pill-pos'
      : tone === 'neg'
        ? 'pill pill-neg'
        : tone === 'accent'
          ? 'pill pill-accent'
          : 'pill'
  return (
    <span className={`${cls} ${className}`} style={style}>
      {children}
    </span>
  )
}
