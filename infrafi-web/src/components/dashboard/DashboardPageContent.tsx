'use client'

import { useEffect, useMemo, useState } from 'react'
import { KpiCard } from '@/components/dashboard/v2/KpiCard'
import {
  MarketDepthCard,
  NavVsMarketCard,
  useOrcaLiquidity,
} from '@/components/dashboard/v2/Liquidity'
import { DashboardSection, Hero, RangeTabs } from '@/components/dashboard/v2/sections'
import {
  CompositionCard,
  type CompositionSegment,
  CumulativeYieldCard,
  RevenueCard,
  UtilizationCard,
} from '@/components/dashboard/v2/YieldEngine'
import { RANGE_DAYS, type RangeKey } from '@/components/dashboard/utils'
import { historySharePrice, liveSharePrice, useNav, useProjects, useVault } from '@/store'

// Flatten sub-threshold jitter out of a series: each point holds the last
// shown value until it differs by at least `minStep`, at which point the real
// value is adopted. Slow drift still registers once it accumulates past the
// threshold (the comparison is against the last *shown* value, not the prior
// point). Used to keep cumulative yield from showing moves smaller than 0.01%.
function suppressMicroMoves(series: number[], minStep: number): number[] {
  if (series.length === 0) return series
  let shown = series[0]
  return series.map((v, i) => {
    if (i === 0) return v
    if (Math.abs(v - shown) >= minStep) shown = v
    return shown
  })
}

// Same idea as suppressMicroMoves, but the threshold is a *relative* percent of
// the last shown value — for level series (e.g. the ~$1.0 NAV price) where a
// 0.01% move is what counts as real, not an absolute 0.01.
function suppressMicroMovesPct(series: number[], minPct: number): number[] {
  if (series.length === 0) return series
  let shown = series[0]
  return series.map((v, i) => {
    if (i === 0) return v
    const denom = Math.abs(shown) || 1
    if ((Math.abs(v - shown) / denom) * 100 >= minPct) shown = v
    return shown
  })
}

// ── Formatting helpers ───────────────────────────────────────────
const fmtMoney = (amount: number): string => {
  if (!Number.isFinite(amount)) return '—'
  const abs = Math.abs(amount)
  if (abs >= 1_000_000_000) return `$${(amount / 1_000_000_000).toFixed(2)}B`
  if (abs >= 1_000_000) return `$${(amount / 1_000_000).toFixed(2)}M`
  if (abs >= 1_000) return `$${(amount / 1_000).toFixed(1)}K`
  return `$${amount.toFixed(0)}`
}

// 1:1 with the formatter Reserves & Projects uses for its stats row + strategy
// cards. We use this for any Dashboard value that should appear identically on
// R&P (deployed total, reserve, utilization split, strategy amounts) so the
// numbers don't diverge through display precision alone.
const fmtMoneyRP = (amount: number): string => {
  if (!Number.isFinite(amount)) return '—'
  if (amount >= 1_000_000) return `$${(amount / 1_000_000).toFixed(1)}M`
  if (amount >= 1_000) return `$${(amount / 1_000).toFixed(1)}K`
  return `$${amount.toFixed(0)}`
}

const fmtDelta = (data: number[]): { text: string; positive: boolean } => {
  const start = data[0]
  const end = data[data.length - 1]
  if (!Number.isFinite(start) || !Number.isFinite(end) || start === 0) {
    return { text: '0.0%', positive: true }
  }
  const pct = ((end - start) / Math.abs(start)) * 100
  return { text: `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`, positive: pct >= 0 }
}

const MONTH_LABELS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
]

// Human label per project strategy — mirrors the on-screen composition legend.
const STRATEGY_LABELS: Record<string, string> = {
  INTERNET_BUILD_OUT: 'Apartment buildings',
  CARRIER_OFFLOAD: 'Carrier offload',
  ISP_ACQUISITION: 'Acquisitions',
  FIBER_DEPLOYMENT: 'Fiber deployment',
  TOWER_BUILD: 'Tower build',
  EDGE_INFRASTRUCTURE: 'Edge infrastructure',
}
const SEGMENT_COLORS = ['#f3a24a', '#ed7c5b', '#e84066', '#c73e7c', '#9b7bff', '#5ba8e6']

export default function DashboardPageContent() {
  const [range, setRange] = useState<RangeKey>('All')
  const [open, setOpen] = useState({ overview: true, yield: true, defi: true })
  const nDays = RANGE_DAYS[range]

  const { nav, navHistory, fetchNav, fetchNavHistory } = useNav()
  const {
    projects,
    capitalByType,
    projectMetrics,
    fetchProjects,
    fetchCapitalByType,
    fetchProjectMetrics,
  } = useProjects()
  const { dryPowder, fetchDryPowder } = useVault()
  // Live Orca liquidity (same feed the card renders) for the Section-03 summary
  // chips, so the collapsed header never contradicts the expanded card.
  const orcaLiquidity = useOrcaLiquidity()

  useEffect(() => {
    fetchNav()
    fetchNavHistory(nDays)
    fetchProjects()
    fetchCapitalByType()
    fetchProjectMetrics()
    fetchDryPowder()
  }, [
    fetchNav,
    fetchNavHistory,
    fetchProjects,
    fetchCapitalByType,
    fetchProjectMetrics,
    fetchDryPowder,
    nDays,
  ])

  // Mirror Reserves & Projects: total deployed comes from projectMetrics so
  // the Dashboard's deployed/utilization headlines line up 1:1 with the R&P
  // stats row.
  const totalDeployedRaw = useMemo(
    () => projectMetrics.reduce((sum, m) => sum + m.deployed_value, 0),
    [projectMetrics],
  )

  // Effective APY — identical to the StatBarChip in TopNav. Weighted by
  // deployed value across ACTIVE projects only, then discounted by the live
  // utilization ratio so the chip and the Vault-Overview KPI agree to the
  // basis point. Returns null while inputs are still loading.
  const effectiveApy = useMemo<number | null>(() => {
    const totalDeployed = projectMetrics.reduce((s, m) => s + m.deployed_value, 0)
    const activeIds = new Set(projects.filter((p) => p.status === 'ACTIVE').map((p) => p.id))
    const active = projectMetrics.filter((m) => activeIds.has(m.project_id))
    const activeDeployed = active.reduce((s, m) => s + m.deployed_value, 0)
    if (activeDeployed <= 0) return null
    const weighted =
      active.reduce((s, m) => s + m.deployed_value * m.yield_rate, 0) / activeDeployed
    const totalCapital = totalDeployed + (dryPowder ?? 0)
    const utilization = totalCapital > 0 ? totalDeployed / totalCapital : 0
    return weighted * utilization * 100
  }, [projects, projectMetrics, dryPowder])

  // ── KPI series (real, from history) ────────────────────────────
  const tvlData = useMemo(() => {
    if (navHistory.length) return navHistory.map((h) => h.net_asset_value)
    return nav ? [nav.net_asset_value_raw] : [0]
  }, [nav, navHistory])

  // APY history mirrors the StatBarChip sparkline: per-snapshot raw apy times
  // utilization_rate, in percent. Using the same series the chip sparkline
  // renders keeps the KPI's chart and current value in lock-step with the
  // status bar.
  const apyData = useMemo(() => {
    if (navHistory.length) return navHistory.map((h) => h.apy * h.utilization_rate * 100)
    if (effectiveApy !== null) return [effectiveApy]
    return [Math.max((nav?.apy ?? 0) * 100, 0)]
  }, [nav?.apy, navHistory, effectiveApy])

  // sUSD.tel price history uses the same per-row resolver as the status bar
  // chip — exchange_rate when plausible, otherwise NAV / shares (then NAV /
  // capital_basis) — so the dashboard never falls back to an unscaled raw
  // exchange_rate (which currently renders as ~$906 on the live snapshot).
  const priceData = useMemo(() => {
    // Suppress sub-0.01% (1 bp) jitter so the chart/delta reflect real price
    // moves rather than resolver noise blown up by auto-scaling.
    if (navHistory.length) return suppressMicroMovesPct(navHistory.map(historySharePrice), 0.01)
    return nav ? [liveSharePrice(nav)] : [0]
  }, [nav, navHistory])

  const tvlDelta = fmtDelta(tvlData)
  const apyDelta = fmtDelta(apyData)
  const priceDelta = fmtDelta(priceData)

  const tvlValue = nav ? fmtMoney(nav.net_asset_value_raw) : '—'
  // Match TopNav's StatBarChip: `${apyRaw.toFixed(1)}%`.
  const apyValue =
    effectiveApy !== null
      ? `${effectiveApy.toFixed(1)}%`
      : nav
        ? `${(nav.apy * 100).toFixed(1)}%`
        : '—'
  // Match TopNav's StatBarChip: `$${priceRaw.toFixed(3)}`.
  const priceRaw = nav ? liveSharePrice(nav) : null
  const priceValue = priceRaw !== null && priceRaw > 0 ? `$${priceRaw.toFixed(3)}` : '—'

  // Per-metric y-scale formatters + the full per-point date series that the
  // expand-modal detail panels use to label/slice their axis charts.
  const fmtPct = (n: number): string => `${n.toFixed(2)}%`
  const fmtPrice = (n: number): string => `$${n.toFixed(2)}`
  const navDates = useMemo(() => navHistory.map((h) => h.date), [navHistory])

  // ── Monthly revenue (bucket interest_profit by calendar month) ──
  const revenue = useMemo(() => {
    const byMonth = new Map<string, { v: number; label: string }>()
    for (const h of navHistory) {
      const d = new Date(h.date)
      if (Number.isNaN(d.getTime())) continue
      const key = `${d.getFullYear()}-${d.getMonth()}`
      byMonth.set(key, { v: h.interest_profit, label: MONTH_LABELS[d.getMonth()] })
    }
    const buckets = Array.from(byMonth.values()).slice(-12)
    const months = buckets.map((b) => b.v)
    const labels = buckets.map((b) => b.label)
    const latest = months.length ? months[months.length - 1] : (nav?.interest_profit ?? 0)
    const delta = fmtDelta(months.length ? months : [0])
    return {
      value: fmtMoney(latest),
      delta: delta.text,
      deltaPositive: delta.positive,
      months,
      labels,
      ytd: fmtMoney(latest),
    }
  }, [navHistory, nav?.interest_profit])

  // ── Deployed asset composition (real capitalByType) ────────────
  // Headline "Deployed" total mirrors the R&P "Total Deployed" stat (sum of
  // projectMetrics.deployed_value); per-strategy segments still come from the
  // grouped /capital-by-type feed, with percentages relative to that group's
  // sum so they line up with the R&P "Portfolio by Strategy" cards.
  const composition = useMemo(() => {
    const groupTotal = capitalByType.reduce((s, c) => s + c.total_deployed, 0)
    const segments: CompositionSegment[] = capitalByType
      .filter((c) => c.total_deployed > 0)
      .sort((a, b) => b.total_deployed - a.total_deployed)
      .map((c, i) => ({
        label: STRATEGY_LABELS[c.project_type] ?? c.project_type,
        pct: groupTotal > 0 ? Math.round((c.total_deployed / groupTotal) * 100) : 0,
        value: fmtMoneyRP(c.total_deployed),
        color: SEGMENT_COLORS[i % SEGMENT_COLORS.length],
      }))
    return { total: fmtMoneyRP(totalDeployedRaw), totalRaw: totalDeployedRaw, segments }
  }, [capitalByType, totalDeployedRaw])

  // ── Utilization (deployed vs reserve) ──────────────────────────
  // Same inputs R&P uses for "Total Deployed" and "Reserves" so the donut's
  // numbers reconcile with the R&P stats row.
  const utilization = useMemo(() => {
    const deployed = totalDeployedRaw
    const reserve = dryPowder ?? 0
    const basis = deployed + reserve
    const pct = basis > 0 ? Math.round((deployed / basis) * 100) : 0
    return {
      pct,
      deployed: fmtMoneyRP(deployed),
      reserve: fmtMoneyRP(reserve),
      total: fmtMoneyRP(basis),
    }
  }, [totalDeployedRaw, dryPowder])

  // ── Cumulative yield (real cumulative_yield series) ────────────
  // Cumulative return since inception, derived from the resolved share-price
  // ratio. Using historySharePrice (same resolver as the status bar) keeps
  // the series correct even when exchange_rate is implausible/missing on a
  // given snapshot, and matches the design's "cumulative yield since
  // inception" intent.
  const cumulative = useMemo(() => {
    const prices = navHistory.map(historySharePrice)
    const base = prices.length ? prices[0] : 0
    const raw = base > 0 ? prices.map((p) => (p / base - 1) * 100) : prices.map(() => 0)
    // Only register a move once it differs from the last shown value by at
    // least 0.01% (1 bp). Holds flat through sub-bp resolver jitter so the
    // line/value reflect real changes instead of noise magnified by the
    // chart's auto-scaling.
    const series = suppressMicroMoves(raw, 0.01)
    const pctNum = series.length ? series[series.length - 1] : 0
    const startLabel = navHistory.length
      ? new Date(navHistory[0].date).toLocaleDateString('en-US', {
          month: 'short',
          year: 'numeric',
        })
      : '—'
    const lastUpdate = nav?.snapshot_date
      ? new Date(nav.snapshot_date).toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
          year: 'numeric',
        })
      : 'live'
    return {
      pct: Number.isFinite(pctNum) ? `${pctNum >= 0 ? '+' : ''}${pctNum.toFixed(2)}%` : '—',
      nav: priceRaw !== null && priceRaw > 0 ? `$${priceRaw.toFixed(3)}` : '',
      data: series.length ? series : [0, 0],
      startLabel,
      lastUpdate,
    }
  }, [nav, navHistory, priceRaw])

  const toggle = (k: keyof typeof open) => setOpen((s) => ({ ...s, [k]: !s[k] }))

  return (
    <div
      data-screen-label='03 Dashboard'
      className='dash fade-up app-container'
      style={{ padding: '8px 32px 80px', display: 'flex', flexDirection: 'column' }}
    >
      <Hero />
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 8 }}>
        <RangeTabs value={range} onChange={setRange} />
      </div>

      <DashboardSection
        index='01'
        title='Vault Overview'
        accent='var(--d-amber)'
        open={open.overview}
        onToggle={() => toggle('overview')}
        summary={[
          { label: 'TVL', value: tvlValue },
          { label: 'APY', value: apyValue },
          { label: 'sUSD.tel', value: priceValue },
        ]}
      >
        <div className='dash-grid-3'>
          <KpiCard
            label='Total Value Locked'
            value={tvlValue}
            sub={range}
            delta={tvlDelta.text}
            deltaPositive={tvlDelta.positive}
            color='#f3a24a'
            data={tvlData}
            info='Total value locked across the USD.tel vault — capital deployed to fund telecom infrastructure.'
            formatValue={fmtMoney}
            dates={navDates}
            about='Aggregate USD value of all assets held in the sUSD.tel InfraFi vault.'
          />
          <KpiCard
            label='sUSD.tel APY'
            value={apyValue}
            sub={range}
            delta={apyDelta.text}
            deltaPositive={apyDelta.positive}
            color='#ed7c5b'
            data={apyData}
            info='Trailing annualized yield earned by sUSD.tel holders.'
            formatValue={fmtPct}
            dates={navDates}
            about='Trailing 30-day annualized yield on staked sUSD.tel, net of protocol fees.'
          />
          <KpiCard
            label='sUSD.tel NAV'
            value={priceValue}
            sub={range}
            delta={priceDelta.text}
            deltaPositive={priceDelta.positive}
            color='#e84066'
            data={priceData}
            info='Net asset value per sUSD.tel share against USD.tel.'
            formatValue={fmtPrice}
            dates={navDates}
            about='Per-share Net Asset Value of sUSD.tel against USD.tel on-chain. Starts at $1.00 and then accrues yield.'
            refLine={1}
            refLabel='PEG TARGET $1.00'
          />
        </div>
      </DashboardSection>

      <DashboardSection
        index='02'
        title='Yield Engine'
        accent='var(--d-rose)'
        open={open.yield}
        onToggle={() => toggle('yield')}
        summary={[
          { label: 'Revenue', value: revenue.value },
          { label: 'Deployed', value: composition.total },
          { label: 'Utilization', value: `${utilization.pct}%` },
        ]}
      >
        <div className='dash-grid-2'>
          <RevenueCard
            value={revenue.value}
            delta={revenue.delta}
            deltaPositive={revenue.deltaPositive}
            months={revenue.months}
            labels={revenue.labels}
            ytd={revenue.ytd}
            formatValue={fmtMoney}
            about='Vault settled telecom revenue paid by mobile network operators for cellular routing.'
          />
          <UtilizationCard
            pct={utilization.pct}
            deployed={utilization.deployed}
            reserve={utilization.reserve}
            total={utilization.total}
            about='Share of vault capital actively deployed into networks vs sitting in reserve. Higher utilization means more yield, but less buffer.'
          />
          <CompositionCard total={composition.total} segments={composition.segments} />
          <CumulativeYieldCard
            pct={cumulative.pct}
            nav={cumulative.nav}
            data={cumulative.data}
            startLabel={cumulative.startLabel}
            lastUpdate={cumulative.lastUpdate}
            formatValue={fmtPct}
            dates={navDates}
            about='Cumulative return of sUSD.tel since inception, derived from the on-chain exchange rate.'
          />
        </div>
      </DashboardSection>

      <DashboardSection
        index='03'
        title='Liquidity & Composability'
        accent='var(--d-coral)'
        open={open.defi}
        onToggle={() => toggle('defi')}
        summary={[
          { label: 'Liquidity', value: orcaLiquidity.total },
          { label: 'Spread', value: '-15.3 bps' },
          { label: 'Pools', value: String(orcaLiquidity.pools.length) },
        ]}
      >
        <div className='dash-grid-2 is-asym'>
          <MarketDepthCard />
          <NavVsMarketCard navData={priceData} dates={navDates} />
        </div>
      </DashboardSection>
    </div>
  )
}
