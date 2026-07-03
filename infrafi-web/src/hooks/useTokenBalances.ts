'use client'

import { useQuery } from '@tanstack/react-query'
import {
  TOKEN_2022_PROGRAM_ID,
  TOKEN_PROGRAM_ID,
  getAssociatedTokenAddressSync,
} from '@solana/spl-token'
import { PublicKey, type Connection } from '@solana/web3.js'
import { deriveVaultShareMint } from 'glow-vaults-sdk'
import { GLOW_DEVNET_VAULT, USDC_MINT, USDTEL_MINT } from '@/lib/solana'

const KNOWN_TOKEN_PROGRAMS: Record<string, PublicKey> = {
  [USDC_MINT.toBase58()]: TOKEN_PROGRAM_ID,
  [USDTEL_MINT.toBase58()]: TOKEN_2022_PROGRAM_ID,
}

type TokenBalanceSelection = {
  includeUsdc?: boolean
  includeUsdtel?: boolean
  includeSusdtel?: boolean
}

async function resolveTokenProgramId(
  rpc: Connection,
  mint: PublicKey,
  tokenProgramOverride?: PublicKey,
): Promise<PublicKey> {
  if (tokenProgramOverride) {
    return tokenProgramOverride
  }

  const knownTokenProgram = KNOWN_TOKEN_PROGRAMS[mint.toBase58()]
  if (knownTokenProgram) {
    return knownTokenProgram
  }

  const mintAccount = await rpc.getAccountInfo(mint)
  return mintAccount?.owner ?? TOKEN_PROGRAM_ID
}

async function fetchTokenBalance(
  rpc: Connection,
  mint: PublicKey,
  owner: PublicKey,
  tokenProgramOverride?: PublicKey,
): Promise<string> {
  const tokenProgramId = await resolveTokenProgramId(rpc, mint, tokenProgramOverride)
  const ata = getAssociatedTokenAddressSync(mint, owner, false, tokenProgramId)
  try {
    const balance = await rpc.getTokenAccountBalance(ata)
    return balance.value.uiAmountString ?? '0'
  } catch {
    // ATA may not exist — scan all token accounts for this mint as a fallback
    try {
      const accounts = await rpc.getParsedTokenAccountsByOwner(owner, { mint })
      if (accounts.value.length > 0) {
        return accounts.value[0].account.data.parsed.info.tokenAmount.uiAmountString ?? '0'
      }
    } catch {
      // wallet has no account for this token
    }
    return '0'
  }
}

async function fetchTokenBalanceByAta(rpc: Connection, ata: PublicKey): Promise<string> {
  try {
    const balance = await rpc.getTokenAccountBalance(ata)
    return balance.value.uiAmountString ?? '0'
  } catch {
    return '0'
  }
}

export function useTokenBalances(
  address: string | undefined,
  connectionOverride?: Connection | null,
  underlyingMintOverride?: PublicKey,
  selection: TokenBalanceSelection = {},
) {
  const ownerKey = (() => {
    if (!address) {
      return null
    }

    try {
      return new PublicKey(address)
    } catch {
      return null
    }
  })()
  const rpc = connectionOverride ?? null
  const rpcEndpoint = rpc?.rpcEndpoint ?? 'no-rpc'
  const underlyingMint = underlyingMintOverride ?? USDTEL_MINT
  const includeUsdc = selection.includeUsdc ?? true
  const includeUsdtel = selection.includeUsdtel ?? true
  const includeSusdtel = selection.includeSusdtel ?? true

  const { data: usdcBalance = '0', isLoading: usdcLoading } = useQuery({
    queryKey: ['balance', 'usdc', address, rpcEndpoint],
    queryFn: () => fetchTokenBalance(rpc!, USDC_MINT, ownerKey!, TOKEN_PROGRAM_ID),
    enabled: !!ownerKey && !!rpc && includeUsdc,
    staleTime: Infinity,
    refetchOnMount: 'always',
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  const { data: usdtelBalance = '0', isLoading: usdtelLoading } = useQuery({
    queryKey: ['balance', 'usdtel', underlyingMint.toBase58(), address, rpcEndpoint],
    queryFn: () => fetchTokenBalance(rpc!, underlyingMint, ownerKey!),
    enabled: !!ownerKey && !!rpc && includeUsdtel,
    staleTime: Infinity,
    refetchOnMount: 'always',
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  const { data: susdtelBalance = '0', isLoading: susdtelLoading } = useQuery({
    queryKey: ['balance', 'susdtel', address, rpcEndpoint],
    queryFn: async () => {
      const shareMint = deriveVaultShareMint(GLOW_DEVNET_VAULT)
      const shareAta = getAssociatedTokenAddressSync(
        shareMint,
        ownerKey!,
        false,
        TOKEN_2022_PROGRAM_ID,
      )
      return fetchTokenBalanceByAta(rpc!, shareAta)
    },
    enabled: !!ownerKey && !!rpc && includeSusdtel,
    staleTime: Infinity,
    refetchOnMount: 'always',
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  return {
    usdcBalance,
    usdtelBalance,
    susdtelBalance,
    isLoading: usdcLoading || usdtelLoading || susdtelLoading,
  }
}
