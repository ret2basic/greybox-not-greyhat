'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { AnchorProvider, Program } from '@coral-xyz/anchor'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import BN from 'bn.js'
import {
  PublicKey,
  TransactionInstruction,
  type Connection,
} from '@solana/web3.js'
import { useAppKitAccount, useAppKitProvider } from '@reown/appkit/react'
import { useAppKitConnection } from '@reown/appkit-adapter-solana/react'
import type { Provider } from '@reown/appkit-utils/solana'
import {
  fetchVault,
  fetchVaultPendingDepositsNullable,
  withClaimDepositedShares,
  withInitiateTransferableWithdrawalFromCustody,
  withTransferableVaultDeposit,
} from 'glow-vaults-sdk'
import IDL from 'glow-vaults-sdk/idls/glow_vault.json'
import type { GlowVault } from 'glow-vaults-sdk/idls/glow_vault'
import { GLOW_DEVNET_VAULT } from '@/lib/solana'
import { sendVaultInstructions, VAULT_TX_COMMITMENT } from '@/lib/sendVaultInstructions'
import { friendlySolanaError, isAlreadyProcessedError } from '@/lib/solanaErrors'

const DEFAULT_COMMITMENT = VAULT_TX_COMMITMENT
const CONFIGURED_MIN_STAKE_UI = process.env.NEXT_PUBLIC_GLOW_MIN_STAKE_UI?.trim() ?? ''
const QUOTE_SIMULATION_OWNER = '3hm8HtbXSV2k26hgWbmhNXh79e5bgxWZdhNGJ2NT5LbF'

type PendingDepositState = {
  index: number
  pendingSharesRaw: string
  pendingSharesUi: string
  depositTimestamp: number
  claimableAtTimestamp: number
  isClaimable: boolean
}

type StakeQuoteState = {
  sharesRaw: string | null
  sharesUi: string | null
  inputUi: string | null
  rate: number | null
}

type UseVaultStakeOptions = {
  quotePreviewAmountUi?: string
  lockQuoteToPreviewAmount?: boolean
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

function quoteSharesFromVaultState(
  amountRaw: BN,
  vaultAccount: { depositShares: BN | number | string; depositTokens: BN | number | string },
): BN {
  const totalShares = new BN(vaultAccount.depositShares.toString())
  const totalTokens = new BN(vaultAccount.depositTokens.toString())
  if (totalShares.lten(0) || totalTokens.lten(0)) {
    return amountRaw
  }
  return amountRaw.mul(totalShares).div(totalTokens)
}

function getProvider(connection: Connection, walletProvider: Provider): AnchorProvider {
  return new AnchorProvider(connection, walletProvider as AnchorProvider['wallet'], {
    commitment: DEFAULT_COMMITMENT,
  })
}

function getQuoteProvider(connection: Connection, quoteOwner: PublicKey): AnchorProvider {
  const readOnlyWallet = {
    publicKey: quoteOwner,
    signTransaction: async <T>(transaction: T): Promise<T> => transaction,
    signAllTransactions: async <T>(transactions: T[]): Promise<T[]> => transactions,
  } as AnchorProvider['wallet']
  return new AnchorProvider(connection, readOnlyWallet, {
    commitment: DEFAULT_COMMITMENT,
  })
}

function createProgram(provider: AnchorProvider): Program<GlowVault> {
  return new Program<GlowVault>(IDL as GlowVault, provider)
}

function resolveQuoteSimulationOwner(): PublicKey {
  return new PublicKey(QUOTE_SIMULATION_OWNER)
}

async function resolveMintDecimals(
  connection: Connection,
  underlyingMint: PublicKey,
  fallbackDecimals: number,
): Promise<number> {
  try {
    const supply = await connection.getTokenSupply(underlyingMint, DEFAULT_COMMITMENT)
    return supply.value.decimals
  } catch (mintError) {
    console.warn('[VaultStake] Failed to fetch mint decimals from RPC, using vault fallback.', {
      underlyingMint: underlyingMint.toBase58(),
      fallbackDecimals,
      error: mintError,
    })
    return fallbackDecimals
  }
}

export function useVaultStake(amount: string, enabled = true, options: UseVaultStakeOptions = {}) {
  const queryClient = useQueryClient()
  const { address, isConnected } = useAppKitAccount()
  const { walletProvider } = useAppKitProvider<Provider>('solana')
  const { connection } = useAppKitConnection()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [quote, setQuote] = useState<StakeQuoteState>({
    sharesRaw: null,
    sharesUi: null,
    inputUi: null,
    rate: null,
  })
  const [quoteError, setQuoteError] = useState<string | null>(null)
  const [isQuoteLoading, setIsQuoteLoading] = useState(false)
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
    queryKey: ['vault-stake-state', owner?.toBase58(), connection?.rpcEndpoint],
    enabled: enabled && !!connection,
    queryFn: async () => {
      const quoteSimulationOwner = resolveQuoteSimulationOwner()
      const provider = getQuoteProvider(connection!, quoteSimulationOwner)
      const program = createProgram(provider)
      const vault = await fetchVault(program, GLOW_DEVNET_VAULT)
      console.info('[VaultStake] Vault fee config loaded.', {
        vault: vault.address.toBase58(),
        performanceFeeRaw: vault.account.performanceFee,
        managementFeeRaw: vault.account.managementFee,
      })
      const pending = owner
        ? await fetchVaultPendingDepositsNullable(program, GLOW_DEVNET_VAULT, owner)
        : null
      const fallbackDecimals = vault.account.underlyingMintExponent
      const decimals = await resolveMintDecimals(connection!, vault.account.underlyingMint, fallbackDecimals)
      const nowSec = Math.floor(Date.now() / 1000)

      const pendingDeposits: PendingDepositState[] = pending
        ? pending.account.deposits
            .map((deposit, index) => {
              const waitSeconds = Number(deposit.deliveryWaitingPeriod)
              if (waitSeconds <= 0) {
                return null
              }
              const depositedAt = deposit.depositTimestamp.toNumber()
              const claimableAt = depositedAt + waitSeconds
              const isClaimable = nowSec >= claimableAt
              return {
                index,
                pendingSharesRaw: deposit.pendingShares.toString(),
                pendingSharesUi: formatUiAmount(deposit.pendingShares.toString(), decimals),
                depositTimestamp: depositedAt,
                claimableAtTimestamp: claimableAt,
                isClaimable,
              }
            })
            .filter((item): item is PendingDepositState => item !== null)
        : []

      const onChainMinimumRaw = vault.account.minimumDeposit.toString()
      const onChainMinimumUi = formatUiAmount(onChainMinimumRaw, decimals)

      const configuredMinStakeRaw = CONFIGURED_MIN_STAKE_UI
        ? toRawAmount(CONFIGURED_MIN_STAKE_UI, decimals).toString()
        : null
      const minimumDepositRaw =
        configuredMinStakeRaw && configuredMinStakeRaw !== '0'
          ? configuredMinStakeRaw
          : onChainMinimumRaw
      const minimumDepositUi =
        configuredMinStakeRaw && configuredMinStakeRaw !== '0'
          ? CONFIGURED_MIN_STAKE_UI
          : onChainMinimumUi

      return {
        vault,
        decimals,
        minimumDepositRaw,
        minimumDepositUi,
        pendingDeposits,
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
        ? 'Failed to load vault stake state.'
        : null

  const amountError = (() => {
    if (!state) {
      return null
    }
    if (!amount.trim()) {
      return null
    }
    const rawAmount = toRawAmount(amount, state.decimals)
    if (rawAmount.lten(0)) {
      return 'Enter a valid amount to stake.'
    }
    const minimumDeposit = new BN(state.minimumDepositRaw)
    if (rawAmount.lt(minimumDeposit)) {
      return `Minimum stake is ${state.minimumDepositUi}.`
    }
    return null
  })()

  useEffect(() => {
    const canSimulate = enabled && !!connection && !!state
    if (!canSimulate) {
      setQuote({ sharesRaw: null, sharesUi: null, inputUi: null, rate: null })
      setQuoteError(null)
      setIsQuoteLoading(false)
      return
    }

    const previewAmountUi = options.quotePreviewAmountUi?.trim() || ''
    const amountForQuoteUi = options.lockQuoteToPreviewAmount ? previewAmountUi : amount.trim() || previewAmountUi
    if (!amountForQuoteUi) {
      setQuote({ sharesRaw: null, sharesUi: null, inputUi: null, rate: null })
      setQuoteError(null)
      setIsQuoteLoading(false)
      return
    }

    const rawAmount = toRawAmount(amountForQuoteUi, state.decimals)
    if (rawAmount.lten(0)) {
      setQuote({ sharesRaw: null, sharesUi: null, inputUi: null, rate: null })
      setQuoteError(null)
      setIsQuoteLoading(false)
      return
    }

    const requestId = ++quoteRequestIdRef.current
    setQuoteError(null)
    setIsQuoteLoading(true)

    const timer = window.setTimeout(async () => {
      try {
        const simulatedSharesRaw = quoteSharesFromVaultState(rawAmount, state.vault.account).toString()
        const simulatedStakeRate = calculateRate(simulatedSharesRaw, rawAmount.toString())
        if (quoteRequestIdRef.current !== requestId) {
          return
        }

        setQuote({
          sharesRaw: simulatedSharesRaw,
          sharesUi: formatUiAmount(simulatedSharesRaw, state.decimals),
          inputUi: amountForQuoteUi,
          rate: simulatedStakeRate,
        })
        setIsQuoteLoading(false)
      } catch (simulationError) {
        if (quoteRequestIdRef.current !== requestId) {
          return
        }
        setQuote({ sharesRaw: null, sharesUi: null, inputUi: null, rate: null })
        setQuoteError(
          simulationError instanceof Error ? simulationError.message : 'Failed to derive stake quote.',
        )
        setIsQuoteLoading(false)
      }
    }, QUOTE_DEBOUNCE_MS)

    return () => {
      window.clearTimeout(timer)
    }
  }, [
    amount,
    connection,
    enabled,
    options.lockQuoteToPreviewAmount,
    options.quotePreviewAmountUi,
    state,
  ])

  const stake = async () => {
    if (!owner || !walletProvider || !connection || !state) {
      console.warn('[VaultStake] Stake skipped: missing wallet/connection/state context.', {
        hasOwner: Boolean(owner),
        hasWalletProvider: Boolean(walletProvider),
        hasConnection: Boolean(connection),
        hasState: Boolean(state),
      })
      return
    }
    const rawAmount = toRawAmount(amount, state.decimals)
    if (amountError) {
      console.warn('[VaultStake] Stake validation failed.', {
        inputAmountUi: amount,
        inputAmountRaw: rawAmount.toString(),
        error: amountError,
      })
      setError(amountError)
      return
    }
    const rawAmountString = rawAmount.toString()
    console.info('[VaultStake] Preparing stake transaction.', {
      owner: owner.toBase58(),
      rpcEndpoint: connection.rpcEndpoint,
      inputAmountUi: amount,
      amountRaw: rawAmountString,
      decimals: state.decimals,
      minimumDepositRaw: state.minimumDepositRaw,
      minimumDepositUi: state.minimumDepositUi,
    })
    setError(null)
    setIsSubmitting(true)
    try {
      const provider = getProvider(connection, walletProvider)
      const program = createProgram(provider)
      const instructions: TransactionInstruction[] = []
      await withTransferableVaultDeposit({
        program,
        vault: state.vault,
        depositor: owner,
        instructions,
        amount: rawAmount,
      })
      console.info('[VaultStake] Sending stake transaction.', {
        instructionCount: instructions.length,
        amountRaw: rawAmountString,
      })
      const signature = await sendVaultInstructions(connection, walletProvider, owner, instructions)
      console.info('[VaultStake] Stake transaction confirmed.', {
        amountRaw: rawAmountString,
        signature,
      })
      await refetchState()
      await queryClient.invalidateQueries({ queryKey: ['balance'] })
      return { signature }
    } catch (txError) {
      if (isAlreadyProcessedError(txError)) {
        // Wallet adapter retried after the deposit already landed on chain.
        // Treat as success — refresh state so the new sUSD.tel balance shows.
        console.warn('[VaultStake] Stake landed despite retry simulation error.', {
          amountRaw: rawAmountString,
          error: txError,
        })
        await refetchState()
        await queryClient.invalidateQueries({ queryKey: ['balance'] })
        return { signature: null }
      }
      console.error('[VaultStake] Stake transaction failed.', {
        amountRaw: rawAmountString,
        error: txError,
      })
      setError(friendlySolanaError(txError))
      return undefined
    } finally {
      setIsSubmitting(false)
    }
  }

  const claimDepositedShares = async (depositIndex: number) => {
    if (!owner || !walletProvider || !connection || !state) {
      return
    }
    setError(null)
    setIsSubmitting(true)
    try {
      const provider = getProvider(connection, walletProvider)
      const program = createProgram(provider)
      const instructions: TransactionInstruction[] = []
      await withClaimDepositedShares({
        program,
        vault: state.vault,
        depositor: owner,
        instructions,
        depositIndex,
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

  const cancelPendingDeposit = async (depositIndex: number) => {
    if (!owner || !walletProvider || !connection || !state) {
      return
    }
    const targetDeposit = state.pendingDeposits.find((deposit) => deposit.index === depositIndex)
    if (!targetDeposit || targetDeposit.pendingSharesRaw === '0') {
      setError('Pending deposit not found.')
      return
    }

    setError(null)
    setIsSubmitting(true)
    try {
      const provider = getProvider(connection, walletProvider)
      const program = createProgram(provider)
      const instructions: TransactionInstruction[] = []
      await withInitiateTransferableWithdrawalFromCustody({
        program,
        connection,
        vault: state.vault,
        withdrawer: owner,
        instructions,
        depositIndex,
        shares: new BN(targetDeposit.pendingSharesRaw),
      })
      await sendVaultInstructions(connection, walletProvider, owner, instructions)
      await refetchState()
      await queryClient.invalidateQueries({ queryKey: ['balance'] })
      await queryClient.invalidateQueries({ queryKey: ['vault-unstake-state'] })
    } catch (txError) {
      if (isAlreadyProcessedError(txError)) {
        await refetchState()
        await queryClient.invalidateQueries({ queryKey: ['balance'] })
        await queryClient.invalidateQueries({ queryKey: ['vault-unstake-state'] })
      } else {
        setError(friendlySolanaError(txError))
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return {
    isReady: !!owner && !!walletProvider && !!connection && isConnected && !!state,
    stake,
    claimDepositedShares,
    cancelPendingDeposit,
    pendingDeposits: state?.pendingDeposits ?? [],
    minimumDepositUi: state?.minimumDepositUi ?? null,
    amountError,
    quoteSharesRaw: quote.sharesRaw,
    quoteSharesUi: quote.sharesUi,
    quoteInputUi: quote.inputUi,
    quoteRate: quote.rate,
    quoteError,
    isQuoteLoading,
    decimals: state?.decimals ?? 6,
    isSubmitting,
    isStateLoading,
    error: stateErrorMessage ?? error,
    refresh: refetchState,
  }
}
