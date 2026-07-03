'use client'

import { useEffect } from 'react'
import { useAppKitAccount } from '@reown/appkit/react'
import { usePoints } from '@/store'

export const usePortfolioPoints = () => {
  const { address, isConnected } = useAppKitAccount()
  const fetchPortfolioPoints = usePoints((state) => state.fetchPortfolioPoints)
  const clear = usePoints((state) => state.clear)
  const points = usePoints()

  useEffect(() => {
    if (!isConnected || !address) {
      clear()
      return
    }

    void fetchPortfolioPoints(address)
  }, [address, clear, fetchPortfolioPoints, isConnected])

  return points
}
