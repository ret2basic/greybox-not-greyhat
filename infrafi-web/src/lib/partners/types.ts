import type { Connection } from '@solana/web3.js'

/**
 * A connected wallet's position in a single strategy, normalized across every
 * partner. `strategyId` must match the `id` of the corresponding row in
 * `@/components/boost/data.ts` so the UI can merge the two.
 */
export type PartnerPosition = {
  strategyId: string
  balanceLabel: string // e.g. "1,240 sUSD.tel"
  usdLabel: string // e.g. "$1,331"
  apyLabel?: string // effective/earned APY for this wallet
}

/**
 * Context handed to every partner fetcher. `connection` is the AppKit Solana
 * connection (may be null before the wallet provider initializes).
 */
export type PartnerFetchContext = {
  walletAddress: string
  connection: Connection | null
}

export type PartnerPositionsFetcher = (
  ctx: PartnerFetchContext,
) => Promise<PartnerPosition[]>

/** USD formatting helper shared by partner fetchers. */
export function formatUsd(value: number): string {
  return `$${value.toLocaleString('en-US', { maximumFractionDigits: 2 })}`
}

/** Token-amount formatting helper, e.g. `formatAmount(1240, 'sUSD.tel')`. */
export function formatAmount(value: number, symbol: string): string {
  return `${value.toLocaleString('en-US', { maximumFractionDigits: 2 })} ${symbol}`
}
