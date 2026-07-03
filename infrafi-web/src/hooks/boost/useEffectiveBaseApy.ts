'use client'

import { useEffect } from 'react'
import { useNav } from '@/store'

/**
 * Live effective sUSD.tel base APY (percent) shared by every Boost strategy:
 * the headline `nav.apy` discounted by `utilization_rate`, since only deployed
 * capital earns it. Matches the TopNav chip / dashboard KPI. Returns `null`
 * while the nav feed is loading or unavailable, so consumers show "—" instead
 * of a fabricated percentage.
 */
export const useEffectiveBaseApy = (): number | null => {
  const { nav, fetchNav } = useNav()

  useEffect(() => {
    fetchNav()
  }, [fetchNav])

  return nav ? nav.apy * nav.utilization_rate * 100 : null
}
