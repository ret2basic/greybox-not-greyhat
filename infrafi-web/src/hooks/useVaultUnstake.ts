'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { AnchorProvider, Program } from '@coral-xyz/anchor'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import BN from 'bn.js'
import { useAppKitAccount, useAppKitProvider } from '@reown/appkit/react'
import { useAppKitConnection } from '@reown/appkit-adapter-solana/react'
import type { Provider } from '@reown/appkit-utils/solana'
import {
  PublicKey,
  SendTransactionError,
  TransactionInstruction,
  type Connection,
} from '@solana/web3.js'
import {
  fetchVault,
  fetchVaultPendingWithdrawalsNullable,
  withCancelTransferableVaultPendingWithdrawal,
  withExecuteTransferableVaultWithdrawal,
  withInitiateTransferableVaultWithdrawal,
} from 'glow-vaults-sdk'
import IDL from 'glow-vaults-sdk/idls/glow_vault.json'
import type { GlowVault } from 'glow-vaults-sdk/idls/glow_vault'
import { GLOW_DEVNET_VAULT } from '@/lib/solana'
import { sendVaultInstructions, VAULT_TX_COMMITMENT } from '@/lib/sendVaultInstructions'
import { friendlySolanaError, isAlreadyProcessedError } from '@/lib/solanaErrors'

const DEFAULT_COMMITMENT = VAULT_TX_COMMITMENT

type PendingWithdrawalState = {
  index: number
  pendingSharesRaw: string
  pendingAssetsRaw: string
  requestedAtTimestamp: number
  executableAtTimestamp: number
  isExecutable: boolean
}

type UnstakeQuoteState = {
  assetsRaw: string | null
  assetsUi: string | null
  inputUi: string | null
  rate: number | null
}

const QUOTE_DEBOUNCE_MS = 400

function toRawAmount(value: string, decimals: number): BN {
  const normalized = value.trim()
  if (!normalized) {
    return new BN(0)
  }
  const [whole = '0', fractional = ''] = normalized.split('.')
  const safeWhole = whole.replace(/[^\d]/g, '') || '0'
  const safeFractional = fractional.replace(/[^\d]/g, '').slice(0, decimals)
  const paddedFractional = safeFractional.padEnd(decimals, '0')
  const raw = `${safeWhole}${paddedFractional}`.replace(/^0+(?=\d)/, '') || '0'
  return new BN(raw)
}

function formatUiAmount(rawAmount: string, decimals: number): string {
  if (!rawAmount) {
    return '0'
  }
  const negative = rawAmount.startsWith('-')
  const value = negative ? rawAmount.slice(1) : rawAmount
  const padded = value.padStart(decimals + 1, '0')
  const whole = padded.slice(0, -decimals) || '0'
  const frac = decimals === 0 ? '' : padded.slice(-decimals).replace(/0+$/, '')
  return `${negative ? '-' : ''}${whole}${frac ? `.${frac}` : ''}`
}

function calculateRate(numeratorRaw: string, denominatorRaw: string): number | null {
  const numerator = new BN(numeratorRaw)
  const denominator = new BN(denominatorRaw)
  if (denominator.lten(0)) {
    return null
  }
  const scale = new BN(1_000_000_000)
  const scaled = numerator.mul(scale).div(denominator)
  return Number(scaled.toString()) / 1_000_000_000
}

function quoteAssetsFromVaultState(
  sharesRaw: BN,
  vaultAccount: { depositShares: BN | number | string; depositTokens: BN | number | string },
): BN {
  const totalShares = new BN(vaultAccount.depositShares.toString())
  const totalTokens = new BN(vaultAccount.depositTokens.toString())
  if (totalShares.lten(0) || totalTokens.lten(0)) {
    return sharesRaw
  }
  return sharesRaw.mul(totalTokens).div(totalShares)
}

// The vault's `underlyingMintExponent` is a signed *price exponent* (e.g. -6 for
// a 6-decimal mint), not a token-decimals count. Feeding it straight into
// `toRawAmount` underscales the amount by 10^decimals (10 -> 10 raw base units
// instead of 10_000_000), so resolve real decimals from the mint like the stake
// hook does, falling back to the magnitude of the exponent if RPC fails.
async function resolveMintDecimals(
  connection: Connection,
  underlyingMint: PublicKey,
  fallbackExponent: number,
): Promise<number> {
  try {
    const supply = await connection.getTokenSupply(underlyingMint, DEFAULT_COMMITMENT)
    return supply.value.decimals
  } catch (mintError) {
    console.warn('[VaultUnstake] Failed to fetch mint decimals from RPC, using vault fallback.', {
      underlyingMint: underlyingMint.toBase58(),
      fallbackExponent,
      error: mintError,
    })
    return Math.abs(fallbackExponent)
  }
}

function getProvider(connection: Connection, walletProvider: Provider): AnchorProvider {
  return new AnchorProvider(connection, walletProvider as AnchorProvider['wallet'], {
    commitment: DEFAULT_COMMITMENT,
  })
}

function createProgram(provider: AnchorProvider): Program<GlowVault> {
  return new Program<GlowVault>(IDL as GlowVault, provider)
}

export function useVaultUnstake(amount: string, enabled = true) {
  const queryClient = useQueryClient()
  const { address, isConnected } = useAppKitAccount()
  const { walletProvider } = useAppKitProvider<Provider>('solana')
  const { connection } = useAppKitConnection()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [quote, setQuote] = useState<UnstakeQuoteState>({
    assetsRaw: null,
    assetsUi: null,
    inputUi: null,
    rate: null,
  })
  const [quoteError, setQuoteError] = useState<string | null>(null)
  const quoteRequestIdRef = useRef(0)

  const owner = useMemo(() => {
    if (!address) {
      return null
    }
    try {
      return walletProvider?.publicKey ?? null
    } catch {
      return null
    }
  }, [address, walletProvider])

  const {
    data: state,
    isLoading: isStateLoading,
    refetch: refetchState,
    error: stateLoadError,
  } = useQuery({
    queryKey: ['vault-unstake-state', owner?.toBase58(), connection?.rpcEndpoint],
    enabled: enabled && !!owner && !!walletProvider && !!connection && isConnected,
    queryFn: async () => {
      const provider = getProvider(connection!, walletProvider!)
      const program = createProgram(provider)
      const vault = await fetchVault(program, GLOW_DEVNET_VAULT)
      console.info('[VaultUnstake] Vault fee config loaded.', {
        vault: vault.address.toBase58(),
        performanceFeeRaw: vault.account.performanceFee,
        managementFeeRaw: vault.account.managementFee,
      })
      const pending = await fetchVaultPendingWithdrawalsNullable(program, GLOW_DEVNET_VAULT, owner!)
      const decimals = await resolveMintDecimals(
        connection!,
        vault.account.underlyingMint,
        vault.account.underlyingMintExponent,
      )
      const nowSec = Math.floor(Date.now() / 1000)
      const pendingWithdrawals: PendingWithdrawalState[] = pending
        ? pending.account.withdrawals
            .map((withdrawal, index) => {
              const waitPeriod = Number(withdrawal.withdrawalWaitingPeriod)
              if (waitPeriod <= 0) {
                return null
              }
              const requestedAt = withdrawal.withdrawalRequestTimestamp.toNumber()
              const executableAt = requestedAt + waitPeriod
              return {
                index,
                pendingSharesRaw: withdrawal.pendingShares.toString(),
                pendingAssetsRaw: withdrawal.pendingAssets.toString(),
                requestedAtTimestamp: requestedAt,
                executableAtTimestamp: executableAt,
                isExecutable: nowSec >= executableAt,
              }
            })
            .filter((item): item is PendingWithdrawalState => item !== null)
        : []

      return {
        vault,
        decimals,
        pendingWithdrawals,
      }
    },
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
  const stateErrorMessage =
    stateLoadError instanceof Error
      ? stateLoadError.message
      : stateLoadError
        ? 'Failed to load vault unstake state.'
        : null

  useEffect(() => {
    const canSimulate = enabled && !!owner && !!walletProvider && !!connection && isConnected && !!state
    if (!canSimulate) {
      setQuote({ assetsRaw: null, assetsUi: null, inputUi: null, rate: null })
      setQuoteError(null)
      return
    }

    const amountForQuoteUi = amount.trim()
    if (!amountForQuoteUi) {
      setQuote({ assetsRaw: null, assetsUi: null, inputUi: null, rate: null })
      setQuoteError(null)
      return
    }

    const rawAmount = toRawAmount(amountForQuoteUi, state.decimals)
    if (rawAmount.lten(0)) {
      setQuote({ assetsRaw: null, assetsUi: null, inputUi: null, rate: null })
      setQuoteError(null)
      return
    }

    const requestId = ++quoteRequestIdRef.current
    setQuoteError(null)

    const timer = window.setTimeout(async () => {
      try {
        const simulatedAssetsRaw = quoteAssetsFromVaultState(rawAmount, state.vault.account).toString()
        const simulatedUnstakeRate = calculateRate(simulatedAssetsRaw, rawAmount.toString())
        if (quoteRequestIdRef.current !== requestId) {
          return
        }

        setQuote({
          assetsRaw: simulatedAssetsRaw,
          assetsUi: formatUiAmount(simulatedAssetsRaw, state.decimals),
          inputUi: amountForQuoteUi,
          rate: simulatedUnstakeRate,
        })
      } catch (simulationError) {
        if (quoteRequestIdRef.current !== requestId) {
          return
        }
        setQuote({ assetsRaw: null, assetsUi: null, inputUi: null, rate: null })
        setQuoteError(
          simulationError instanceof Error ? simulationError.message : 'Failed to derive unstake quote.',
        )
      }
    }, QUOTE_DEBOUNCE_MS)

    return () => {
      window.clearTimeout(timer)
    }
  }, [amount, connection, enabled, isConnected, owner, state, walletProvider])

  const initiateUnstake = async () => {
    if (!owner || !walletProvider || !connection || !state) {
      return
    }
    const rawAmount = toRawAmount(amount, state.decimals)
    if (rawAmount.lten(0)) {
      setError('Enter a valid amount to unstake.')
      return
    }
    setError(null)
    setIsSubmitting(true)
    try {
      const provider = getProvider(connection, walletProvider)
      const program = createProgram(provider)
      const instructions: TransactionInstruction[] = []
      await withInitiateTransferableVaultWithdrawal({
        program,
        connection,
        vault: state.vault,
        withdrawer: owner,
        instructions,
        amount: rawAmount,
      })
      const signature = await sendVaultInstructions(connection, walletProvider, owner, instructions)
      await refetchState()
      await queryClient.invalidateQueries({ queryKey: ['balance'] })
      return { signature }
    } catch (txError) {
      if (isAlreadyProcessedError(txError)) {
        await refetchState()
        await queryClient.invalidateQueries({ queryKey: ['balance'] })
        return { signature: null }
      }
      if (txError instanceof SendTransactionError) {
        try {
          const logs = await txError.getLogs(connection)
          // Concatenate logs into the message so friendlySolanaError can
          // pick out the AnchorError line, then surface the friendly form.
          const combined =
            logs && logs.length > 0
              ? `${txError.message}\n${logs.join('\n')}`
              : txError.message
          console.error('[VaultUnstake] Initiate unstake program error.', {
            message: txError.message,
            logs,
          })
          setError(friendlySolanaError(new Error(combined)))
        } catch {
          setError(friendlySolanaError(txError))
        }
      } else {
        setError(friendlySolanaError(txError))
      }
      return undefined
    } finally {
      setIsSubmitting(false)
    }
  }

  const executeUnstake = async (withdrawalIndex: number) => {
    if (!owner || !walletProvider || !connection || !state) {
      return
    }
    setError(null)
    setIsSubmitting(true)
    try {
      const provider = getProvider(connection, walletProvider)
      const program = createProgram(provider)
      const instructions: TransactionInstruction[] = []
      await withExecuteTransferableVaultWithdrawal({
        program,
        vault: state.vault,
        withdrawer: owner,
        instructions,
        withdrawalIndex,
      })
      await sendVaultInstructions(connection, walletProvider, owner, instructions)
      await refetchState()
      await queryClient.invalidateQueries({ queryKey: ['balance'] })
    } catch (txError) {
      if (isAlreadyProcessedError(txError)) {
        await refetchState()
        await queryClient.invalidateQueries({ queryKey: ['balance'] })
      } else {
        setError(friendlySolanaError(txError))
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  const cancelUnstake = async (withdrawalIndex: number) => {
    if (!owner || !walletProvider || !connection || !state) {
      return
    }
    setError(null)
    setIsSubmitting(true)
    try {
      const provider = getProvider(connection, walletProvider)
      const program = createProgram(provider)
      const instructions: TransactionInstruction[] = []
      await withCancelTransferableVaultPendingWithdrawal({
        program,
        vault: state.vault,
        owner,
        instructions,
        withdrawalIndex,
      })
      await sendVaultInstructions(connection, walletProvider, owner, instructions)
      await refetchState()
      await queryClient.invalidateQueries({ queryKey: ['balance'] })
    } catch (txError) {
      if (isAlreadyProcessedError(txError)) {
        await refetchState()
        await queryClient.invalidateQueries({ queryKey: ['balance'] })
      } else {
        setError(friendlySolanaError(txError))
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return {
    isReady: !!owner && !!walletProvider && !!connection && isConnected && !!state,
    initiateUnstake,
    executeUnstake,
    cancelUnstake,
    pendingWithdrawals: state?.pendingWithdrawals ?? [],
    quoteAssetsRaw: quote.assetsRaw,
    quoteAssetsUi: quote.assetsUi,
    quoteInputUi: quote.inputUi,
    quoteRate: quote.rate,
    quoteError,
    decimals: state?.decimals ?? 6,
    isSubmitting,
    isStateLoading,
    error: stateErrorMessage ?? error,
    refresh: refetchState,
  }
}
