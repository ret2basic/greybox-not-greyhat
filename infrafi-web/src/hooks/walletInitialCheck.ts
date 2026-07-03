'use client'

let hasInitialWalletCheckFinishedGlobally = false

export const hasInitialWalletCheckFinished = () => hasInitialWalletCheckFinishedGlobally

export const markInitialWalletCheckFinished = () => {
  hasInitialWalletCheckFinishedGlobally = true
}
