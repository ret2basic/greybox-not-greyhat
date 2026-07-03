import type { PartnerPosition } from './types'

// Exponent PT / YT / LP are SPL tokens, so a wallet's *holdings* are readable
// today with the same ATA-balance approach as `@/hooks/useTokenBalances`.
// Going live requires the sUSD.tel market's token mints below, plus a price
// source to value PT (trades at a discount) and YT (decays to maturity).
//
// Program ID (mainnet): ExponentnaRg3CQbW6dqQNZKXp7gtZ9DGMp1cwC4HAS7
// Docs: https://docs.exponent.finance
//
// TODO(partner-config): set these once provided by the Exponent team.
export const EXPONENT_MINTS = {
  pt: undefined as string | undefined, // PT-sUSD.tel mint
  yt: undefined as string | undefined, // YT-sUSD.tel mint
  lp: undefined as string | undefined, // sUSD.tel LP vault mint
}

export const fetchExponentPositions = async (): Promise<PartnerPosition[]> => {
  // Once EXPONENT_MINTS are set, read each ATA balance (see useTokenBalances)
  // and map to strategy ids: 'exponent-pt-susdtel', 'exponent-yt-susdtel',
  // 'exponent-lp-susdtel'. Valuation comes from the Exponent program's market
  // price accounts (or a DefiLlama yields fallback).
  return []
}
