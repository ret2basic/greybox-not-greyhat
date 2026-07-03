'use client'

import { useAppKitAccount } from '@reown/appkit/react'
import { useAppKitConnection } from '@reown/appkit-adapter-solana/react'
import { useAppKitState } from '@reown/appkit/react'
import { useTokenBalances } from '@/hooks/useTokenBalances'
import { useWalletInitialization } from '@/hooks/useWalletInitialization'
import { combineUsdtelBalances, DEV_USDTEL_MINT, USDTEL_MINT } from '@/lib/solana'

export type PortfolioBalances = {
  devUsdtelBalance: string
  isConnected: boolean
  isLoading: boolean
  mainnetUsdtelBalance: string
  susdtelBalance: string
  usdcBalance: string
  usdtelBalance: string
}

export const usePortfolioBalances = (): PortfolioBalances => {
  const { address, isConnected, status } = useAppKitAccount()
  const { initialized, loading } = useAppKitState()
  const { connection } = useAppKitConnection()
  const isWalletInitializing = useWalletInitialization()
  const isResolvingWalletConnection =
    !isConnected && (status === 'connecting' || status === 'reconnecting' || loading || !initialized)
  const {
    usdtelBalance: devUsdtelBalance,
    susdtelBalance,
    isLoading: isDevBalanceLoading,
  } = useTokenBalances(
    address,
    connection ?? undefined,
    DEV_USDTEL_MINT,
    { includeUsdc: false },
  )
  const {
    usdtelBalance: mainnetUsdtelBalance,
    usdcBalance,
    isLoading: isMainnetBalanceLoading,
  } = useTokenBalances(
    address,
    connection ?? undefined,
    USDTEL_MINT,
    { includeUsdc: true, includeSusdtel: false },
  )

  return {
    devUsdtelBalance,
    isConnected,
    isLoading:
      isWalletInitializing ||
      isResolvingWalletConnection ||
      (isConnected && (isDevBalanceLoading || isMainnetBalanceLoading)),
    mainnetUsdtelBalance,
    susdtelBalance,
    usdcBalance,
    usdtelBalance: combineUsdtelBalances(devUsdtelBalance, mainnetUsdtelBalance),
  }
}
