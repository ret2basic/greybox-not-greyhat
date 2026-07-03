import type { StaticImageData } from 'next/image'

export type BoostNetwork = 'Base' | 'Solana'

export enum BoostTab {
  All = 'all',
  Looping = 'looping',
  YieldTrading = 'yield-trading',
  Lending = 'lending',
  Liquidity = 'liquidity',
}

export type StrategyStatus = 'live' | 'pending'

/**
 * A connected wallet's live position in a single strategy, normalized across
 * partners by `usePartnerPositions`. All values are pre-formatted for display.
 */
export type UserPosition = {
  balanceLabel: string // e.g. "1,240 sUSD.tel"
  usdLabel: string // e.g. "$1,331"
  apyLabel?: string // effective/earned APY for this wallet, e.g. "11.2%"
}

export type StrategyMetric = {
  label: string
  value: string
  hasInfo?: boolean
  tooltip?: string
  tooltipWidthClassName?: string
  widthClassName?: string
}

export type StrategyTabConfig = {
  id: BoostTab
  label: string
  mobileLabel?: string
}

export type SectionStat = {
  label: string
  value: string
}

export type SectionHeaderProps = {
  icon: StaticImageData
  title: string
  description: string
  stats: SectionStat[]
  marginBottomClass?: string
}

export type ColumnHeader = {
  label: string
  widthClass: string
  alignClass?: string
}

export type StrategySectionProps = {
  hasBottomSpacing?: boolean
  hasTopSpacing?: boolean
}

export type RowVisualProps = {
  protocol: string
  title: string
}

/**
 * Stable identifier used to merge a live `UserPosition` onto a strategy row.
 * Must match the ids produced by the partner fetchers in `@/lib/partners`.
 */
export type StrategyId = string

type BaseRow = {
  /** Stable id keyed by `usePartnerPositions` to attach live wallet data. */
  id: StrategyId
  /** `pending` rows render disabled ("Soon") and are never fetched live. */
  status: StrategyStatus
  /** Partner deep-link the Enter button opens to deposit into the strategy. */
  depositUrl?: string
}

export type LoopingRow = BaseRow & {
  pool: string
  protocol: string
  network: BoostNetwork
  leverage: string
  tvl: string
  apy: string
  apyBreakdown: string
}

export type YieldTradingRow = BaseRow & {
  asset: string
  protocol: string
  network: BoostNetwork
  maturity: string
  tvl: string
  apy: string
  type: 'Fixed' | 'Variable'
}

export type LendingRow = BaseRow & {
  asset: string
  protocol: string
  network: BoostNetwork
  marketType: string
  lendRate: string
  tvl: string
  netApy: string
  breakdown: string
}

export type LiquidityRow = BaseRow & {
  pair: string
  protocol: string
  network: BoostNetwork
  poolType: string
  feeApr: string
  tvl: string
  netApy: string
  breakdown: string
}
