// All Section-03 (Liquidity & Composability) data plus reserve-mix
// breakdown lives here. None of this is in the api yet — the real source
// would be DEX subgraphs (depth, NAV/market spread) plus a curated config
// for integrations and reserve composition. Marked clearly as MOCK_*.

import type { ReactNode } from 'react'

// Seeded PRNG for deterministic mocks — same shape as the design's rngLq.
function rngLq(seed: number) {
  let s = seed >>> 0
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0
    return s / 4294967296
  }
}

export type DepthVenue = {
  key: 'curve' | 'raydium' | 'uniV3' | 'orca'
  label: string
  color: string
  base: number
  vol: number
  drift: number
}

export type DepthDay = {
  i: number
  byVenue: Record<DepthVenue['key'], number> & { total: number }
}

const DEPTH_VENUES: DepthVenue[] = [
  { key: 'curve', label: 'Curve · sUSD.tel/USD.tel', color: '#F3A24A', base: 1.8, vol: 0.06, drift: 0.012 },
  { key: 'raydium', label: 'Raydium · sUSD.tel/USD.tel', color: '#EA5270', base: 1.1, vol: 0.07, drift: 0.018 },
  { key: 'uniV3', label: 'Uni v3 · sUSD.tel/USD.tel', color: '#9B7BFF', base: 0.7, vol: 0.05, drift: 0.008 },
  { key: 'orca', label: 'Orca · sUSD.tel/USD.tel', color: '#7ED9A8', base: 0.4, vol: 0.06, drift: 0.014 },
]

export function depthSeries(n = 30): { venues: DepthVenue[]; days: DepthDay[] } {
  const days: DepthDay[] = []
  const r = rngLq(41)
  const cur: Record<string, number> = {}
  DEPTH_VENUES.forEach((v) => {
    cur[v.key] = v.base
  })
  // Scale per-step drift so totals stay sane across longer ranges.
  const driftScale = 30 / n
  for (let i = 0; i < n; i++) {
    const byVenue = {} as DepthDay['byVenue']
    let total = 0
    DEPTH_VENUES.forEach((v) => {
      const noise = (r() - 0.5) * v.vol
      cur[v.key] = Math.max(0.05, cur[v.key] * (1 + noise + (v.drift / 30) * driftScale))
      byVenue[v.key] = cur[v.key]
      total += cur[v.key]
    })
    byVenue.total = total
    days.push({ i, byVenue })
  }
  return { venues: DEPTH_VENUES, days }
}

export type NavPoint = { i: number; nav: number; mkt: number }

export function navSeries(n = 30): NavPoint[] {
  const r = rngLq(91)
  const out: NavPoint[] = []
  let nav = 1.0
  // Daily NAV drift gives ~8% APY when applied 365×.
  const drift = 0.00021
  for (let i = 0; i < n; i++) {
    nav = nav * (1 + drift + (r() - 0.5) * 0.0006)
    const spread = (r() - 0.45) * 0.006
    const mkt = nav * (1 + spread)
    out.push({ i, nav, mkt })
  }
  return out
}

// ---------------- Integrations ----------------

export type IntegrationStatus = 'live' | 'soon'

export type Integration = {
  venue: string
  chain: 'Ethereum' | 'Base'
  chainColor: string
  role: string
  tvl: number
  rateLabel: string
  rate: number | null
  status: IntegrationStatus
  actions: Array<{ label: string; url: string }>
}

export const MOCK_INTEGRATIONS: Integration[] = [
  {
    venue: 'Curve',
    chain: 'Ethereum',
    chainColor: '#627EEA',
    role: 'LP · sUSD.tel/USDC',
    tvl: 1.82,
    rateLabel: 'APY',
    rate: 9.4,
    status: 'live',
    actions: [
      { label: 'Provide liquidity', url: 'https://curve.fi' },
      { label: 'Stake LP for CRV', url: 'https://curve.fi' },
      { label: 'View pool stats', url: 'https://curve.fi' },
    ],
  },
  {
    venue: 'Balancer',
    chain: 'Ethereum',
    chainColor: '#627EEA',
    role: 'LP · BoostedPool',
    tvl: 1.14,
    rateLabel: 'APY',
    rate: 8.7,
    status: 'live',
    actions: [
      { label: 'Provide liquidity', url: 'https://balancer.fi' },
      { label: 'Stake BPT for BAL', url: 'https://balancer.fi' },
    ],
  },
  {
    venue: 'Uniswap v3',
    chain: 'Base',
    chainColor: '#0052FF',
    role: 'LP · 0.05% pool',
    tvl: 0.71,
    rateLabel: 'APY',
    rate: 11.2,
    status: 'live',
    actions: [
      { label: 'Add liquidity (concentrated)', url: 'https://app.uniswap.org' },
      { label: 'Swap sUSD.tel ↔ USD.tel', url: 'https://app.uniswap.org' },
    ],
  },
  {
    venue: 'Fluid',
    chain: 'Ethereum',
    chainColor: '#627EEA',
    role: 'Lending · collateral',
    tvl: 0.62,
    rateLabel: 'Borrow',
    rate: 5.8,
    status: 'live',
    actions: [
      { label: 'Deposit sUSD.tel as collateral', url: 'https://fluid.instadapp.io' },
      { label: 'Borrow against sUSD.tel', url: 'https://fluid.instadapp.io' },
    ],
  },
  {
    venue: 'Morpho',
    chain: 'Base',
    chainColor: '#0052FF',
    role: 'Lending market',
    tvl: 0.41,
    rateLabel: 'APY',
    rate: 7.9,
    status: 'live',
    actions: [
      { label: 'Supply sUSD.tel', url: 'https://app.morpho.org' },
      { label: 'Borrow stablecoins', url: 'https://app.morpho.org' },
    ],
  },
  {
    venue: 'Pendle',
    chain: 'Ethereum',
    chainColor: '#627EEA',
    role: 'Yield · PT/YT split',
    tvl: 0.28,
    rateLabel: 'Fixed APY',
    rate: 8.3,
    status: 'live',
    actions: [
      { label: 'Buy PT (fixed yield)', url: 'https://app.pendle.finance' },
      { label: 'Buy YT (leveraged yield)', url: 'https://app.pendle.finance' },
      { label: 'Provide LP', url: 'https://app.pendle.finance' },
    ],
  },
  {
    venue: 'Aave v3',
    chain: 'Ethereum',
    chainColor: '#627EEA',
    role: 'Lending · collateral',
    tvl: 0,
    rateLabel: 'Listing',
    rate: null,
    status: 'soon',
    actions: [{ label: 'View governance proposal', url: 'https://app.aave.com' }],
  },
  {
    venue: 'Spectra',
    chain: 'Base',
    chainColor: '#0052FF',
    role: 'Yield · PT/YT split',
    tvl: 0,
    rateLabel: 'Listing',
    rate: null,
    status: 'soon',
    actions: [{ label: 'Pre-register interest', url: 'https://app.spectra.finance' }],
  },
]

// Inline chain glyphs as JSX so the IntegrationRow can render them.
// Using ReactNode here means consumers don't import SVGs separately.
import { createElement } from 'react'

export const CHAIN_GLYPH: Record<Integration['chain'], ReactNode> = {
  Ethereum: createElement(
    'svg',
    { width: '11', height: '11', viewBox: '0 0 256 417', fill: 'currentColor' },
    createElement('path', {
      d: 'M127.961 0L125.166 9.5v275.668l2.795 2.79L255.922 212.32z',
      opacity: '0.6',
    }),
    createElement('path', {
      d: 'M127.962 0L0 212.32l127.962 75.639V154.158z',
    }),
    createElement('path', {
      d: 'M127.961 312.187l-1.575 1.92v98.199l1.575 4.6L256 236.587z',
      opacity: '0.6',
    }),
    createElement('path', {
      d: 'M127.962 416.905v-104.72L0 236.585z',
    }),
    createElement('path', {
      d: 'M127.961 287.958l127.96-75.637-127.96-58.162z',
      opacity: '0.2',
    }),
    createElement('path', {
      d: 'M0 212.32l127.96 75.638V154.159z',
      opacity: '0.6',
    }),
  ),
  Base: createElement(
    'svg',
    { width: '11', height: '11', viewBox: '0 0 111 111', fill: 'currentColor' },
    createElement('path', {
      d: 'M54.921 110.034C85.359 110.034 110.034 85.402 110.034 55.017S85.359 0 54.921 0C26.043 0 2.353 22.222 0 50.498h72.857v9.038H0c2.353 28.276 26.043 50.498 54.921 50.498z',
    }),
  ),
}

// ---------------- Reserve mix breakdown (used by Utilization card) ----------------

export type ReserveSlice = {
  label: string
  v: number
  color: string
  desc: string
}

export const MOCK_RESERVE_MIX: ReserveSlice[] = [
  {
    label: 'T-bill backed',
    v: 60,
    color: '#7ED9A8',
    desc: 'Short-duration U.S. Treasuries',
  },
  {
    label: 'USD.tel idle',
    v: 28,
    color: '#F3A24A',
    desc: 'Held in custody for redemptions',
  },
  {
    label: 'Insurance fund',
    v: 6,
    color: '#9B7BFF',
    desc: 'Slashing & coverage reserves',
  },
]

export const MOCK_RESERVE_DETAIL: Array<ReserveSlice & { vDollarsK: number }> = [
  {
    label: 'T-bill backed',
    v: 60,
    color: '#7ED9A8',
    desc: '$56.4K · short-duration U.S. Treasuries earning 5.2% yield. Custodied by Anchorage Trust.',
    vDollarsK: 56.4,
  },
  {
    label: 'USD.tel idle',
    v: 28,
    color: '#F3A24A',
    desc: '$26.3K · held in protocol multisig for redemptions. Refreshed daily.',
    vDollarsK: 26.3,
  },
  {
    label: 'Insurance fund',
    v: 6,
    color: '#9B7BFF',
    desc: '$5.6K · slashing coverage, paid into by 1% of all settlement fees.',
    vDollarsK: 5.6,
  },
  {
    label: 'Operational buffer',
    v: 6,
    color: '#C73E7C',
    desc: '$5.6K · gas, audits, oracle subscriptions. Three months of runway.',
    vDollarsK: 5.6,
  },
]

// ---------------- City revenue (Section 02 -> Network revenue detail panel) ----------------

export type CityRow = {
  name: string
  region: string
  rev: number
  nodes: number
  growth: number
}

export const MOCK_CITIES: CityRow[] = [
  { name: 'NYC-3a', region: 'North America', rev: 32, nodes: 412, growth: 12.4 },
  { name: 'LAX-2b', region: 'North America', rev: 24, nodes: 318, growth: 8.1 },
  { name: 'MEX-5c', region: 'Latin America', rev: 19, nodes: 261, growth: 22.7 },
  { name: 'GRU-2a', region: 'Latin America', rev: 16, nodes: 234, growth: 14.2 },
  { name: 'CHI-1a', region: 'North America', rev: 14, nodes: 198, growth: 5.8 },
  { name: 'BOM-2a', region: 'Asia Pacific', rev: 12, nodes: 184, growth: 31.2 },
  { name: 'LHR-3b', region: 'Europe', rev: 8, nodes: 142, growth: -2.1 },
  { name: 'MNL-1a', region: 'Asia Pacific', rev: 5, nodes: 96, growth: 18.5 },
]
