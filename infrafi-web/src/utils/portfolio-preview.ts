export enum PortfolioView {
  Populated = 'populated',
  Empty = 'empty',
  NotConnected = 'not-connected',
  WalletEmpty = 'wallet-empty',
  DeployedEmpty = 'deployed-empty',
}

// Temporary preview switch for Portfolio mock states.
export const PORTFOLIO_PREVIEW_VIEW: PortfolioView = PortfolioView.Populated
