'use client'

import { useQuery } from '@tanstack/react-query'
import { useAppKitAccount } from '@reown/appkit/react'
import { useAppKitConnection } from '@reown/appkit-adapter-solana/react'
import { PARTNER_FETCHERS, type PartnerPosition } from '@/lib/partners'
import type { UserPosition } from '@/components/boost/types'

export type PartnerPositionsMap = Record<string, UserPosition>

function toUserPosition({ balanceLabel, usdLabel, apyLabel }: PartnerPosition): UserPosition {
  return { balanceLabel, usdLabel, apyLabel }
}

/**
 * Reads the connected wallet's live positions across every Boost partner and
 * returns them keyed by strategy id (matching `boost/data.ts` row ids).
 * Disconnected wallets get an empty map, so rows fall back to their static
 * marketing data.
 */
export const usePartnerPositions = (): PartnerPositionsMap => {
  const { address, isConnected } = useAppKitAccount()
  const { connection } = useAppKitConnection()
  const rpcEndpoint = connection?.rpcEndpoint ?? 'no-rpc'

  const { data } = useQuery({
    queryKey: ['boost', 'partner-positions', address, rpcEndpoint],
    queryFn: async () => {
      const ctx = { walletAddress: address!, connection: connection ?? null }
      const results = await Promise.allSettled(PARTNER_FETCHERS.map((fetch) => fetch(ctx)))

      const map: PartnerPositionsMap = {}
      for (const result of results) {
        if (result.status !== 'fulfilled') continue
        for (const position of result.value) {
          map[position.strategyId] = toUserPosition(position)
        }
      }
      return map
    },
    enabled: !!isConnected && !!address,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  })

  return data ?? {}
}
