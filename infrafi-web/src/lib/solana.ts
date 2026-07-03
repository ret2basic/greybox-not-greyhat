import { Connection, PublicKey } from '@solana/web3.js'

const SOLANA_RPC_PROXY_PATH = '/api/rpc/solana/mainnet'

function getServerOrigin() {
  if (process.env.NEXT_PUBLIC_APP_URL) {
    return process.env.NEXT_PUBLIC_APP_URL
  }

  if (process.env.VERCEL_URL) {
    return `https://${process.env.VERCEL_URL}`
  }

  return `http://127.0.0.1:${process.env.PORT || 3000}`
}

function getSolanaRpcProxyEndpoint() {
  const baseUrl = typeof window === 'undefined' ? getServerOrigin() : window.location.origin
  return new URL(SOLANA_RPC_PROXY_PATH, baseUrl).toString()
}

export const USDC_MINT = new PublicKey('EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v')
export const USDTEL_MINT = new PublicKey('dawn7ZUF7h7anFuEsDdAU1Y3HYwikwqNMAENZsQJdNL')
export const DEV_USDTEL_MINT = new PublicKey(
  process.env.NEXT_PUBLIC_DEV_USDTEL_MINT ?? 'H5upkFzf3fibf5519vUm7vAtNNVzx6XR1wf9wWjYWWMA',
)
export const DEV_USDTEL_LABEL = process.env.NEXT_PUBLIC_DEV_USDTEL_LABEL ?? 'Dev USD.tel'
export const GLOW_DEVNET_VAULT = new PublicKey(
  process.env.NEXT_PUBLIC_GLOW_VAULT_ADDRESS ?? 'EzDmLUHTj53mSLN4BBrsuW8w3Gvc1iDGiYCXrkwm4vrR',
)

// In production the "dev" USD.tel mint is configured to the same address as the
// real mint, so the dev + mainnet balance queries return the *same* token.
const DEV_USDTEL_IS_DISTINCT = !DEV_USDTEL_MINT.equals(USDTEL_MINT)

// Combine the dev-mint and mainnet-mint USD.tel balances without double-counting
// when both point at the same mint. Only a genuinely separate dev token is added
// on top of the mainnet balance.
export function combineUsdtelBalances(devBalance: string, mainnetBalance: string): string {
  if (!DEV_USDTEL_IS_DISTINCT) {
    return mainnetBalance
  }
  return String(Number(devBalance) + Number(mainnetBalance))
}

export const connection = new Connection(getSolanaRpcProxyEndpoint(), 'confirmed')
