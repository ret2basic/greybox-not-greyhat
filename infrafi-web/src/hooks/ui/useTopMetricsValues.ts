'use client'

import { useEffect, useMemo } from 'react'
import { useNav } from '@/store'

const DEFAULT_VALUES = {
  apy: '7.40%',
  susdtel: '$1.073',
  tvl: '$686.9M',
} as const

const formatMoney = (amount: number): string => {
  if (amount >= 1_000_000_000) return `$${(amount / 1_000_000_000).toFixed(1)}B`
  if (amount >= 1_000_000) return `$${(amount / 1_000_000).toFixed(1)}M`
  if (amount >= 1_000) return `$${Math.round(amount / 1_000)}K`
  return `$${amount.toFixed(0)}`
}

export const useTopMetricsValues = () => {
  const { nav, fetchNav } = useNav()

  useEffect(() => {
    fetchNav()
  }, [fetchNav])

  return useMemo(
    () => ({
      apy: nav ? `${(nav.apy * 100).toFixed(2)}%` : DEFAULT_VALUES.apy,
      susdtel: nav ? `$${nav.exchange_rate.toFixed(3)}` : DEFAULT_VALUES.susdtel,
      tvl: nav ? formatMoney(nav.net_asset_value_raw) : DEFAULT_VALUES.tvl,
    }),
    [nav],
  )
}
