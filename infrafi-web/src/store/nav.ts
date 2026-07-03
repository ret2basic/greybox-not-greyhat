'use client'

import { useApp } from './app'
import { createStore } from './util'

export interface NavResult {
  vault_id: string
  vault_name: string
  snapshot_date: string
  net_asset_value: number
  net_asset_value_raw: number
  exchange_rate: number
  apy: number
  utilization_rate: number
  cumulative_yield: number
  shares_outstanding: number
  assets_under_management: number
  dry_powder: number
  capital_basis: number
  outstanding_principal: number
  interest_profit: number
  mgmt_fee_accrued: number
  interest_accrued: number
  ripcord: boolean
}

export interface NavHistoryItem {
  date: string
  net_asset_value: number
  outstanding_principal: number
  dry_powder: number
  interest_profit: number
  capital_basis: number
  shares_outstanding: number
  exchange_rate: number
  utilization_rate: number
  cumulative_yield: number
  apy: number
}

// sUSD.tel share price (USD per share). Prefer the API exchange_rate when it
// looks like a real per-share NAV; otherwise recompute from NAV ÷ shares, then
// NAV ÷ capital_basis. History often has exchange_rate = 0 when the indexer's
// shares series is missing for past dates — without this fallback the chart
// flatlines at $0 while the live snapshot shows a plausible ~$1.xx price.
const MAX_PLAUSIBLE_SHARE_PRICE = 10

function resolveSharePrice(opts: {
  exchange_rate: number
  nav: number
  shares_outstanding: number
  capital_basis: number
}): number {
  const { exchange_rate, nav, shares_outstanding, capital_basis } = opts
  const fromShares = shares_outstanding > 0 ? nav / shares_outstanding : 0
  const fromCapital = capital_basis > 0 ? nav / capital_basis : 0

  if (exchange_rate > 0 && exchange_rate <= MAX_PLAUSIBLE_SHARE_PRICE) {
    return exchange_rate
  }
  if (fromShares > 0 && fromShares <= MAX_PLAUSIBLE_SHARE_PRICE) return fromShares
  if (fromCapital > 0) return fromCapital
  return exchange_rate > 0 ? exchange_rate : 0
}

export function historySharePrice(h: NavHistoryItem): number {
  return resolveSharePrice({
    exchange_rate: h.exchange_rate,
    nav: h.net_asset_value,
    shares_outstanding: h.shares_outstanding,
    capital_basis: h.capital_basis,
  })
}

export function liveSharePrice(nav: NavResult): number {
  return resolveSharePrice({
    exchange_rate: nav.exchange_rate,
    nav: nav.net_asset_value_raw,
    shares_outstanding: nav.shares_outstanding,
    capital_basis: nav.capital_basis,
  })
}

interface NavStore {
  nav: NavResult | null
  navHistory: NavHistoryItem[]
  // Separate window used by the stat-chip chart expansion so changing its
  // range never disturbs the header sparklines (which stay on navHistory).
  navRangeHistory: NavHistoryItem[]
  fetchNav: () => Promise<void>
  fetchNavHistory: (days?: number) => Promise<void>
  fetchNavRangeHistory: (days: number) => Promise<void>
}

interface NavApiResult {
  vault_id: string
  vault_name: string
  snapshot_date: string
  net_asset_value: string
  net_asset_value_raw: string
  exchange_rate: string
  apy: string
  utilization_rate: string
  cumulative_yield: string
  shares_outstanding: string
  assets_under_management: string
  dry_powder: string
  capital_basis: string
  outstanding_principal: string
  interest_profit: string
  mgmt_fee_accrued: string
  interest_accrued: string
  ripcord: boolean
}

const parseApiNumber = (value: string, field: keyof Omit<NavApiResult, 'vault_id' | 'vault_name' | 'snapshot_date' | 'ripcord'>): number => {
  const parsed = Number(value)
  if (Number.isNaN(parsed)) {
    throw new Error(`Invalid numeric value for nav field: ${field}`)
  }
  return parsed
}

const mapNavResult = (api: NavApiResult): NavResult => ({
  vault_id: api.vault_id,
  vault_name: api.vault_name,
  snapshot_date: api.snapshot_date,
  net_asset_value: parseApiNumber(api.net_asset_value, 'net_asset_value'),
  net_asset_value_raw: parseApiNumber(api.net_asset_value_raw, 'net_asset_value_raw'),
  exchange_rate: parseApiNumber(api.exchange_rate, 'exchange_rate'),
  apy: parseApiNumber(api.apy, 'apy'),
  utilization_rate: parseApiNumber(api.utilization_rate, 'utilization_rate'),
  cumulative_yield: parseApiNumber(api.cumulative_yield, 'cumulative_yield'),
  shares_outstanding: parseApiNumber(api.shares_outstanding, 'shares_outstanding'),
  assets_under_management: parseApiNumber(api.assets_under_management, 'assets_under_management'),
  dry_powder: parseApiNumber(api.dry_powder, 'dry_powder'),
  capital_basis: parseApiNumber(api.capital_basis, 'capital_basis'),
  outstanding_principal: parseApiNumber(api.outstanding_principal, 'outstanding_principal'),
  interest_profit: parseApiNumber(api.interest_profit, 'interest_profit'),
  mgmt_fee_accrued: parseApiNumber(api.mgmt_fee_accrued, 'mgmt_fee_accrued'),
  interest_accrued: parseApiNumber(api.interest_accrued, 'interest_accrued'),
  ripcord: api.ripcord,
})

export const useNav = createStore<NavStore>(
  'nav',
  (set) => ({
    nav: null,
    navHistory: [],
    navRangeHistory: [],

    fetchNav: async () => {
      const { http } = useApp.getState()
      try {
        const { data } = await http.get<NavApiResult>('/vault/solana/nav')
        set({ nav: mapNavResult(data) })
      } catch (error) {
        void error
        set({ nav: null })
      }
    },

    fetchNavHistory: async (days = 30) => {
      const { http } = useApp.getState()
      try {
        const { data } = await http.get<{ items: NavHistoryItem[] }>('/vault/solana/nav/history', {
          params: { days },
        })
        set({ navHistory: data.items })
      } catch (error) {
        void error
        set({ navHistory: [] })
      }
    },

    fetchNavRangeHistory: async (days: number) => {
      const { http } = useApp.getState()
      try {
        const { data } = await http.get<{ items: NavHistoryItem[] }>('/vault/solana/nav/history', {
          params: { days },
        })
        set({ navRangeHistory: data.items })
      } catch (error) {
        void error
        set({ navRangeHistory: [] })
      }
    },
  }),
  false,
)
