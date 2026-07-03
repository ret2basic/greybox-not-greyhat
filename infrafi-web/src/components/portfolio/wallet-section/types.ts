import type { PortfolioSectionState } from '@/components/portfolio/types'
import type { PortfolioBalances } from '@/hooks/portfolio/usePortfolioBalances'

export type PendingDepositActionStyle = 'muted' | 'accent'
export type PortfolioWalletTab = 'positions' | 'leaderboard'

export type PortfolioSectionProps = {
  state: PortfolioSectionState
  activeTab: PortfolioWalletTab
  balances: PortfolioBalances
  onTabChange: (tab: PortfolioWalletTab) => void
}
