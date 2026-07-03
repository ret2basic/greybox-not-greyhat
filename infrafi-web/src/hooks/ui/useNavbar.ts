'use client'

import { useEffect, useLayoutEffect, useState } from 'react'
import { usePathname } from 'next/navigation'
import { useAppKit, useAppKitAccount, useAppKitState, useWalletInfo } from '@reown/appkit/react'
import {
  hasInitialWalletCheckFinished,
  markInitialWalletCheckFinished,
} from '@/hooks/walletInitialCheck'
import { useCompliance } from '@/store'

const navigationItems = [
  { label: 'Buy & Stake', href: '/buy-stake', isExternal: false },
  { label: 'Reserves & Projects', href: '/reserves-projects', isExternal: false },
  { label: 'Portfolio', href: '/portfolio', isExternal: false },
  { label: 'Dashboard', href: '/dashboard', isExternal: false },
  { label: 'Boost', href: '/boost', isExternal: false },
  { label: 'Docs', href: 'https://docs.dawninternet.com/', isExternal: true },
] as const

const INITIAL_WALLET_RESTORE_DELAY_MS = 1200
const CACHED_WALLET_ADDRESS_KEY = 'dawn:last-connected-wallet-address'

const readCachedWalletAddress = () => {
  if (typeof window === 'undefined') {
    return null
  }

  return window.sessionStorage.getItem(CACHED_WALLET_ADDRESS_KEY)
}

export const useNavbar = () => {
  const pathname = usePathname()
  const { open } = useAppKit()
  const { address, isConnected, status } = useAppKitAccount()
  const { initialized: isAppKitInitialized, loading: isAppKitLoading } = useAppKitState()
  const { walletInfo } = useWalletInfo()
  const requestWalletConnection = useCompliance((state) => state.requestWalletConnection)
  const [cachedWalletAddress, setCachedWalletAddress] = useState<string | null>(readCachedWalletAddress)
  const [isInitialWalletRestorePending, setIsInitialWalletRestorePending] = useState(Boolean(cachedWalletAddress))
  const [isInitialWalletCheckFinished, setIsInitialWalletCheckFinished] = useState(
    hasInitialWalletCheckFinished,
  )
  const isAppKitResolvingWallet = status === 'connecting' || status === 'reconnecting'

  useLayoutEffect(() => {
    const storedWalletAddress = readCachedWalletAddress()
    if (!storedWalletAddress) {
      return
    }

    setCachedWalletAddress(storedWalletAddress)
    setIsInitialWalletRestorePending(true)
  }, [])

  useEffect(() => {
    if (isConnected && address) {
      setIsInitialWalletRestorePending(false)
      markInitialWalletCheckFinished()
      setIsInitialWalletCheckFinished(true)
      return
    }

    if (!isInitialWalletCheckFinished && isAppKitResolvingWallet) {
      setIsInitialWalletRestorePending(true)
      return
    }

    if (isInitialWalletCheckFinished) {
      setIsInitialWalletRestorePending(false)
      return
    }

    const timer = window.setTimeout(() => {
      setIsInitialWalletRestorePending(false)
      markInitialWalletCheckFinished()
      setIsInitialWalletCheckFinished(true)
    }, INITIAL_WALLET_RESTORE_DELAY_MS)

    return () => window.clearTimeout(timer)
  }, [address, isAppKitResolvingWallet, isConnected, isInitialWalletCheckFinished])

  useEffect(() => {
    if (!isConnected || !address) {
      return
    }

    setCachedWalletAddress(address)
    window.sessionStorage.setItem(CACHED_WALLET_ADDRESS_KEY, address)
  }, [address, isConnected])

  useEffect(() => {
    if (
      status !== 'disconnected' ||
      isInitialWalletRestorePending ||
      isAppKitLoading ||
      !isAppKitInitialized
    ) {
      return
    }

    setCachedWalletAddress(null)
    window.sessionStorage.removeItem(CACHED_WALLET_ADDRESS_KEY)
  }, [isAppKitInitialized, isAppKitLoading, isInitialWalletRestorePending, status])

  const fallbackWalletAddress = isConnected && address ? address : cachedWalletAddress
  const isWalletResolving =
    !isInitialWalletCheckFinished &&
    (isAppKitResolvingWallet ||
      isAppKitLoading ||
      !isAppKitInitialized ||
      Boolean(isInitialWalletRestorePending && cachedWalletAddress))

  return {
    connectedWalletIcon: walletInfo?.icon,
    connectedWalletName: walletInfo?.name ?? 'Connected wallet',
    connectedWalletShortLabel: fallbackWalletAddress
      ? `${fallbackWalletAddress.slice(0, 2)}...${fallbackWalletAddress.slice(-2)}`
      : '',
    handleConnectWalletClick: () => {
      void requestWalletConnection(() => open())
    },
    handleOpenAccountClick: () => open({ view: 'Account' }),
    isActive: (href: string) => pathname === href,
    isWalletConnected: Boolean(isConnected && address),
    isWalletResolving,
    navigationItems,
    walletLabel: fallbackWalletAddress
      ? `${fallbackWalletAddress.slice(0, 6)}...${fallbackWalletAddress.slice(-4)}`
      : 'Connect Wallet',
  }
}
