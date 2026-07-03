import type { DeployedRow, PortfolioAsset, WalletRow } from '@/components/portfolio/types'
import type { OverviewMetricItem } from '@/components/ui/OverviewMetricsRow'
import { SUSDTEL_TOOLTIP_TEXT, TVL_TOOLTIP_TEXT } from '@/constants/metric-tooltips'

const formatCompactUsd = (amount: number): string => {
  if (!Number.isFinite(amount) || amount <= 0) return '$0'
  if (amount >= 1_000_000_000) return `$${(amount / 1_000_000_000).toFixed(1)}B`
  if (amount >= 1_000_000) return `$${(amount / 1_000_000).toFixed(1)}M`
  if (amount >= 1_000) return `$${(amount / 1_000).toFixed(1)}K`
  return `$${amount.toFixed(0)}`
}

export const getPortfolioOverviewMetrics = (params: {
  tvl?: number | null
  apy?: number | null
  exchangeRate?: number | null
}): readonly OverviewMetricItem[] => [
  {
    label: 'TVL',
    value: formatCompactUsd(params.tvl ?? 0),
    hasInfo: true,
    tooltip: TVL_TOOLTIP_TEXT,
    tooltipWidthClassName: 'w-[198px]',
    widthClassName: 'w-[60px]',
  },
  {
    label: 'APY',
    value: `${(((params.apy ?? 0) as number) * 100).toFixed(2)}%`,
    widthClassName: 'w-[45px]',
  },
  {
    label: 'sUSD.tel',
    value: `$${((params.exchangeRate ?? 0) as number).toFixed(3)}`,
    hasInfo: true,
    tooltip: SUSDTEL_TOOLTIP_TEXT,
    tooltipWidthClassName: 'w-[230px]',
    widthClassName: 'w-[60px]',
  },
]

export const getWalletPointsAndApyByAsset = (params: {
  points: number
  apy?: number | null
}): Record<PortfolioAsset, Pick<WalletRow, 'points' | 'apy'>> => ({
  'USD.tel': { points: '0', apy: '0.00%' },
  'sUSD.tel': {
    points: params.points.toLocaleString('en-US', { maximumFractionDigits: 0 }),
    apy: `${(((params.apy ?? 0) as number) * 100).toFixed(2)}%`,
  },
})

export const DEPLOYED_ROWS: DeployedRow[] = [
  {
    protocol: 'Aave',
    network: 'Base',
    asset: 'USD.tel',
    balance: '300',
    usd: '$300',
    points: '150',
    apy: '7.4%',
  },
  {
    protocol: 'Uniswap',
    network: 'Solana',
    asset: 'sUSD.tel',
    balance: '300',
    usd: '$300',
    points: '150',
    apy: '10.2%',
  },
  {
    protocol: 'Uniswap',
    network: 'Solana',
    asset: 'sUSD.tel',
    balance: '300',
    usd: '$300',
    points: '150',
    apy: '8.9%',
  },
]

export const PENDING_DEPOSITS_POPOVER_ITEMS = [
  'Days 0–28: Locked (no actions)',
  'Days 28–40: You can Cancel (get USD.tel back)',
  'Day 40+: You can Claim sUSD.tel into your wallet',
] as const
