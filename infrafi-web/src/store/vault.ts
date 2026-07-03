'use client'

import { useApp } from './app'
import { createStore } from './util'

interface VaultStore {
  dryPowder: number | null
  fetchDryPowder: () => Promise<void>
}

export const useVault = createStore<VaultStore>(
  'vault',
  (set) => ({
    dryPowder: null,

    fetchDryPowder: async () => {
      const { http } = useApp.getState()
      const { data } = await http.get<{ balance: number }>('/vault/solana/dry-powder')
      set({ dryPowder: data.balance })
    },
  }),
  false,
)
