import type { FC } from 'react'
import type { StaticImageData } from 'next/image'
import { SUSDTEL_TOOLTIP_TEXT, TVL_TOOLTIP_TEXT } from '@/constants/metric-tooltips'
import BaseChainIcon from '@/assets/chains/BASE'
import SolanaChainIcon from '@/assets/chains/SOLANA'
import usdtelIcon from '@/assets/tokens/USD.tel_token_icon/USD.tel_token_icon.svg'
import susdtelIcon from '@/assets/tokens/sUSD.tel_token_icon/sUSD.tel_token_icon.svg'
import loopscaleIcon from '@/assets/tokens/boost-page/Loopscale.png'
import exponentIcon from '@/assets/tokens/boost-page/Exponent.png'
import kaminoIcon from '@/assets/tokens/boost-page/Kamino.jpg'
import orcaIcon from '@/assets/tokens/boost-page/Orca.png'
import {
  type BoostNetwork,
  BoostTab,
  type LendingRow,
  type LiquidityRow,
  type LoopingRow,
  type StrategyMetric,
  type StrategyTabConfig,
  type YieldTradingRow,
} from './types'

// Strategy rows below come from the partner plan provided by the PM. Numeric
// pool-level figures (TVL / APY / rates) are intentionally `—`: we only render
// real values where a live feed is wired (currently Orca pool data + the nav
// base APY). A connected wallet's actual position is overlaid at runtime by
// `usePartnerPositions` keyed on each row's `id`. Descriptors (protocol,
// network, market/pool type, asset/pair names) are kept as static facts.
const NO_DATA = '—'

export const BOOST_OVERVIEW_METRICS: StrategyMetric[] = [
  {
    label: 'TVL',
    value: '$686.9M',
    hasInfo: true,
    tooltip: TVL_TOOLTIP_TEXT,
    tooltipWidthClassName: 'w-[198px]',
    widthClassName: 'w-[60px]',
  },
  { label: 'APY', value: '7.40%', widthClassName: 'w-[45px]' },
  {
    label: 'sUSD.tel',
    value: '$1.073',
    hasInfo: true,
    tooltip: SUSDTEL_TOOLTIP_TEXT,
    tooltipWidthClassName: 'w-[230px]',
    widthClassName: 'w-[60px]',
  },
]

// Looping — Loopscale (live), Kamino (pending). No live pool feed wired yet, so
// quantitative cells render `—`.
export const LOOPING_ROWS: LoopingRow[] = [
  {
    id: 'loopscale-loop-susdtel',
    status: 'live',
    pool: 'sUSD.tel → USDC',
    protocol: 'Loopscale',
    network: 'Solana',
    leverage: NO_DATA,
    tvl: NO_DATA,
    apy: NO_DATA,
    apyBreakdown: '',
    depositUrl: 'https://app.loopscale.com',
  },
  {
    id: 'kamino-loop-susdtel',
    status: 'pending',
    pool: 'sUSD.tel → USDC',
    protocol: 'Kamino',
    network: 'Solana',
    leverage: NO_DATA,
    tvl: NO_DATA,
    apy: NO_DATA,
    apyBreakdown: 'Coming soon',
  },
]

// Yield Trading — Exponent: Fixed Yield (PT) and Long Yield (YT) on sUSD.tel.
// No live feed wired yet, so quantitative cells render `—`.
export const YIELD_TRADING_ROWS: YieldTradingRow[] = [
  {
    id: 'exponent-pt-susdtel',
    status: 'live',
    asset: 'PT-sUSD.tel',
    protocol: 'Exponent',
    network: 'Solana',
    maturity: NO_DATA,
    tvl: NO_DATA,
    apy: NO_DATA,
    type: 'Fixed',
    depositUrl: 'https://app.exponent.finance',
  },
  {
    id: 'exponent-yt-susdtel',
    status: 'live',
    asset: 'YT-sUSD.tel',
    protocol: 'Exponent',
    network: 'Solana',
    maturity: NO_DATA,
    tvl: NO_DATA,
    apy: NO_DATA,
    type: 'Variable',
    depositUrl: 'https://app.exponent.finance',
  },
]

// Lending — Loopscale (live), Kamino (pending). No live lend-rate feed wired
// yet, so quantitative cells render `—` (Net APY can't be formed without a real
// lend rate, even though the base APY is live).
export const LENDING_ROWS: LendingRow[] = [
  {
    id: 'loopscale-lend-susdtel',
    status: 'live',
    asset: 'sUSD.tel',
    protocol: 'Loopscale',
    network: 'Solana',
    marketType: 'Order book',
    lendRate: NO_DATA,
    tvl: NO_DATA,
    netApy: NO_DATA,
    breakdown: '',
    depositUrl: 'https://app.loopscale.com',
  },
  {
    id: 'kamino-lend-susdtel',
    status: 'pending',
    asset: 'sUSD.tel',
    protocol: 'Kamino',
    network: 'Solana',
    marketType: 'Main pool',
    lendRate: NO_DATA,
    tvl: NO_DATA,
    netApy: NO_DATA,
    breakdown: 'Coming soon',
  },
]

// Liquidity Provisioning — Exponent LP vault + Orca pools. Orca rows get live
// TVL / Fee APR / Net APY overlaid at runtime (`useOrcaPoolStats`); Exponent has
// no live feed yet so its quantitative cells render `—`.
export const LIQUIDITY_ROWS: LiquidityRow[] = [
  {
    id: 'exponent-lp-susdtel',
    status: 'live',
    pair: 'sUSD.tel LP vault',
    protocol: 'Exponent',
    network: 'Solana',
    poolType: 'LP vault',
    feeApr: NO_DATA,
    tvl: NO_DATA,
    netApy: NO_DATA,
    breakdown: '',
    depositUrl: 'https://app.exponent.finance',
  },
  {
    id: 'orca-susdtel-usdtel',
    status: 'live',
    pair: 'sUSD.tel / USD.tel',
    protocol: 'Orca',
    network: 'Solana',
    poolType: 'Concentrated LP',
    feeApr: NO_DATA,
    tvl: NO_DATA,
    netApy: NO_DATA,
    breakdown: '',
    depositUrl: 'https://www.orca.so/pools/34ri8LjXhtwViLTUNiYBJYUPMLpzKThwNgq7LZWZQz8o',
  },
  {
    id: 'orca-usdtel-usdc',
    status: 'live',
    pair: 'USD.tel / USDC',
    protocol: 'Orca',
    network: 'Solana',
    poolType: 'Concentrated LP',
    feeApr: NO_DATA,
    tvl: NO_DATA,
    netApy: NO_DATA,
    breakdown: '',
    depositUrl: 'https://www.orca.so/pools/HDHQDJENWCrw6CisxwGTSRksoWAkuQUeFxKdJ4Knf7YL',
  },
]

const STRATEGY_TAB_COUNT =
  LOOPING_ROWS.length + YIELD_TRADING_ROWS.length + LENDING_ROWS.length + LIQUIDITY_ROWS.length

export const STRATEGY_TABS: StrategyTabConfig[] = [
  {
    id: BoostTab.All,
    label: `All Strategies (${STRATEGY_TAB_COUNT})`,
    mobileLabel: `All (${STRATEGY_TAB_COUNT})`,
  },
  { id: BoostTab.Looping, label: `Looping (${LOOPING_ROWS.length})` },
  { id: BoostTab.YieldTrading, label: `Yield Trading (${YIELD_TRADING_ROWS.length})` },
  { id: BoostTab.Lending, label: `Lending (${LENDING_ROWS.length})` },
  { id: BoostTab.Liquidity, label: `Liquidity Provision (${LIQUIDITY_ROWS.length})` },
]

export const NETWORK_ICONS: Record<BoostNetwork, FC> = {
  Base: BaseChainIcon,
  Solana: SolanaChainIcon,
}

const TOKEN_ICONS = {
  'USD.tel': usdtelIcon,
  'sUSD.tel': susdtelIcon,
}

export const PROTOCOL_ICONS: Record<string, StaticImageData> = {
  Loopscale: loopscaleIcon,
  Exponent: exponentIcon,
  Kamino: kaminoIcon,
  Orca: orcaIcon,
}

export function resolveFallbackTokenIcon(title: string) {
  return title.includes('sUSD.tel') ? TOKEN_ICONS['sUSD.tel'] : TOKEN_ICONS['USD.tel']
}
