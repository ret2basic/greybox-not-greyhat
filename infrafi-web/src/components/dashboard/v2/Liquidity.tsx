'use client'

import { useId, useMemo, useRef, useState } from 'react'
import { navSeries } from '@/components/dashboard/mock-data'
import {
  buildSmoothSegments,
  formatTimestamp,
  parseSeriesDate,
  type RangeKey,
  smoothPath,
  smoothYAtX,
} from '@/components/dashboard/utils'
import { LIQUIDITY_ROWS } from '@/components/boost/data'
import { formatPct } from '@/lib/boost/apy'
import { formatUsdCompact } from '@/lib/partners/orca'
import { useOrcaPoolStats } from '@/hooks/boost/useOrcaPoolStats'
import {
  DetailFooter,
  DetailHeader,
  DetailRangeTabs,
  DetailStatPanel,
  pickAxisDates,
  sliceByRange,
} from './charts'
import { Card, ExpandGlyph, InfoBadge, useExpanded } from './ui'

// NAV is the real exchange-rate history. `marketSpot` is the live secondary
// price from Orca (the only venue with DAWN liquidity), in the same units as
// NAV. Orca's pool API is a snapshot with no per-day history, so we can only
// plot the current spot — the market line is held flat at it. When the spot
// isn't loaded yet, the market falls back to NAV (zero spread) rather than a
// fabricated quote. Falls back to the mock navSeries only when no real NAV.
function buildNavSeries(
  navReal: number[],
  marketSpot?: number,
): Array<{ nav: number; mkt: number }> {
  const navs = navReal && navReal.length >= 2 ? navReal : navSeries(30).map((p) => p.nav)
  const mkt = (nav: number) => (marketSpot && marketSpot > 0 ? marketSpot : nav)
  return navs.map((nav) => ({ nav, mkt: mkt(nav) }))
}

// Live secondary-market price of sUSD.tel from Orca (the only venue with DAWN
// liquidity), in NAV units. The USD.tel/sUSD.tel whirlpool reports price as
// sUSD.tel per USD.tel (token B per token A), so a share's value in USD.tel —
// comparable to NAV — is the inverse. Undefined until the pool snapshot loads.
function useOrcaMarketSpot(): number | undefined {
  const stats = useOrcaPoolStats()
  const price = stats['orca-susdtel-usdtel']?.price
  return price && price > 0 ? 1 / price : undefined
}

// ── On-chain liquidity ───────────────────────────────────────────
// Real per-pool TVL for DAWN's Orca whirlpools, read from the same live feed
// the Boost page uses (`useOrcaPoolStats`, proxied through Orca's public pool
// API). Orca is currently the ONLY venue with DAWN liquidity, and the API
// exposes a snapshot — no per-day history — so we render the live composition
// (TVL share per pool) rather than a fabricated time series. Pool descriptors
// (pair, type, deposit link) come straight from the Boost strategy rows so the
// two surfaces never diverge.
const POOL_COLORS: Record<string, string> = {
  'orca-susdtel-usdtel': '#f3a24a',
  'orca-usdtel-usdc': '#9b7bff',
}
const ORCA_POOLS = LIQUIDITY_ROWS.filter((row) => row.protocol === 'Orca')

type LivePool = {
  id: string
  pair: string
  poolType: string
  depositUrl?: string
  color: string
  tvlUsd: number
  tvl: string
  feeAprPct: number
}

// Merges the static Orca pool descriptors with live TVL / fee APR. `loaded` is
// false until at least one pool resolves, so the card can show an honest empty
// state instead of a fabricated zero.
export function useOrcaLiquidity() {
  const stats = useOrcaPoolStats()
  const pools: LivePool[] = ORCA_POOLS.map((row) => {
    const raw = stats[row.id]
    return {
      id: row.id,
      pair: row.pair,
      poolType: row.poolType,
      depositUrl: row.depositUrl,
      color: POOL_COLORS[row.id] ?? '#7ed9a8',
      tvlUsd: raw?.tvlUsd ?? 0,
      tvl: raw?.tvl ?? '—',
      feeAprPct: raw?.feeAprPct ?? 0,
    }
  })
  const loaded = Object.keys(stats).length > 0
  const totalUsd = pools.reduce((sum, p) => sum + p.tvlUsd, 0)
  return { pools, loaded, totalUsd, total: loaded ? formatUsdCompact(totalUsd) : '—' }
}

// One pool as a proportional TVL gauge: pair · live TVL, a share-of-total bar,
// and pool type · fee APR. The fill animates from 0 so the snapshot reads as
// "just measured" without implying historical movement.
function PoolGauge({
  pool,
  totalUsd,
  loaded,
}: {
  pool: LivePool
  totalUsd: number
  loaded: boolean
}) {
  const share = totalUsd > 0 ? (pool.tvlUsd / totalUsd) * 100 : 0
  const fill = loaded && share > 0 ? Math.max(share, 2) : 0
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: 12,
        }}
      >
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <span className='dash-legend-dot' style={{ background: pool.color }} />
          <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--d-ink-80)' }}>
            {pool.pair}
          </span>
        </span>
        <span className='tabular' style={{ fontSize: 13, fontWeight: 500 }}>
          {loaded ? pool.tvl : '—'}
        </span>
      </div>
      <div
        style={{
          height: 8,
          borderRadius: 999,
          background: 'var(--d-bg)',
          border: '1px solid var(--d-line)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${fill}%`,
            height: '100%',
            borderRadius: 999,
            background: `linear-gradient(90deg, ${pool.color}, ${pool.color}b3)`,
            transition: 'width 600ms cubic-bezier(0.2, 0.7, 0.2, 1)',
          }}
        />
      </div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: 10,
          letterSpacing: '0.04em',
          color: 'var(--d-ink-60)',
        }}
      >
        <span>{pool.poolType}</span>
        <span className='tabular'>
          {loaded ? `${share.toFixed(0)}% · Fee APR ${formatPct(pool.feeAprPct)}` : 'Fetching…'}
        </span>
      </div>
    </div>
  )
}

// Expand-modal detail — total headline, the same per-pool gauges, a per-pool
// stat grid (live TVL · share · fee APR + deposit link), and a footer naming
// the data source.
function OnChainLiquidityDetail({
  pools,
  loaded,
  totalUsd,
  total,
}: ReturnType<typeof useOrcaLiquidity>) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <DetailHeader
        kicker='On-chain liquidity'
        title="Live TVL across DAWN's Orca pools on Solana"
      />
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
        <span className='dash-card-value tabular' style={{ fontSize: 30 }}>
          {total}
        </span>
        <span style={{ fontSize: 13, color: 'var(--d-ink-60)' }}>
          total across {pools.length} pools
        </span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
        {pools.map((p) => (
          <PoolGauge key={p.id} pool={p} totalUsd={totalUsd} loaded={loaded} />
        ))}
      </div>
      <div
        className='dash-detail-stat-grid'
        style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 14 }}
      >
        {pools.map((p) => {
          const share = totalUsd > 0 ? Math.round((p.tvlUsd / totalUsd) * 100) : 0
          return (
            <div
              key={p.id}
              className='dash-detail-stat-tile'
              style={{
                padding: 16,
                borderRadius: 12,
                border: '1px solid var(--d-line)',
                background: 'var(--d-bg)',
              }}
            >
              <div
                className='dash-detail-stat-tile-legend'
                style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}
              >
                <span className='dash-legend-dot' style={{ background: p.color }} />
                <span
                  style={{
                    fontSize: 11,
                    letterSpacing: '0.14em',
                    color: 'var(--d-ink-80)',
                    textTransform: 'uppercase',
                  }}
                >
                  {p.pair}
                </span>
              </div>
              <div
                className='tabular'
                style={{
                  fontFamily: 'var(--font-sans)',
                  fontWeight: 500,
                  fontSize: 24,
                  letterSpacing: '-0.02em',
                }}
              >
                {loaded ? p.tvl : '—'}
              </div>
              <div
                style={{
                  fontSize: 10,
                  letterSpacing: '0.1em',
                  color: 'var(--d-ink-60)',
                  marginTop: 4,
                  textTransform: 'uppercase',
                }}
              >
                {loaded ? `${share}% of total · Fee APR ${formatPct(p.feeAprPct)}` : '—'}
              </div>
              {p.depositUrl && (
                <a
                  href={p.depositUrl}
                  target='_blank'
                  rel='noreferrer'
                  style={{
                    display: 'inline-block',
                    marginTop: 12,
                    fontSize: 12,
                    fontWeight: 500,
                    color: 'var(--d-amber)',
                  }}
                >
                  Provide liquidity →
                </a>
              )}
            </div>
          )
        })}
      </div>
      <DetailFooter label='Where this comes from'>
        Pulled live from Orca&apos;s public pool API for DAWN&apos;s two concentrated-liquidity
        whirlpools on Solana. Orca is currently the only venue with DAWN liquidity; other venues
        will appear here as sUSD.tel lists across more DEXs.
      </DetailFooter>
    </div>
  )
}

export function MarketDepthCard() {
  const liquidity = useOrcaLiquidity()
  const { pools, loaded, totalUsd, total } = liquidity
  return (
    <Card detail={<OnChainLiquidityDetail {...liquidity} />}>
      <ExpandGlyph />
      <div className='dash-card-label' style={{ marginBottom: 12 }}>
        On-chain liquidity
        <InfoBadge title="Live TVL across DAWN's Orca pools on Solana." />
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 24 }}>
        <span className='dash-card-value tabular'>{total}</span>
        <span style={{ fontSize: 14, color: 'var(--d-ink-40)' }}>Orca · Solana</span>
        <span className={`dash-delta ${loaded ? 'pos' : ''}`} style={{ gap: 6 }}>
          <span style={{ width: 4, height: 4, borderRadius: '50%', background: 'currentColor' }} />
          {loaded ? 'Live' : 'Loading'}
        </span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
        {pools.map((p) => (
          <PoolGauge key={p.id} pool={p} totalUsd={totalUsd} loaded={loaded} />
        ))}
      </div>
    </Card>
  )
}

// ── NAV vs market ────────────────────────────────────────────────
// NAV is the real exchange-rate history. There is no secondary-market price
// feed, so the market line is a deterministic MOCK wiggle around NAV and the
// spread headline / "Tight" badge are the design's mock values. Falls back to
// the mock navSeries when no real history is loaded yet.
function NavMarketChart({
  navReal,
  height = 204,
  xLabels,
  pointDates,
  marketSpot,
}: {
  navReal: number[]
  height?: number
  xLabels?: string[]
  pointDates?: string[]
  marketSpot?: number
}) {
  const id = useId()
  const expanded = useExpanded()
  const series = useMemo(() => buildNavSeries(navReal, marketSpot), [navReal, marketSpot])

  const width = 583
  const padL = 46
  const padR = 8
  const padT = 12
  const padB = expanded ? 30 : 14
  const H = expanded ? 300 : height
  const innerW = width - padL - padR
  const innerH = H - padT - padB
  const all = series.flatMap((d) => [d.nav, d.mkt])
  const min = Math.min(...all)
  const max = Math.max(...all)
  const span = max - min || 1
  const lo = min - span * 0.12
  const hi = max + span * 0.12
  const x = (i: number) => padL + (i / (series.length - 1)) * innerW
  const y = (v: number) => padT + (1 - (v - lo) / (hi - lo)) * innerH

  const navPts = series.map((d, i) => [x(i), y(d.nav)] as [number, number])
  const navSegs = buildSmoothSegments(navPts)
  const navLine = smoothPath(navPts)
  const navArea = `${navLine} L ${x(series.length - 1)} ${padT + innerH} L ${padL} ${padT + innerH} Z`
  const mktLine = series.map((d, i) => `${i === 0 ? 'M' : 'L'} ${x(i)} ${y(d.mkt)}`).join(' ')
  const band =
    series.map((d, i) => `${i === 0 ? 'M' : 'L'} ${x(i)} ${y(d.nav)}`).join(' ') +
    ' ' +
    series
      .map((d, i) => `L ${x(series.length - 1 - i)} ${y(series[series.length - 1 - i].mkt)}`)
      .join(' ') +
    ' Z'
  const ticks = [hi, (hi + lo) / 2, lo]

  // Per-pixel hover (expanded only): NAV dot rides the smooth curve, market dot
  // rides its straight line, and the tooltip reads both values + the spread at
  // the exact cursor position.
  const plotRef = useRef<HTMLDivElement | null>(null)
  const [hoverX, setHoverX] = useState<number | null>(null)
  const onMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!plotRef.current) return
    const rect = plotRef.current.getBoundingClientRect()
    const vx = ((e.clientX - rect.left) / rect.width) * width
    setHoverX(Math.max(padL, Math.min(width - padR, vx)))
  }
  const datesAligned = pointDates && pointDates.length === series.length
  const hover =
    expanded && hoverX != null
      ? (() => {
          const frac = innerW > 0 ? (hoverX - padL) / innerW : 0
          const fi = frac * (series.length - 1)
          const loI = Math.floor(fi)
          const hiI = Math.min(loI + 1, series.length - 1)
          const f = fi - loI
          const navY = smoothYAtX(navSegs, hoverX)
          const navV = lo + (1 - (navY - padT) / innerH) * (hi - lo)
          const mktV = series[loI].mkt + (series[hiI].mkt - series[loI].mkt) * f
          const spreadBps = navV !== 0 ? ((mktV - navV) / navV) * 10000 : 0
          let label = ''
          if (datesAligned) {
            const t0 = parseSeriesDate(pointDates![loI])
            const t1 = parseSeriesDate(pointDates![hiI])
            label = formatTimestamp(t0 + (t1 - t0) * f, pointDates)
          }
          return {
            leftPct: (hoverX / width) * 100,
            navTopPct: (navY / H) * 100,
            mktTopPct: (y(mktV) / H) * 100,
            navV,
            mktV,
            spreadBps,
            label,
          }
        })()
      : null

  return (
    <div
      ref={plotRef}
      style={{ position: 'relative', height: H, cursor: expanded ? 'crosshair' : undefined }}
      onMouseMove={expanded ? onMove : undefined}
      onMouseLeave={expanded ? () => setHoverX(null) : undefined}
    >
      <svg
        width='100%'
        height={H}
        viewBox={`0 0 ${width} ${H}`}
        preserveAspectRatio='none'
        style={{ display: 'block' }}
      >
        <defs>
          <linearGradient id={`navfill-${id}`} x1='0' y1='0' x2='0' y2='1'>
            <stop offset='0%' stopColor='#f3a24a' stopOpacity='0.18' />
            <stop offset='100%' stopColor='#f3a24a' stopOpacity='0' />
          </linearGradient>
        </defs>
        {ticks.map((_, i) => {
          const yy = padT + (i / (ticks.length - 1)) * innerH
          return (
            <line
              key={i}
              x1={padL}
              x2={width - padR}
              y1={yy}
              y2={yy}
              stroke='var(--d-line)'
              strokeWidth='1'
              strokeDasharray='2 3'
            />
          )
        })}
        <path d={navArea} fill={`url(#navfill-${id})`} stroke='none' />
        <path d={band} fill='rgba(155,123,255,0.10)' stroke='none' />
        <path
          d={navLine}
          fill='none'
          stroke='#f3a24a'
          strokeWidth='2'
          vectorEffect='non-scaling-stroke'
        />
        <path
          d={mktLine}
          fill='none'
          stroke='#9b7bff'
          strokeWidth='1.5'
          strokeDasharray='3 2'
          vectorEffect='non-scaling-stroke'
        />
      </svg>
      {ticks.map((t, i) => {
        const yy = padT + (i / (ticks.length - 1)) * innerH
        return (
          <span
            key={i}
            className='tabular'
            style={{
              position: 'absolute',
              left: 0,
              top: (yy / H) * 100 + '%',
              transform: 'translateY(-50%)',
              fontSize: 9,
              color: 'var(--d-ink-60)',
            }}
          >
            {t.toFixed(4)}
          </span>
        )
      })}
      {expanded &&
        xLabels &&
        xLabels.map((l, i) => (
          <span
            key={`x-${i}`}
            className='tabular'
            style={{
              position: 'absolute',
              left: `${((padL + (i / (xLabels.length - 1)) * innerW) / width) * 100}%`,
              top: `${((padT + innerH) / H) * 100}%`,
              marginTop: 6,
              transform: 'translateX(-50%)',
              fontSize: 9,
              letterSpacing: '0.04em',
              color: 'var(--d-ink-60)',
              whiteSpace: 'nowrap',
            }}
          >
            {l}
          </span>
        ))}
      {hover && (
        <>
          <div
            style={{
              position: 'absolute',
              left: `${hover.leftPct}%`,
              top: `${(padT / H) * 100}%`,
              width: 1,
              height: `${(innerH / H) * 100}%`,
              background: 'rgba(255,255,255,0.6)',
              pointerEvents: 'none',
            }}
          />
          {[
            { topPct: hover.mktTopPct, c: '#9b7bff' },
            { topPct: hover.navTopPct, c: '#f3a24a' },
          ].map((d, i) => (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: `${hover.leftPct}%`,
                top: `${d.topPct}%`,
                transform: 'translate(-50%, -50%)',
                width: 9,
                height: 9,
                borderRadius: '50%',
                background: d.c,
                border: '1.5px solid #0b0814',
                pointerEvents: 'none',
              }}
            />
          ))}
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
              minWidth: 138,
              pointerEvents: 'none',
              boxShadow: '0 8px 24px -8px rgba(0,0,0,0.4)',
              zIndex: 5,
            }}
          >
            {hover.label && (
              <div style={{ fontSize: 9, letterSpacing: '0.12em', color: 'var(--d-ink-60)', textTransform: 'uppercase', marginBottom: 6 }}>
                {hover.label}
              </div>
            )}
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ color: '#f3a24a' }}>NAV</span>
              <span>${hover.navV.toFixed(4)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ color: '#9b7bff' }}>Market</span>
              <span>${hover.mktV.toFixed(4)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid var(--d-line)', paddingTop: 4, marginTop: 2 }}>
              <span style={{ color: 'var(--d-ink-60)' }}>Spread</span>
              <span>{hover.spreadBps.toFixed(1)} bps</span>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function NavMarketLegend() {
  return (
    <div style={{ display: 'flex', gap: 18 }}>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <span style={{ width: 11, height: 3, borderRadius: 2, background: '#f3a24a' }} />
        <span
          style={{
            fontSize: 10,
            letterSpacing: '0.14em',
            color: 'var(--d-ink-80)',
            fontWeight: 500,
          }}
        >
          NAV
        </span>
      </span>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <span style={{ width: 11, height: 3, borderRadius: 2, background: '#9b7bff' }} />
        <span
          style={{
            fontSize: 10,
            letterSpacing: '0.14em',
            color: 'var(--d-ink-80)',
            fontWeight: 500,
          }}
        >
          Market (Orca)
        </span>
      </span>
    </div>
  )
}

function NavVsMarketDetail({ navData, dates }: { navData: number[]; dates: string[] }) {
  const [range, setRange] = useState<RangeKey>('30D')
  const marketSpot = useOrcaMarketSpot()
  const sliced = sliceByRange(navData, dates, range)
  const series = sliced.data.length >= 2 ? sliced.data : navData
  const xLabels = pickAxisDates(sliced.dates.length >= 2 ? sliced.dates : dates)
  const built = buildNavSeries(series, marketSpot)
  const today = built[built.length - 1]
  const first = built[0]
  const n = built.length
  const apy = first && first.nav > 0 && n > 1 ? ((today.nav / first.nav) ** (365 / n) - 1) * 100 : 0
  const fmtP = (v: number) => `$${v.toFixed(4)}`
  // Real spread of the live Orca spot vs current NAV (bps). Null until the
  // pool snapshot loads, in which case the market line tracks NAV (0 spread).
  const spreadBps =
    marketSpot && today.nav > 0 ? ((today.mkt - today.nav) / today.nav) * 10000 : null
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <DetailHeader kicker='NAV vs market' title='Mint/redeem price vs secondary market price' />
      <div>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 16,
            marginBottom: 14,
            flexWrap: 'nowrap',
          }}
        >
          <span
            style={{
              fontSize: 11,
              letterSpacing: '0.14em',
              color: 'var(--d-ink-60)',
              textTransform: 'uppercase',
              minWidth: 0,
            }}
          >
            NAV vs market · {range}
          </span>
          <div style={{ flexShrink: 0 }}>
            <DetailRangeTabs value={range} onChange={setRange} />
          </div>
        </div>
        <NavMarketChart
          navReal={series}
          xLabels={xLabels}
          pointDates={sliced.dates.length >= 2 ? sliced.dates : dates}
          marketSpot={marketSpot}
        />
        <div style={{ marginTop: 16, paddingLeft: 46 }}>
          <NavMarketLegend />
        </div>
      </div>
      <div
        className='dash-detail-stat-grid'
        style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}
      >
        <DetailStatPanel
          label='NAV today'
          value={fmtP(today.nav)}
          sub={`${apy >= 0 ? '+' : ''}${apy.toFixed(1)}% APY · ${range}`}
          subTone={apy >= 0 ? 'pos' : undefined}
        />
        <DetailStatPanel
          label='Market today'
          value={marketSpot ? fmtP(today.mkt) : '—'}
          sub='Orca whirlpool · spot'
        />
        <DetailStatPanel
          label='Spread'
          value={spreadBps != null ? `${spreadBps >= 0 ? '+' : ''}${spreadBps.toFixed(1)} bps` : '—'}
          sub='Orca spot vs NAV'
          subTone={spreadBps != null && Math.abs(spreadBps) <= 10 ? 'pos' : undefined}
        />
      </div>
      <DetailFooter label='Why it matters'>
        NAV is the price at which the protocol mints and redeems sUSD.tel directly. Market is what
        secondary buyers and sellers are paying on DEXs.
      </DetailFooter>
    </div>
  )
}

export function NavVsMarketCard({ navData, dates = [] }: { navData: number[]; dates?: string[] }) {
  const marketSpot = useOrcaMarketSpot()
  const lastNav = navData.length ? navData[navData.length - 1] : 0
  const spreadBps =
    marketSpot && lastNav > 0 ? ((marketSpot - lastNav) / lastNav) * 10000 : null
  const tight = spreadBps != null && Math.abs(spreadBps) <= 10
  return (
    <Card detail={<NavVsMarketDetail navData={navData} dates={dates} />}>
      <ExpandGlyph />
      <div className='dash-card-label' style={{ marginBottom: 12 }}>
        NAV vs market
        <InfoBadge title='On-chain NAV vs Orca secondary-market price.' />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 }}>
        <span className='dash-card-value tabular'>
          {spreadBps != null ? `${spreadBps >= 0 ? '+' : ''}${spreadBps.toFixed(1)} bps` : '—'}
        </span>
        <span style={{ fontSize: 14, color: 'var(--d-ink-40)' }}>Spread</span>
        {tight && (
          <span className='dash-delta pos' style={{ gap: 6 }}>
            <span style={{ width: 4, height: 4, borderRadius: '50%', background: 'currentColor' }} />
            Tight
          </span>
        )}
      </div>
      <NavMarketChart navReal={navData} marketSpot={marketSpot} />
      <div style={{ marginTop: 16, paddingLeft: 17 }}>
        <NavMarketLegend />
      </div>
    </Card>
  )
}
