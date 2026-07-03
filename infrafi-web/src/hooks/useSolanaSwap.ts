'use client'

import { useState, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useAppKitAccount, useAppKitProvider } from '@reown/appkit/react'
import { useAppKitConnection } from '@reown/appkit-adapter-solana/react'
import type { Provider } from '@reown/appkit-utils/solana'
import { PublicKey, SendTransactionError } from '@solana/web3.js'
import { confirmSolanaSignature } from '@/lib/confirmSolanaSignature'
import { fetchQuote, toRawAmount, fromRawAmount, deserializeTransaction, type SwapDirection } from '@/lib/m0'

const SWAP_CONFIRM_COMMITMENT = 'confirmed' as const
const M0_QUOTE_PREVIEW_WALLET = process.env.NEXT_PUBLIC_M0_QUOTE_PREVIEW_WALLET

function normalizePublicWalletAddress(value: string | undefined): string | null {
  if (!value || /^YOUR_[A-Z0-9_]+_HERE$/i.test(value.trim())) {
    return null
  }

  try {
    return new PublicKey(value).toBase58()
  } catch {
    return null
  }
}

export function useSolanaSwap(amountIn: string, direction: SwapDirection) {
  const queryClient = useQueryClient()
  const { address, isConnected } = useAppKitAccount()
  const { walletProvider } = useAppKitProvider<Provider>('solana')
  const { connection } = useAppKitConnection()
  const solanaAddress = (() => {
    if (!address) {
      return null
    }

    try {
      return new PublicKey(address).toBase58()
    } catch {
      return null
    }
  })()

  const [debouncedAmount, setDebouncedAmount] = useState(amountIn)
  const [isSwapping, setIsSwapping] = useState(false)
  const [isSwappingProcessing, setIsSwappingProcessing] = useState(false)
  const [swapError, setSwapError] = useState<string | null>(null)
  const [swapSignatures, setSwapSignatures] = useState<string[]>([])

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedAmount(amountIn), 500)
    return () => clearTimeout(timer)
  }, [amountIn])

  const rawAmount = toRawAmount(debouncedAmount, direction)
  const previewWallet = normalizePublicWalletAddress(M0_QUOTE_PREVIEW_WALLET)
  const canFetchQuote = isConnected && !!solanaAddress && !!previewWallet && rawAmount !== '0'

  const {
    data: quote,
    isLoading: isQuoteLoading,
    error: quoteError,
  } = useQuery({
    queryKey: ['m0-quote', rawAmount, direction, previewWallet],
    queryFn: () => fetchQuote(rawAmount, direction, previewWallet!),
    enabled: canFetchQuote,
    staleTime: 20_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: 1,
  })

  const quoteAmountOut = quote ? fromRawAmount(quote.amountOut, direction === 'buy' ? 'sell' : 'buy') : ''

  const executeSwap = async (overrideAmountIn?: string) => {
    if (!walletProvider || !connection || !solanaAddress) {
      console.warn('[executeSwap] aborted — missing prerequisites', {
        hasWalletProvider: !!walletProvider,
        hasConnection: !!connection,
        address: solanaAddress,
      })
      return
    }

    const requestedRawAmount = overrideAmountIn
      ? toRawAmount(overrideAmountIn, direction)
      : quote?.amountIn ?? rawAmount

    if (!requestedRawAmount || requestedRawAmount === '0') {
      setSwapError('Enter an amount greater than 0.')
      return
    }

    console.log('[executeSwap] starting swap', {
      direction,
      amountIn: requestedRawAmount,
      sender: solanaAddress,
    })

    setIsSwapping(true)
    setSwapError(null)
    setSwapSignatures([])

    try {
      const executableQuote = await fetchQuote(requestedRawAmount, direction, solanaAddress)
      console.log('[executeSwap] quote resolved', {
        amountIn: executableQuote.amountIn,
        amountOut: executableQuote.amountOut,
      })
      console.log('[executeSwap] orchestration payload count', { count: executableQuote.transactionBase64s.length })
      const confirmedSignatures: string[] = []
      for (let index = 0; index < executableQuote.transactionBase64s.length; index += 1) {
        const tx = deserializeTransaction(executableQuote.transactionBase64s[index])
        console.log('[executeSwap] transaction deserialized', {
          payloadIndex: index,
          numInstructions: tx.message.compiledInstructions.length,
        })

        const { blockhash } = await connection.getLatestBlockhash(SWAP_CONFIRM_COMMITMENT)
        tx.message.recentBlockhash = blockhash

        console.log('[executeSwap] sending transaction...', { payloadIndex: index })
        const sig = await walletProvider.sendTransaction(tx, connection)
        setIsSwappingProcessing(true)
        console.log('[executeSwap] transaction sent', {
          payloadIndex: index,
          signature: sig,
          explorerUrl: `https://solscan.io/tx/${sig}`,
        })

        console.log('[executeSwap] waiting for confirmation...', { payloadIndex: index })
        await confirmSolanaSignature(connection, sig, SWAP_CONFIRM_COMMITMENT)
        console.log('[executeSwap] confirmed ✓', { payloadIndex: index, signature: sig })
        confirmedSignatures.push(sig)
      }

      setSwapSignatures(confirmedSignatures)
      await queryClient.invalidateQueries({ queryKey: ['balance'] })
      return { signatures: confirmedSignatures }
    } catch (err) {
      console.error('[executeSwap] failed', err)
      if (err instanceof SendTransactionError) {
        const logs = await err.getLogs(connection).catch(() => null)
        if (logs && logs.length > 0) {
          console.error('[executeSwap] simulation/program logs', logs)
          setSwapError(`${err.message}\n${logs.join('\n')}`)
          return undefined
        }
      }
      setSwapError(err instanceof Error ? err.message : 'Swap failed. Please try again.')
      return undefined
    } finally {
      setIsSwappingProcessing(false)
      setIsSwapping(false)
    }
  }

  const clearSwapStatus = () => {
    setSwapError(null)
    setSwapSignatures([])
  }

  return {
    quote,
    quoteAmountOut,
    isQuoteLoading,
    quoteError: quoteError instanceof Error ? quoteError.message : quoteError ? 'Failed to fetch quote' : null,
    executeSwap,
    isSwapping,
    isSwappingProcessing,
    swapError,
    swapSignatures,
    clearSwapStatus,
    isConnected: isConnected && !!solanaAddress,
    address: solanaAddress ?? undefined,
  }
}
