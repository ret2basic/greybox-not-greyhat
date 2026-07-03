'use client'

import { useQuery } from '@tanstack/react-query'
import { fetchOrcaPoolStats, type OrcaPoolRaw } from '@/lib/partners/orca'

export type OrcaPoolStatsMap = Record<string, OrcaPoolRaw>

/**
 * Reads pool-derived stats (TVL + trading-fee APR) for the Orca pools, keyed by
 * strategy id (matching `boost/data.ts` row ids). Needs no wallet, so it runs
 * for everyone. The sUSD.tel base yield is layered on by the section via
 * `useEffectiveBaseApy`; rows without live data fall back to static figures.
 */
export const useOrcaPoolStats = (): OrcaPoolStatsMap => {
  const { data } = useQuery({
    queryKey: ['boost', 'orca-pool-stats'],
    queryFn: fetchOrcaPoolStats,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  })

  return data ?? {}
}
