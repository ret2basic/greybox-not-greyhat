import { SolanaAdapter } from '@reown/appkit-adapter-solana/react'
import { solana, solanaDevnet, type AppKitNetwork } from '@reown/appkit/networks'

export const projectId = process.env.NEXT_PUBLIC_PROJECT_ID

if (!projectId) {
  throw new Error('NEXT_PUBLIC_PROJECT_ID is not defined')
}

const SOLANA_RPC_PROXY_PATHS = {
  mainnet: '/api/rpc/solana/mainnet',
  devnet: '/api/rpc/solana/devnet',
} as const

function getServerOrigin() {
  if (process.env.NEXT_PUBLIC_APP_URL) {
    return process.env.NEXT_PUBLIC_APP_URL
  }

  if (process.env.VERCEL_URL) {
    return `https://${process.env.VERCEL_URL}`
  }

  return `http://127.0.0.1:${process.env.PORT || 3000}`
}

export function getSolanaRpcProxyUrl(cluster: keyof typeof SOLANA_RPC_PROXY_PATHS) {
  const baseUrl = typeof window === 'undefined' ? getServerOrigin() : window.location.origin
  return new URL(SOLANA_RPC_PROXY_PATHS[cluster], baseUrl).toString()
}

const solanaMainnetRpcProxyUrl = getSolanaRpcProxyUrl('mainnet')
const solanaDevnetRpcProxyUrl = getSolanaRpcProxyUrl('devnet')

const solanaMainnetNetwork: AppKitNetwork = {
  ...solana,
  rpcUrls: {
    ...solana.rpcUrls,
    default: { http: [solanaMainnetRpcProxyUrl] },
  },
}

const solanaDevnetNetwork: AppKitNetwork = {
  ...solanaDevnet,
  rpcUrls: {
    ...solanaDevnet.rpcUrls,
    default: { http: [solanaDevnetRpcProxyUrl] },
  },
}

export const networks: [AppKitNetwork, ...AppKitNetwork[]] = [
  solanaMainnetNetwork,
  solanaDevnetNetwork,
]

export const customRpcUrls = {
  [`solana:${solana.id}`]: [{ url: solanaMainnetRpcProxyUrl }],
  [`solana:${solanaDevnet.id}`]: [{ url: solanaDevnetRpcProxyUrl }],
}

export const solanaAdapter = new SolanaAdapter({
  connectionSettings: 'confirmed',
})
