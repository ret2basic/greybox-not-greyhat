import { PortfolioView } from '@/utils/portfolio-preview'

export type PortfolioAsset = 'USD.tel' | 'sUSD.tel'
export type PortfolioNetwork = 'Base' | 'Solana'

export type WalletRow = {
  asset: PortfolioAsset
  balance: string
  usd: string
  lockedBalance: string
  points: string
  apy: string
  action: 'withdraw' | 'none'
  isBalanceLoading?: boolean
}

export type PortfolioProtocol = 'Aave' | 'Uniswap'

export type DeployedRow = {
  protocol: PortfolioProtocol
  network: PortfolioNetwork
  asset: PortfolioAsset
  balance: string
  usd: string
  points: string
  apy: string
}

export type PortfolioContentState = 'portfolio' | 'empty' | 'not-connected'

export type PortfolioSectionState = 'filled' | 'empty'

export type PortfolioBoostCallout = {
  title: string
  description: string
}

export type PortfolioViewConfig = {
  cardClassName: string
  contentGapClassName: string
  contentState: PortfolioContentState
  walletState?: PortfolioSectionState
  deployedState?: PortfolioSectionState
  boostCallout?: PortfolioBoostCallout
}

export type PortfolioViewConfigMap = Record<PortfolioView, PortfolioViewConfig>
