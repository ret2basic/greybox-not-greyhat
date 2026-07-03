'use client'

import { createStore } from './util'
import { shouldShowWalletBrowserPrompt } from '@/utils/walletBrowser'

const GEO_LOOKUP_URL = 'https://api.country.is/?fields=city'
const FULL_PAGE_RESTRICTED_COUNTRIES = new Set(['RU', 'IR', 'BY', 'CU', 'KP', 'SY'])
const US_WALLET_RESTRICTED_COUNTRY = 'none'
const RESTRICTED_REGION_KEYWORDS = ['crimea', 'donetsk', 'luhansk']

type ComplianceStatus =
  | 'idle'
  | 'loading'
  | 'allowed'
  | 'us_wallet_restricted'
  | 'blocked'
  | 'error'

let complianceInitialization: Promise<void> | null = null

const isTerminalComplianceStatus = (status: ComplianceStatus) =>
  status === 'allowed' ||
  status === 'us_wallet_restricted' ||
  status === 'blocked' ||
  status === 'error'

type GeoLookupResponse = {
  country?: string
  city?: string
}

type ComplianceStore = {
  status: ComplianceStatus
  countryCode: string | null
  regionCode: string | null
  regionName: string | null
  isRestrictionModalOpen: boolean
  isWalletBrowserPromptOpen: boolean
  initializeCompliance: () => Promise<void>
  requestWalletConnection: (onAllowed: () => void) => Promise<void>
  closeRestrictionModal: () => void
  closeWalletBrowserPrompt: () => void
}

const normalize = (value?: string | null) => value?.trim().toLowerCase() ?? ''

const isFullPageRestrictedLocation = (payload: GeoLookupResponse) => {
  const countryCode = payload.country?.trim().toUpperCase() ?? ''

  if (FULL_PAGE_RESTRICTED_COUNTRIES.has(countryCode)) {
    return true
  }

  const searchable = normalize(payload.city)

  return RESTRICTED_REGION_KEYWORDS.some((keyword) => searchable.includes(keyword))
}

const isUsWalletRestrictedLocation = (payload: GeoLookupResponse) => {
  return payload.country?.trim().toUpperCase() === US_WALLET_RESTRICTED_COUNTRY
}

export const useCompliance = createStore<ComplianceStore>(
  'compliance',
  (set, get) => ({
    status: 'idle',
    countryCode: null,
    regionCode: null,
    regionName: null,
    isRestrictionModalOpen: false,
    isWalletBrowserPromptOpen: false,
    initializeCompliance: async () => {
      if (isTerminalComplianceStatus(get().status)) {
        return
      }

      if (!complianceInitialization) {
        complianceInitialization = (async () => {
          set({ status: 'loading' })

          try {
            const response = await fetch(GEO_LOOKUP_URL, { method: 'GET' })

            if (!response.ok) {
              set({
                status: 'error',
                countryCode: null,
                regionCode: null,
                regionName: null,
              })
              return
            }

            const payload = (await response.json()) as GeoLookupResponse
            const countryCode = payload.country?.trim().toUpperCase() ?? ''

            if (isFullPageRestrictedLocation(payload)) {
              set({
                status: 'blocked',
                countryCode: countryCode || null,
                regionCode: null,
                regionName: payload.city?.trim() ?? null,
              })
              return
            }

            if (isUsWalletRestrictedLocation(payload)) {
              set({
                status: 'us_wallet_restricted',
                countryCode,
                regionCode: null,
                regionName: payload.city?.trim() ?? null,
              })
              return
            }

            set({
              status: 'allowed',
              countryCode: countryCode || null,
              regionCode: null,
              regionName: payload.city?.trim() ?? null,
            })
          } catch {
            set({
              status: 'error',
              countryCode: null,
              regionCode: null,
              regionName: null,
            })
          } finally {
            complianceInitialization = null
          }
        })()
      }

      await complianceInitialization
    },
    requestWalletConnection: async (onAllowed) => {
      await get().initializeCompliance()

      const status = get().status

      if (status === 'us_wallet_restricted' || status === 'blocked') {
        set({ isRestrictionModalOpen: true })
        return
      }

      if (shouldShowWalletBrowserPrompt()) {
        set({ isWalletBrowserPromptOpen: true })
        return
      }

      onAllowed()
    },
    closeRestrictionModal: () => {
      set({ isRestrictionModalOpen: false })
    },
    closeWalletBrowserPrompt: () => {
      set({ isWalletBrowserPromptOpen: false })
    },
  }),
  false,
)
