import { fetchExponentPositions } from './exponent'
import { fetchKaminoPositions } from './kamino'
import { fetchLoopscalePositions } from './loopscale'
import { fetchOrcaPositions } from './orca'
import type { PartnerPositionsFetcher } from './types'

export type { PartnerPosition, PartnerFetchContext } from './types'

/** Every partner fetcher, run together by `usePartnerPositions`. */
export const PARTNER_FETCHERS: PartnerPositionsFetcher[] = [
  fetchLoopscalePositions, // live (REST)
  fetchExponentPositions, // scaffold — needs PT/YT/LP mints
  fetchOrcaPositions, // scaffold — needs whirlpool addresses
  fetchKaminoPositions, // pending
]
