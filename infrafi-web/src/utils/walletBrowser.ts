const MOBILE_USER_AGENT_REGEX =
  /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i

const WALLET_BROWSER_USER_AGENT_REGEX =
  /MetaMaskMobile|Trust|CoinbaseWallet|Phantom|TokenPocket|OKX|BitKeep|Bitget|imToken|Rainbow/i

type WalletAwareWindow = Window & {
  ethereum?: {
    isMetaMask?: boolean
    isTrust?: boolean
    isCoinbaseWallet?: boolean
    isTokenPocket?: boolean
    providers?: Array<{
      isMetaMask?: boolean
      isTrust?: boolean
      isCoinbaseWallet?: boolean
    }>
  }
  phantom?: {
    solana?: unknown
  }
  solana?: {
    isPhantom?: boolean
    isTrust?: boolean
  }
}

const hasInjectedWalletProvider = (windowObject: WalletAwareWindow) => {
  const ethereumProviders = windowObject.ethereum?.providers ?? []

  return Boolean(
    windowObject.solana?.isPhantom ||
      windowObject.solana?.isTrust ||
      windowObject.phantom?.solana ||
      windowObject.ethereum?.isMetaMask ||
      windowObject.ethereum?.isTrust ||
      windowObject.ethereum?.isCoinbaseWallet ||
      windowObject.ethereum?.isTokenPocket ||
      ethereumProviders.some(
        (provider) => provider.isMetaMask || provider.isTrust || provider.isCoinbaseWallet,
      ),
  )
}

export const shouldShowWalletBrowserPrompt = () => {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') {
    return false
  }

  const userAgent = navigator.userAgent ?? ''
  const isMobileDevice = MOBILE_USER_AGENT_REGEX.test(userAgent)

  if (!isMobileDevice) {
    return false
  }

  const isWalletBrowserUserAgent = WALLET_BROWSER_USER_AGENT_REGEX.test(userAgent)

  if (isWalletBrowserUserAgent) {
    return false
  }

  return !hasInjectedWalletProvider(window as WalletAwareWindow)
}
