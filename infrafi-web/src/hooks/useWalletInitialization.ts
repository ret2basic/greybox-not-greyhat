'use client'

import { useEffect, useState } from 'react'
import { useAppKitAccount, useAppKitState } from '@reown/appkit/react'
import {
  hasInitialWalletCheckFinished,
  markInitialWalletCheckFinished,
} from '@/hooks/walletInitialCheck'

const INITIAL_WALLET_RESTORE_DELAY_MS = 1200

export function useWalletInitialization() {
  const { address, isConnected, status } = useAppKitAccount()
  const { initialized, loading } = useAppKitState()
  const [isInitialWalletRestorePending, setIsInitialWalletRestorePending] = useState(
    !hasInitialWalletCheckFinished(),
  )
  const [isInitialWalletCheckFinished, setIsInitialWalletCheckFinished] = useState(
    hasInitialWalletCheckFinished(),
  )
  const isAppKitResolvingWallet = status === 'connecting' || status === 'reconnecting'

  const finishInitialWalletCheck = () => {
    markInitialWalletCheckFinished()
    setIsInitialWalletCheckFinished(true)
  }

  useEffect(() => {
    if (isConnected && address) {
      setIsInitialWalletRestorePending(false)
      finishInitialWalletCheck()
      return
    }

    if (!isInitialWalletCheckFinished && (isAppKitResolvingWallet || loading || !initialized)) {
      setIsInitialWalletRestorePending(true)
      return
    }

    if (isInitialWalletCheckFinished) {
      setIsInitialWalletRestorePending(false)
      return
    }

    const timer = window.setTimeout(() => {
      setIsInitialWalletRestorePending(false)
      finishInitialWalletCheck()
    }, INITIAL_WALLET_RESTORE_DELAY_MS)

    return () => window.clearTimeout(timer)
  }, [address, initialized, isAppKitResolvingWallet, isConnected, isInitialWalletCheckFinished, loading])

  return (
    !isInitialWalletCheckFinished &&
    (isAppKitResolvingWallet || loading || !initialized || isInitialWalletRestorePending)
  )
}
