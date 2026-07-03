'use client'

import { useState } from 'react'
import { useAppKit } from '@reown/appkit/react'
import { useAppKitConnection } from '@reown/appkit-adapter-solana/react'
import { useSolanaSwap } from '@/hooks/useSolanaSwap'
import { useTokenBalances } from '@/hooks/useTokenBalances'
import { useWalletInitialization } from '@/hooks/useWalletInitialization'
import { BuyMode } from '@/hooks/buy-stake/types'
import { combineUsdtelBalances, DEV_USDTEL_MINT, USDTEL_MINT } from '@/lib/solana'
import { useCompliance } from '@/store'
import { formatTokenBalance } from '@/utils/formatAmount'

const DEFAULT_FROM_BALANCE = '0'
const DEFAULT_TO_BALANCE = '0'

const sanitizeNumericInput = (value: string) => {
  const cleaned = value.replace(/[^0-9.]/g, '')
  const [wholePart = '', ...decimalParts] = cleaned.split('.')
  const decimalPart = decimalParts.join('').slice(0, 2)
  const hasDecimalSeparator = cleaned.includes('.')

  if (cleaned === '.') {
    return '0.'
  }

  if (cleaned.startsWith('.')) {
    return `0.${decimalPart}`
  }

  return hasDecimalSeparator ? `${wholePart}.${decimalPart}` : wholePart
}

const formatInputValue = (value: string) => {
  const sanitized = sanitizeNumericInput(value)

  if (!sanitized) {
    return ''
  }

  const hasDecimalSeparator = sanitized.includes('.')
  const [wholePart = '0', decimalPart = ''] = sanitized.split('.')
  const normalizedWholePart = wholePart.replace(/^0+(?=\d)/, '') || '0'
  const formattedWholePart = normalizedWholePart.replace(/\B(?=(\d{3})+(?!\d))/g, ',')

  if (!hasDecimalSeparator) {
    return formattedWholePart
  }

  return decimalPart.length > 0 ? `${formattedWholePart}.${decimalPart}` : `${formattedWholePart}.`
}

const parseAmount = (value: string) => {
  const numericValue = Number(value.replace(/,/g, ''))
  return Number.isFinite(numericValue) ? numericValue : 0
}

const formatDollarValue = (amount: number) => `$${amount.toFixed(2)}`

const formatReceiveAmount = (amount: number) =>
  amount.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })

export const useBuyForm = (mode: BuyMode) => {
  const [fromAmount, setFromAmount] = useState<string>('')
  const { open } = useAppKit()
  const { connection } = useAppKitConnection()
  const requestWalletConnection = useCompliance((state) => state.requestWalletConnection)
  const isWalletInitializing = useWalletInitialization()
  const amountForQuote = fromAmount.replace(/,/g, '')
  const numericAmount = parseAmount(fromAmount)
  const hasAmount = numericAmount > 0
  const swapDirection = mode === BuyMode.Withdraw ? 'sell' : 'buy'

  const {
    quote,
    quoteAmountOut,
    isQuoteLoading,
    quoteError,
    executeSwap,
    isSwapping,
    isSwappingProcessing,
    swapError,
    swapSignatures,
    clearSwapStatus,
    isConnected,
    address,
  } = useSolanaSwap(amountForQuote, swapDirection)

  const { usdcBalance, usdtelBalance: devUsdtelBalance, isLoading: isDevBalanceLoading } = useTokenBalances(
    address,
    connection ?? undefined,
    DEV_USDTEL_MINT,
    {
      includeSusdtel: false,
    },
  )
  const { usdtelBalance: mainnetUsdtelBalance, isLoading: isMainnetBalanceLoading } = useTokenBalances(
    address,
    connection ?? undefined,
    USDTEL_MINT,
    { includeUsdc: false, includeSusdtel: false },
  )
  const isBalanceLoading = isDevBalanceLoading || isMainnetBalanceLoading
  const usdtelBalance = combineUsdtelBalances(devUsdtelBalance, mainnetUsdtelBalance)

  const fromBalanceRaw = mode === BuyMode.Withdraw ? usdtelBalance : usdcBalance
  const toBalanceRaw = mode === BuyMode.Withdraw ? usdcBalance : usdtelBalance
  const fromBalanceAmount = parseAmount(fromBalanceRaw)
  const fromTokenLabel = mode === BuyMode.Withdraw ? 'USD.tel' : 'USDC'
  const amountError =
    isConnected && hasAmount && !isBalanceLoading && numericAmount > fromBalanceAmount
      ? `Insufficient ${fromTokenLabel} balance.`
      : null

  const effectiveReceiveAmount = hasAmount
    ? isConnected && quoteAmountOut
      ? parseAmount(quoteAmountOut)
      : numericAmount
    : 0

  const isReceiveAmountLoading = isConnected && hasAmount && !quoteAmountOut && !quoteError
  const displayReceiveAmount = hasAmount
    ? isConnected
      ? quoteAmountOut
        ? formatReceiveAmount(effectiveReceiveAmount)
        : '0'
      : formatReceiveAmount(effectiveReceiveAmount)
    : '0'
  const payDollarValue = hasAmount ? formatDollarValue(numericAmount) : '$0.00'
  const receiveDollarValue = hasAmount
    ? isConnected
      ? quoteAmountOut
        ? formatDollarValue(effectiveReceiveAmount)
        : '...'
      : formatDollarValue(effectiveReceiveAmount)
    : '$0.00'

  const displayFromBalance = isConnected
    ? formatTokenBalance(fromBalanceRaw)
    : DEFAULT_FROM_BALANCE
  const displayToBalance = isConnected ? formatTokenBalance(toBalanceRaw) : DEFAULT_TO_BALANCE

  const handleAmountChange = (value: string) => {
    clearSwapStatus()
    setFromAmount(formatInputValue(value))
  }

  const handleMaxClick = () => {
    clearSwapStatus()
    setFromAmount(formatInputValue(isConnected ? fromBalanceRaw : '0'))
  }

  const handleConnectWallet = () => {
    void requestWalletConnection(() => open())
  }

  const buttonLabel = (() => {
    if (!isConnected) return 'Connect Wallet'
    if (isSwapping) return 'Swapping'
    if (isQuoteLoading) return 'Fetching Quote'
    return mode === BuyMode.Withdraw ? 'Withdraw' : 'Buy'
  })()

  const canSubmit =
    isConnected && !!quote && !isQuoteLoading && !isSwapping && hasAmount && !amountError

  const handleBuy = async () => {
    if (!hasAmount) {
      return undefined
    }
    return executeSwap()
  }

  return {
    amountError,
    buttonLabel,
    canSubmit,
    displayFromBalance,
    displayReceiveAmount,
    displayToBalance,
    fromAmount,
    handleAmountChange,
    handleBuy,
    handleConnectWallet,
    handleMaxClick,
    isConnected,
    isWalletInitializing,
    isBalanceLoading,
    isSwapping,
    isSwappingProcessing,
    isQuoteLoading,
    isReceiveAmountLoading,
    payDollarValue,
    quoteError,
    receiveDollarValue,
    swapError,
    swapSignatures,
  }
}
