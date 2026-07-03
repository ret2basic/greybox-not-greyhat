'use client'

import { createStore } from './util'

interface UserStore {
  walletAddress: string | null
  isConnected: boolean

  setWalletAddress: (address: string | null) => void
  setConnected: (connected: boolean) => void
  disconnect: () => void
}

export const useUser = createStore<UserStore>(
  'user',
  (set) => {
    return {
      walletAddress: null,
      isConnected: false,

      setWalletAddress: (address) => {
        set({ walletAddress: address })
      },

      setConnected: (connected) => {
        set({ isConnected: connected })
      },

      disconnect: () => {
        set({ walletAddress: null, isConnected: false })
      },
    }
  },
  false,
)
