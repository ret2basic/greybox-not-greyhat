'use client'

import { customRpcUrls, solanaAdapter, projectId, networks } from '@/config'
import { reownThemeVariables } from '@/config/reownTheme'
import { QueryClient } from '@tanstack/react-query'
import { createAppKit } from '@reown/appkit/react'

const queryClient = new QueryClient()

let isAppKitInitialized = false

const getAppOrigin = () => {
  if (typeof window !== 'undefined') {
    return window.location.origin
  }

  if (process.env.NEXT_PUBLIC_APP_URL) {
    return process.env.NEXT_PUBLIC_APP_URL
  }

  if (process.env.VERCEL_URL) {
    return `https://${process.env.VERCEL_URL}`
  }

  return `http://127.0.0.1:${process.env.PORT || 3000}`
}

const ensureAppKitInitialized = () => {
  if (isAppKitInitialized) return
  const appOrigin = getAppOrigin().replace(/\/$/, '')
  const appKitMetadata = {
    name: 'Infrafi',
    description: 'Retail Crypto Investment Platform — DAWN Network',
    url: appOrigin,
    icons: [`${appOrigin}/favicon.ico`],
  }

  createAppKit({
    adapters: [solanaAdapter],
    projectId: projectId!,
    networks,
    defaultNetwork: networks[0],
    customRpcUrls,
    metadata: appKitMetadata,
    termsConditionsUrl: 'https://dawninternet.com/terms',
    privacyPolicyUrl: 'https://dawninternet.com/privacy',
    themeMode: 'dark',
    themeVariables: reownThemeVariables,
    features: {
      analytics: true,
      email: false,
      socials: false,
      emailShowWallets: false,
      legalCheckbox: true,
    },
  })

  isAppKitInitialized = true
}

export const useProviders = () => {
  ensureAppKitInitialized()

  return { queryClient }
}
