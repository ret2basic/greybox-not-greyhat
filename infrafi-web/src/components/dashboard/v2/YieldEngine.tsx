'use client'

import { useRef, useState } from 'react'
import { changeFromStart, type RangeKey } from '@/components/dashboard/utils'
import {
  AreaSpark,
  BarChart,
  DetailFooter,
  DetailHeader,
  DetailRangeTabs,
  DetailStat,
  DetailStatPanel,
  Donut,
  pickAxisDates,
  recentDates,
  sliceByRange,
} from './charts'
import { Card, DeltaPill, ExpandGlyph, InfoBadge } from './ui'
import { SegmentedToggle } from '@/components/ui/SegmentedToggle'

// Parse a compact money string ("$18K", "$2.16M", "$738") to a number.
function parseMoney(s: string): number {
  const m = s.match(/([\d.]+)\s*([KM]?)/i)
  if (!m) return 0
  const n = parseFloat(m[1])
  return m[2]?.toUpperCase() === 'M' ? n * 1e6 : m[2]?.toUpperCase() === 'K' ? n * 1e3 : n
}

// Deterministic backward random-walk anchored to `end` (the real current
// value). Used to render the over-time charts the backend has no feed for yet.
function mockHistory(end: number, n: number, seed: number, vol = 0.1): number[] {
  let s = seed >>> 0
  const rand = () => {
    s = (s * 1664525 + 1013904223) >>> 0
    return s / 4294967296
  }
  const out: number[] = [Math.max(end, 0)]
  let v = Math.max(end, 0.0001)
  for (let i = 1; i < n; i++) {
    v = Math.max(0, v * (1 - (rand() - 0.45) * vol))
    out.unshift(v)
  }
  return out
}

// ── Monthly network revenue ──────────────────────────────────────
function RevenueDetail({
  months,
  labels,
  formatValue,
  about,
}: {
  months: number[]
  labels: string[]
  formatValue: (n: number) => string
  about?: string
}) {
  const current = months.length ? months[months.length - 1] : 0
  const prev = months.length > 1 ? months[months.length - 2] : current
  const change = changeFromStart(current, prev, formatValue)
  const high = months.length ? Math.max(...months) : 0
  const low = months.length ? Math.min(...months) : 0
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <DetailHeader kicker='Monthly network revenue' title='Monthly network revenue' />
      <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap' }}>
        <DetailStat label='Current' value={formatValue(current)} />
        <DetailStat label='Change' value={change.label} tone={change.positive ? 'pos' : 'neg'} />
        <DetailStat label='High' value={formatValue(high)} />
        <DetailStat label='Low' value={formatValue(low)} />
      </div>
      <BarChart data={months} labels={labels} formatValue={formatValue} />
      {about && <DetailFooter label='About'>{about}</DetailFooter>}
    </div>
  )
}

export function RevenueCard({
  value,
  delta,
  deltaPositive,
  months,
  labels,
  ytd,
  formatValue,
  about,
}: {
  value: string
  delta: string
  deltaPositive: boolean
  months: number[]
  labels: string[]
  ytd: string
  formatValue?: (n: number) => string
  about?: string
}) {
  const fmt = formatValue ?? ((n: number) => String(Math.round(n)))
  return (
    <Card detail={<RevenueDetail months={months} labels={labels} formatValue={fmt} about={about} />}>
      <ExpandGlyph />
      <div className='dash-card-label' style={{ marginBottom: 12 }}>
        Monthly network revenue
        <InfoBadge title='Settlement revenue earned by the vault from telecom deployments.' />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
        <span className='dash-card-value tabular'>{value}</span>
        <DeltaPill value={delta} positive={deltaPositive} />
      </div>
      <div className='dash-card-sub' style={{ marginBottom: 14 }}>
        Trailing 12 months
      </div>
      <BarChart data={months} labels={labels} height={120} formatValue={formatValue} />
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: 12,
          fontSize: 12,
          color: 'var(--d-ink-40)',
        }}
      >
        <span>Net of operator costs</span>
        <span>YTD · {ytd}</span>
      </div>
    </Card>
  )
}

// ── Deployed asset composition ───────────────────────────────────
export type CompositionSegment = { label: string; pct: number; value: string; color: string }

// Build a smooth left→right gradient whose color stops sit at each segment's
// cumulative midpoint — reads as the Figma's blended amber→coral bar while
// still reflecting the real proportions. Falls back to a flat track if empty.
function compositionGradient(segments: CompositionSegment[]): string {
  if (!segments.length) return 'var(--d-line-soft)'
  const stops: string[] = []
  let acc = 0
  for (const s of segments) {
    const mid = acc + s.pct / 2
    stops.push(`${s.color} ${mid.toFixed(1)}%`)
    acc += s.pct
  }
  return `linear-gradient(90deg, ${stops.join(', ')})`
}

// Per-strategy blurbs for the expanded composition grid (design copy).
const STRATEGY_DESC: Record<string, string> = {
  'Apartment buildings': 'Hardware deployment in residential properties.',
  'Carrier offload': 'MNO data offload settlement.',
  Acquisitions: 'Network expansion & site acquisition.',
  'Fiber deployment': 'Last-mile fiber build-out.',
  'Tower build': 'Macro tower construction.',
  'Edge infrastructure': 'Edge compute & caching nodes.',
}

// Stacked "composition over time" area — deterministic mock history anchored
// to each segment's real current value, with a $ y-scale + gridlines.
function CompositionStacked({ segments, height = 240 }: { segments: CompositionSegment[]; height: number }) {
  const N = 24
  const W = 600
  const series = segments.map((s, i) => mockHistory(parseMoney(s.value), N, 13 + i * 97))
  const totals = Array.from({ length: N }, (_, d) => series.reduce((a, s) => a + s[d], 0))
  const max = Math.max(...totals, 1) * 1.05
  const x = (i: number) => (i / (N - 1)) * W
  const y = (v: number) => height - (v / max) * height
  let bottoms = Array(N).fill(0)
  const layers = segments.map((s, si) => {
    const tops = totals.map((_, d) => bottoms[d] + series[si][d])
    const path =
      Array.from({ length: N }, (_, d) => `${d === 0 ? 'M' : 'L'} ${x(d)} ${y(tops[d])}`).join(' ') +
      ' ' +
      Array.from({ length: N }, (_, d) => `L ${x(N - 1 - d)} ${y(bottoms[N - 1 - d])}`).join(' ') +
      ' Z'
    bottoms = tops
    return { color: s.color, path, key: s.label }
  })
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((p) => ({ p, v: max * (1 - p) }))

  // Per-pixel hover: read every layer's stacked value + the total at the exact
  // cursor x (a crosshair + breakdown tooltip — too many layers for per-dot).
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
          const frac = hoverX / W
          const fi = frac * (N - 1)
          const loI = Math.floor(fi)
          const hiI = Math.min(loI + 1, N - 1)
          const f = fi - loI
          const values = segments.map((s, si) => ({
            label: s.label,
            color: s.color,
            value: series[si][loI] + (series[si][hiI] - series[si][loI]) * f,
          }))
          const total = values.reduce((a, v) => a + v.value, 0)
          return { leftPct: frac * 100, values, total, daysAgo: Math.round((1 - frac) * 90) }
        })()
      : null
  const money = (v: number) => (v >= 1000 ? `$${(v / 1000).toFixed(1)}K` : `$${v.toFixed(0)}`)

  return (
    <div style={{ position: 'relative', paddingLeft: 56 }}>
      <div
        ref={plotRef}
        style={{ position: 'relative', height, cursor: 'crosshair' }}
        onMouseMove={onMove}
        onMouseLeave={() => setHoverX(null)}
      >
        <svg width='100%' height={height} viewBox={`0 0 ${W} ${height}`} preserveAspectRatio='none' style={{ display: 'block' }}>
          {layers.map((l) => (
            <path key={l.key} d={l.path} fill={l.color} fillOpacity='0.85' stroke={l.color} strokeOpacity='0.5' strokeWidth='0.6' vectorEffect='non-scaling-stroke' />
          ))}
        </svg>
        {hover && (
          <>
            <div
              style={{
                position: 'absolute',
                left: `${hover.leftPct}%`,
                top: 0,
                width: 1,
                height: '100%',
                background: 'rgba(255,255,255,0.6)',
                pointerEvents: 'none',
              }}
            />
            <div
              className='tabular'
              style={{
                position: 'absolute',
                left: `${hover.leftPct}%`,
                top: 4,
                transform: hover.leftPct > 60 ? 'translateX(calc(-100% - 12px))' : 'translateX(12px)',
                background: 'var(--d-surface, var(--d-bg))',
                border: '1px solid var(--d-line)',
                borderRadius: 8,
                padding: '8px 10px',
                fontSize: 10,
                minWidth: 150,
                pointerEvents: 'none',
                boxShadow: '0 8px 24px -8px rgba(0,0,0,0.4)',
                zIndex: 5,
              }}
            >
              <div style={{ fontSize: 9, letterSpacing: '0.12em', color: 'var(--d-ink-60)', textTransform: 'uppercase', marginBottom: 6 }}>
                {hover.daysAgo === 0 ? 'Now' : `${hover.daysAgo}D ago`}
              </div>
              {hover.values.map((v) => (
                <div key={v.label} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 4 }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--d-ink-80)' }}>
                    <span style={{ width: 7, height: 7, borderRadius: '50%', background: v.color }} />
                    {v.label}
                  </span>
                  <span>{money(v.value)}</span>
                </div>
              ))}
              <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid var(--d-line)', paddingTop: 4, marginTop: 2 }}>
                <span style={{ color: 'var(--d-ink-60)' }}>Total</span>
                <span>{money(hover.total)}</span>
              </div>
            </div>
          </>
        )}
        {ticks.map((t, i) => (
          <div key={`g-${i}`} style={{ position: 'absolute', left: 0, right: 0, top: `${t.p * 100}%`, borderTop: '1px dashed var(--d-line)', opacity: 0.5 }} />
        ))}
        {ticks.map((t, i) => (
          <span
            key={`l-${i}`}
            className='tabular'
            style={{ position: 'absolute', right: '100%', marginRight: 8, top: `${t.p * 100}%`, transform: 'translateY(-50%)', width: 44, textAlign: 'right', fontSize: 10, color: 'var(--d-ink-60)', whiteSpace: 'nowrap' }}
          >
            ${(t.v / 1000).toFixed(0)}K
          </span>
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10, paddingLeft: 0, fontSize: 10, letterSpacing: '0.04em', color: 'var(--d-ink-60)' }}>
        <span>90D ago</span>
        <span>Now</span>
      </div>
    </div>
  )
}

function CompositionDetail({ segments }: { total: string; segments: CompositionSegment[] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <DetailHeader kicker='Deployed asset composition' title='Where deployed capital is going' />
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 18, marginBottom: 14, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, letterSpacing: '0.14em', color: 'var(--d-ink-60)', textTransform: 'uppercase' }}>Composition over time</span>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            {segments.map((s) => (
              <span key={s.label} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <span className='dash-legend-dot' style={{ background: s.color }} />
                <span style={{ fontSize: 10, letterSpacing: '0.12em', color: 'var(--d-ink-80)', textTransform: 'uppercase' }}>{s.label}</span>
              </span>
            ))}
          </div>
        </div>
        <CompositionStacked segments={segments} height={240} />
      </div>
      <div className='dash-detail-stat-grid' style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(segments.length, 3)}, 1fr)`, gap: 14 }}>
        {segments.map((s) => (
          <div key={s.label} className='dash-detail-stat-tile' style={{ padding: 16, borderRadius: 12, border: '1px solid var(--d-line)', background: 'var(--d-bg)' }}>
            <div className='dash-detail-stat-tile-legend' style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <span className='dash-legend-dot' style={{ background: s.color }} />
              <span style={{ fontSize: 11, letterSpacing: '0.14em', color: 'var(--d-ink-80)', textTransform: 'uppercase' }}>{s.label}</span>
            </div>
            <div className='tabular' style={{ fontFamily: 'var(--font-sans)', fontWeight: 500, fontSize: 24, letterSpacing: '-0.02em' }}>{s.value}</div>
            <div style={{ fontSize: 10, letterSpacing: '0.1em', color: 'var(--d-ink-60)', marginTop: 4, textTransform: 'uppercase' }}>{s.pct}% of total</div>
            {STRATEGY_DESC[s.label] && <div style={{ fontSize: 12, color: 'var(--d-ink-60)', marginTop: 10, lineHeight: 1.5 }}>{STRATEGY_DESC[s.label]}</div>}
          </div>
        ))}
      </div>
    </div>
  )
}

export function CompositionCard({ total, segments }: { total: string; segments: CompositionSegment[] }) {
  return (
    <Card detail={<CompositionDetail total={total} segments={segments} />}>
      <ExpandGlyph />
      <div className='dash-card-label' style={{ marginBottom: 12 }}>
        Deployed asset composition
        <InfoBadge title='Breakdown of deployed capital across telecom strategies.' />
      </div>
      <div className='dash-card-value tabular' style={{ marginBottom: 4 }}>
        {total}
      </div>
      <div className='dash-card-sub' style={{ marginBottom: 14 }}>
        Deployed
      </div>
      <div
        style={{
          height: 11,
          borderRadius: 999,
          background: compositionGradient(segments),
        }}
      />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 18 }}>
        {segments.map((s, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span className='dash-legend-dot' style={{ background: s.color }} />
            <span
              style={{ flex: 1, fontSize: 10, letterSpacing: '0.14em', color: 'var(--d-ink-60)', fontWeight: 500 }}
            >
              {String(i + 1).padStart(2, '0')} · {s.label}
            </span>
            <span
              className='tabular'
              style={{ fontSize: 10, letterSpacing: '0.14em', color: 'var(--d-ink-60)', width: 36, textAlign: 'right' }}
            >
              {s.pct}%
            </span>
            <span
              className='tabular'
              style={{ fontSize: 10, letterSpacing: '0.14em', color: 'var(--d-text)', width: 40, textAlign: 'right', fontWeight: 500 }}
            >
              {s.value}
            </span>
          </div>
        ))}
      </div>
    </Card>
  )
}

// ── Utilization rate (donut) ─────────────────────────────────────
// One legend row: real deployed/reserve in "Split", reserve breakdown in
// "Reserve mix". infrafi-api has no reserve-composition feed, so the mix values
// render as skeletons (the categories are the designed labels).
function UtilRow({ color, label, value }: { color: string; label: string; value: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 9 }}>
        <span className='dash-legend-dot' style={{ background: color }} />
        <span style={{ fontSize: 14, letterSpacing: '0.14em', color: 'var(--d-text)' }}>{label}</span>
      </span>
      <span
        className='tabular'
        style={{ fontSize: 18, fontWeight: 500, letterSpacing: '0.04em', color: 'var(--d-text)' }}
      >
        {value}
      </span>
    </div>
  )
}

function UtilizationDetail({
  pct,
  deployed,
  reserve,
  total,
  about,
}: {
  pct: number
  deployed: string
  reserve: string
  total: string
  about?: string
}) {
  const [view, setView] = useState<'util' | 'reserve'>('util')
  const N = 30
  const series = mockHistory(Number.isFinite(pct) ? pct : 0, N, 4242, 0.08)
  const xLabels = pickAxisDates(recentDates(N))
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <DetailHeader kicker='Utilization' title='Capital deployed vs reserves held' />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 11, letterSpacing: '0.14em', color: 'var(--d-ink-60)', textTransform: 'uppercase' }}>
          {view === 'util' ? 'Utilization over time' : 'Reserve mix'}
        </span>
        <SegmentedToggle
          value={view}
          onChange={setView}
          equalWidth
          options={[
            { value: 'util', label: 'Utilization' },
            { value: 'reserve', label: 'Reserve mix' },
          ]}
        />
      </div>
      {view === 'util' ? (
        <AreaSpark data={series} color='#f3a24a' formatValue={(n) => `${n.toFixed(1)}%`} xLabels={xLabels} pointDates={recentDates(N)} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18, padding: '20px 0' }}>
          <UtilRow color='#7ed9a8' label='T-Bill backed' value='$60.0K' />
          <UtilRow color='#f3a24a' label='USD.tel idle' value='$28.0K' />
          <UtilRow color='#9b7bff' label='Insurance' value='$6.0K' />
        </div>
      )}
      <div className='dash-detail-stat-grid' style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
        <DetailStatPanel label='Deployed' value={deployed} sub={`of ${total}`} />
        <DetailStatPanel label='Reserve' value={reserve} sub='held in buffer' />
        <DetailStatPanel label='Target util' value='35%' sub='set by governance' />
      </div>
      {about && <DetailFooter label='About'>{about}</DetailFooter>}
    </div>
  )
}

export function UtilizationCard({
  pct,
  deployed,
  reserve,
  total,
  about,
}: {
  pct: number
  deployed: string
  reserve: string
  total: string
  about?: string
}) {
  const [view, setView] = useState<'split' | 'reserve'>('split')
  return (
    <Card detail={<UtilizationDetail pct={pct} deployed={deployed} reserve={reserve} total={total} about={about} />}>
      <ExpandGlyph />
      <div className='dash-card-label' style={{ marginBottom: 8 }}>
        Utilization rate
        <InfoBadge title='Share of vault capital actively deployed vs held in reserve.' />
      </div>
      <div style={{ display: 'flex', justifyContent: 'center', marginTop: 10 }}>
        <div style={{ position: 'relative', width: 80, height: 80 }}>
          <Donut pct={pct} size={80} thickness={8} />
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <span
              className='tabular'
              style={{ fontFamily: 'var(--font-sans)', fontSize: 22, fontWeight: 500, color: 'var(--d-text)' }}
            >
              {Number.isFinite(pct) ? `${pct}%` : '—'}
            </span>
          </div>
        </div>
      </div>
      <div
        className='tabular'
        style={{ textAlign: 'center', marginTop: 10, fontSize: 12, color: 'var(--d-ink-60)' }}
      >
        {deployed} / {total}
      </div>
      <div style={{ display: 'flex', justifyContent: 'center', marginTop: 12, marginBottom: 18 }}>
        <SegmentedToggle
          value={view}
          onChange={setView}
          equalWidth
          options={[
            { value: 'split', label: 'Split' },
            { value: 'reserve', label: 'Reserve mix' },
          ]}
        />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-evenly', height: 66 }}>
        {view === 'split' ? (
          <>
            <UtilRow color='#eb6567' label='Deployed' value={deployed} />
            <UtilRow color='#424243' label='Reserve' value={reserve} />
          </>
        ) : (
          <>
            <UtilRow color='#7ed9a8' label='T-Bill backed' value='$60.0K' />
            <UtilRow color='#f3a24a' label='USD.tel idle' value='$28.0K' />
            <UtilRow color='#9b7bff' label='Insurance' value='$6.0K' />
          </>
        )}
      </div>
    </Card>
  )
}

// ── Active deployments ───────────────────────────────────────────
// Online/Queued/In-review counts + share bars are derived from real project
// lifecycle status, and the weekly delta from project created_at (see
// DashboardPageContent). The "By tier" operator breakdown has no infrafi-api
// feed yet, so TIERS stays a design mock; the layout mirrors the Figma 1:1.
export type DeploymentCount = { label: string; value: string }
export type DeploymentBar = { label: string; pct: number; color: string }

const TIERS = [
  { label: 'Operators · Tier 1', color: '#d18d44', count: '96', pct: '67.6%' },
  { label: 'Operators · Tier 2', color: '#e84066', count: '32', pct: '22.5%' },
  { label: 'Operators · Tier 3', color: '#ed7c5b', count: '14', pct: '9.9%' },
]

// Shared body (counts · share bars · tiers) used by both the card and its
// expanded detail so the two stay in lockstep.
function DeploymentBreakdown({ counts, bars }: { counts: DeploymentCount[]; bars: DeploymentBar[] }) {
  return (
    <>
      {/* Online / Queued / In review counts */}
      <div style={{ display: 'flex', marginBottom: 26 }}>
        {counts.map((c, i) => (
          <div
            key={c.label}
            style={{
              flex: 1,
              borderLeft: i === 0 ? 'none' : '1px solid var(--d-line)',
              paddingLeft: i === 0 ? 0 : 22,
            }}
          >
            <div
              className='tabular'
              style={{ fontSize: 30, fontWeight: 500, lineHeight: 1.15, color: 'var(--d-text)', marginBottom: 2 }}
            >
              {c.value}
            </div>
            <div style={{ fontSize: 12, color: 'var(--d-ink-40)' }}>{c.label}</div>
          </div>
        ))}
      </div>

      {/* Online / Queued share bars */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 18, marginBottom: 22 }}>
        {bars.map((b) => (
          <div key={b.label} style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <span style={{ width: 58, fontSize: 10, letterSpacing: '0.14em', color: 'var(--d-text)' }}>{b.label}</span>
            <div className='dash-bar-track' style={{ flex: 1, height: 6 }}>
              <div className='dash-bar-fill' style={{ width: `${b.pct}%`, background: b.color }} />
            </div>
            <span
              className='tabular'
              style={{ width: 44, textAlign: 'right', fontSize: 10, letterSpacing: '0.1em', color: 'var(--d-ink-80)' }}
            >
              {b.pct}%
            </span>
          </div>
        ))}
      </div>

      <div style={{ borderTop: '1px solid var(--d-line)', paddingTop: 18 }}>
        <div style={{ fontSize: 10, letterSpacing: '0.14em', color: 'var(--d-ink-60)', marginBottom: 16 }}>By tier</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
          {TIERS.map((t) => (
            <div key={t.label} style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <span className='dash-legend-dot' style={{ background: t.color }} />
              <span style={{ flex: 1, fontSize: 10, letterSpacing: '0.14em', color: 'var(--d-ink-80)', fontWeight: 500 }}>
                {t.label}
              </span>
              <span
                className='tabular'
                style={{ width: 32, textAlign: 'right', fontSize: 10, letterSpacing: '0.1em', color: 'var(--d-ink-60)' }}
              >
                {t.count}
              </span>
              <span
                className='tabular'
                style={{ width: 39, textAlign: 'right', fontSize: 10, letterSpacing: '0.1em', color: 'var(--d-text)' }}
              >
                {t.pct}
              </span>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}

function ActiveDeploymentsDetail({ counts, bars, deltaLabel }: ActiveDeploymentsProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <DetailHeader kicker='Active deployments' title='Validated operators on the network' />
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span className='dash-card-sub'>Validated operators</span>
        <DeltaPill value={deltaLabel} positive />
      </div>
      <DeploymentBreakdown counts={counts} bars={bars} />
      <DetailFooter label='About'>Validated operators running telecom deployments funded by the vault.</DetailFooter>
    </div>
  )
}

type ActiveDeploymentsProps = {
  counts: DeploymentCount[]
  bars: DeploymentBar[]
  deltaLabel: string
}

export function ActiveDeploymentsCard({ counts, bars, deltaLabel }: ActiveDeploymentsProps) {
  return (
    <Card detail={<ActiveDeploymentsDetail counts={counts} bars={bars} deltaLabel={deltaLabel} />}>
      <ExpandGlyph />
      <div className='dash-card-label' style={{ marginBottom: 8 }}>
        Active deployments
        <InfoBadge title='Validated operators running telecom deployments funded by the vault.' />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 22 }}>
        <span className='dash-card-sub'>Validated operators</span>
        <DeltaPill value={deltaLabel} positive />
      </div>
      <DeploymentBreakdown counts={counts} bars={bars} />
    </Card>
  )
}

// ── Cumulative yield (real cumulative_yield series) ──────────────
function CumulativeYieldDetail({
  data,
  dates,
  formatValue,
  about,
}: {
  data: number[]
  dates: string[]
  formatValue: (n: number) => string
  about?: string
}) {
  const [range, setRange] = useState<RangeKey>('30D')
  const sliced = sliceByRange(data, dates, range)
  const series = sliced.data.length >= 2 ? sliced.data : data
  const xLabels = pickAxisDates(sliced.dates.length >= 2 ? sliced.dates : dates)
  const current = series[series.length - 1]
  const first = series[0]
  const change = changeFromStart(current, first, formatValue)
  const high = Math.max(...series)
  const low = Math.min(...series)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <DetailHeader kicker='Cumulative yield' title='Cumulative yield' />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap' }}>
          <DetailStat label='Current' value={formatValue(current)} />
          <DetailStat label='Change' value={change.label} tone={change.positive ? 'pos' : 'neg'} />
          <DetailStat label={`${range} High`} value={formatValue(high)} />
          <DetailStat label={`${range} Low`} value={formatValue(low)} />
        </div>
        <DetailRangeTabs value={range} onChange={setRange} />
      </div>
      <AreaSpark
        data={series}
        color='#f3a24a'
        formatValue={formatValue}
        xLabels={xLabels}
        pointDates={sliced.dates.length >= 2 ? sliced.dates : dates}
      />
      {about && <DetailFooter label='About'>{about}</DetailFooter>}
    </div>
  )
}

export function CumulativeYieldCard({
  pct,
  nav,
  data,
  startLabel,
  lastUpdate,
  formatValue,
  dates = [],
  about,
}: {
  pct: string
  nav: string
  data: number[]
  startLabel: string
  lastUpdate: string
  formatValue?: (n: number) => string
  dates?: string[]
  about?: string
}) {
  const fmt = formatValue ?? ((n: number) => `${n.toFixed(2)}%`)
  return (
    <Card detail={<CumulativeYieldDetail data={data} dates={dates} formatValue={fmt} about={about} />}>
      <ExpandGlyph />
      <div className='dash-card-label' style={{ marginBottom: 12 }}>
        Cumulative yield
        <InfoBadge title='Total yield accrued by the vault since inception.' />
      </div>
      <div className='dash-card-sub' style={{ marginBottom: 14 }}>
        Daily · Since inception
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
        <span className='dash-card-value tabular'>{pct}</span>
        {nav && (
          <span className='dash-delta pos'>
            {nav} NAV
          </span>
        )}
      </div>
      <div style={{ marginLeft: -4, marginRight: -4, paddingTop: 10, paddingBottom: 10 }}>
        <AreaSpark data={data} color='#f3a24a' width={630} height={98} strokeWidth={2} pad={8} formatValue={formatValue} />
      </div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: 8,
          fontSize: 10,
          letterSpacing: '0.04em',
          color: 'var(--d-ink-60)',
        }}
      >
        <span>{startLabel}</span>
        <span>Today</span>
      </div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: 14,
          paddingTop: 14,
          borderTop: '1px solid var(--d-line)',
          fontSize: 12,
          color: 'var(--d-ink-40)',
        }}
      >
        <span>Inception · {startLabel}</span>
        <span>Last update · {lastUpdate}</span>
      </div>
    </Card>
  )
}
