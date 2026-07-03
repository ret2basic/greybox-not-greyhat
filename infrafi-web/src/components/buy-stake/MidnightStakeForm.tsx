'use client'

import { useEffect, useMemo, useState } from 'react'
import { useAppKit, useAppKitAccount } from '@reown/appkit/react'
import { useAppKitConnection } from '@reown/appkit-adapter-solana/react'
import { StakeMode } from '@/hooks/buy-stake/types'
import { useTokenBalances } from '@/hooks/useTokenBalances'
import { useVaultStake } from '@/hooks/useVaultStake'
import { useVaultUnstake } from '@/hooks/useVaultUnstake'
import { combineUsdtelBalances, DEV_USDTEL_MINT, USDTEL_MINT } from '@/lib/solana'
import { useCompliance, useNav, liveSharePrice } from '@/store'
import { GradientButton } from '@/components/ui/GradientButton'
import { TokenInput, SwitchArrow } from './TokenInput'

type Props = {
  mode: StakeMode
  onModeChange: (mode: StakeMode) => void
  onTxStart?: (info: { stakeMode: StakeMode; amountIn: number; amountOut: number }) => void
  onTxResult?: (result: { ok: boolean; signature?: string | null }) => void
  // Reports the latest pending-deposit count up so the parent can render
  // the in-overlay footer slot (Figma 6575-9515).
  onPendingDepositCountChange?: (count: number) => void
  // Mobile sizing pass — forwarded to the token inputs / switch (Figma 6605-6560).
  compact?: boolean
}

const fmtUsd = (n: number) => {
  if (!Number.isFinite(n)) return '$0'
  return `$${n.toLocaleString('en-US', { maximumFractionDigits: 2 })}`
}

const formatBalanceValue = (value: string) => {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) {
    return '0.00'
  }
  return numeric.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

const formatCalculatedAmount = (value: number) => {
  if (!Number.isFinite(value) || value <= 0) {
    return '0.00'
  }

  return value.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  })
}

const formatExchangeRate = (value: number) => {
  if (!Number.isFinite(value) || value <= 0) {
    return '0'
  }

  return value.toFixed(6)
}

const sanitizeNumeric = (value: string) => {
  const cleaned = value.replace(/[^0-9.]/g, '')
  if (cleaned === '.') return '0.'
  if (cleaned.startsWith('.')) return `0${cleaned}`
  const [whole = '', ...rest] = cleaned.split('.')
  if (rest.length === 0) return whole.replace(/^0+(?=\d)/, '') || whole
  return `${whole.replace(/^0+(?=\d)/, '') || '0'}.${rest.join('')}`
}

export function MidnightStakeForm({
  mode,
  onModeChange,
  onTxStart,
  onTxResult,
  onPendingDepositCountChange,
  compact,
}: Props) {
  const isUnstake = mode === StakeMode.Unstake
  const [amount, setAmount] = useState('')

  const { open } = useAppKit()
  const { isConnected, address } = useAppKitAccount()
  const { connection } = useAppKitConnection()
  const requestWalletConnection = useCompliance((s) => s.requestWalletConnection)
  const nav = useNav((s) => s.nav)
  const fetchNav = useNav((s) => s.fetchNav)
  const { usdtelBalance: devUsdtelBalance, susdtelBalance } = useTokenBalances(
    address,
    connection ?? undefined,
    DEV_USDTEL_MINT,
    { includeUsdc: false },
  )
  const { usdtelBalance: mainnetUsdtelBalance } = useTokenBalances(
    address,
    connection ?? undefined,
    USDTEL_MINT,
    { includeUsdc: false, includeSusdtel: false },
  )
  const usdtelBalance = combineUsdtelBalances(devUsdtelBalance, mainnetUsdtelBalance)
  const stake = useVaultStake(amount, true, {
    quotePreviewAmountUi: '100',
    lockQuoteToPreviewAmount: true,
  })
  const unstake = useVaultUnstake(amount, isUnstake)

  const simulatedStakeRate = stake.quoteRate
  const simulatedUnstakeRate =
    simulatedStakeRate !== null && Number.isFinite(simulatedStakeRate) && simulatedStakeRate > 0
      ? 1 / simulatedStakeRate
      : null
  const numericAmount = Number(amount.replace(/,/g, '')) || 0
  const receiveAmountText = useMemo(() => {
    if (isUnstake) {
      if (numericAmount <= 0) {
        return '0.00'
      }
      if (simulatedUnstakeRate && simulatedUnstakeRate > 0) {
        return formatCalculatedAmount(numericAmount * simulatedUnstakeRate)
      }
      return '0.00'
    }

    if (numericAmount <= 0) {
      return '0.00'
    }
    if (simulatedStakeRate && simulatedStakeRate > 0) {
      return formatCalculatedAmount(numericAmount * simulatedStakeRate)
    }
    if (stake.quoteError) {
      return 'Unavailable'
    }
    return '—'
  }, [isUnstake, numericAmount, simulatedStakeRate, simulatedUnstakeRate, stake.quoteError])
  const receiveAmountNumeric = useMemo(() => {
    const parsed = Number(receiveAmountText.replace(/,/g, ''))
    return Number.isFinite(parsed) ? parsed : 0
  }, [receiveAmountText])

  const balanceFromRaw = isUnstake ? susdtelBalance ?? '0' : usdtelBalance ?? '0'
  const balanceToRaw = isUnstake ? usdtelBalance ?? '0' : susdtelBalance ?? '0'
  const balanceFrom = isConnected ? formatBalanceValue(balanceFromRaw) : '0'
  const balanceTo = isConnected ? formatBalanceValue(balanceToRaw) : '0'
  const availableBalance = Number(balanceFromRaw.replace(/,/g, '')) || 0

  const handleMax = () => {
    const max = isUnstake ? susdtelBalance : usdtelBalance
    if (max) setAmount(sanitizeNumeric(max))
  }

  const handleAmountChange = (next: string) => {
    setAmount(sanitizeNumeric(next))
  }

  const pendingDepositCount = stake.pendingDeposits?.length ?? 0
  const isSubmitting = stake.isSubmitting || unstake.isSubmitting

  useEffect(() => {
    onPendingDepositCountChange?.(pendingDepositCount)
  }, [pendingDepositCount, onPendingDepositCountChange])

  useEffect(() => {
    fetchNav()
  }, [fetchNav])

  const handleSubmit = async () => {
    if (!isConnected) {
      void requestWalletConnection(() => open())
      return
    }
    onTxStart?.({ stakeMode: mode, amountIn: numericAmount, amountOut: receiveAmountNumeric })
    try {
      const result = isUnstake
        ? await unstake.initiateUnstake?.()
        : await stake.stake?.()
      if (result === undefined) {
        // Hook caught an error and set its `error` state — surfaced via the
        // existing in-form banner. Tell parent to dismiss the overlay.
        onTxResult?.({ ok: false })
        return
      }
      onTxResult?.({ ok: true, signature: result.signature })
      setAmount('')
    } catch (err) {
      console.error('[MidnightStakeForm] submit failed', err)
      onTxResult?.({ ok: false })
    }
  }

  const ctaLabel = (() => {
    if (!isConnected) return 'Connect wallet'
    if (isSubmitting) return isUnstake ? 'Unstaking…' : 'Staking…'
    return isUnstake ? 'Unstake sUSD.tel' : 'Stake USD.tel'
  })()

  // Share price (USD.tel per sUSD.tel) — same resolver as the header sUSD.tel
  // chip so the label matches TopNav. Raw `nav.exchange_rate` can be wrong when
  // indexer share count is off (e.g. ~906 instead of ~$1).
  const navExchangeRate = useMemo(() => {
    if (!nav) return null
    const price = liveSharePrice(nav)
    return price > 0 ? price : null
  }, [nav])
  const navStakeRate = navExchangeRate ? 1 / navExchangeRate : null
  const exchangeRateText = isUnstake
    ? navExchangeRate
      ? `1 sUSD.tel = ${formatExchangeRate(navExchangeRate)} USD.tel`
      : ''
    : navStakeRate
      ? `1 USD.tel = ${formatExchangeRate(navStakeRate)} sUSD.tel`
      : '...'

  const minimumAmount = 10
  const minimumAmountError =
    amount.trim() && numericAmount > 0 && numericAmount < minimumAmount
      ? `Min amount is ${minimumAmount}.`
      : null
  const maximumAmountError =
    isConnected && amount.trim() && numericAmount > availableBalance
      ? 'Balance exceeded.'
      : null
  const inputValidationMessage = maximumAmountError || minimumAmountError

  const errorMessage = isUnstake
    ? unstake.quoteError || unstake.error
    : stake.error || unstake.error || stake.amountError || stake.quoteError

  // Sub-tabs (Stake/Unstake) are now rendered by the parent form panel so
  // the card height stays identical between Buy and Stake modes.
  void onModeChange

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <TokenInput
        label={isUnstake ? 'You unstake' : 'You stake'}
        value={amount}
        onChange={handleAmountChange}
        token={isUnstake ? 'sUSD.tel' : 'USD.tel'}
        balance={balanceFrom}
        showMax={isConnected}
        onMaxClick={handleMax}
        sub={fmtUsd(numericAmount * (isUnstake ? (simulatedUnstakeRate ?? 0) : 1))}
        invalid={!!inputValidationMessage}
        validationMessage={inputValidationMessage}
        compact={compact}
      />

      <SwitchArrow disabled compact={compact} />

      <div style={{ height: 6 }} />

      <TokenInput
        label='You receive'
        value={receiveAmountText}
        token={isUnstake ? 'USD.tel' : 'sUSD.tel'}
        balance={balanceTo}
        sub={fmtUsd(receiveAmountNumeric)}
        disabled
        compact={compact}
      />

      {/* Exchange rate */}
      <div
        style={{
          marginTop: 12,
          display: 'flex',
          justifyContent: 'space-between',
          padding: '10px 14px',
          background: 'rgba(255,255,255,0.015)',
          border: '1px solid var(--line)',
          borderRadius: 8,
        }}
      >
        <span
          style={{
            fontSize: 12,
            letterSpacing: '0.07em',
            color: 'var(--fg-2)',
            fontWeight: 500,
          }}
        >
          Exchange rate
        </span>
        <span
          className='tabular'
          style={{
            fontSize: 12,
            color: 'var(--fg)',
            fontWeight: 500,
          }}
        >
          {exchangeRateText}
        </span>
      </div>

      {/* Pending deposits notice — Stake mode only (Figma 6575-8989). */}
      {isConnected && !isUnstake && pendingDepositCount > 0 && (
        <div
          style={{
            marginTop: 8,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '12px 14px',
            background: 'rgba(243,162,74,0.05)',
            border: '1px solid rgba(243,162,74,0.18)',
            borderRadius: 8,
          }}
        >
          <span style={{ fontSize: 12, color: 'var(--fg-2)' }}>
            You have{' '}
            <span style={{ color: 'var(--dawn-amber)' }}>
              {pendingDepositCount} pending deposit{pendingDepositCount === 1 ? '' : 's'}
            </span>
          </span>
          <a href='/portfolio' className='link-arrow'>
            View in Portfolio →
          </a>
        </div>
      )}

      {/* Settlement notice — kept identical to MidnightBuyForm so the section
          does not shift when switching between the Buy and Stake tabs. */}
      <div
        style={{
          marginTop: 8,
          display: 'flex',
          gap: 9,
          padding: '9px 13px',
          color: 'var(--fg-3)',
          fontSize: 12,
          lineHeight: 1.5,
        }}
      >
        <span style={{ color: 'var(--dawn-amber)', fontSize: 13, lineHeight: '18px' }}>●</span>
        <span>
          Transactions typically settle within minutes. Larger transactions can take up to 30
          minutes to settle.
        </span>
      </div>

      {/* Error */}
      {errorMessage && (
        <div
          style={{
            padding: '10px 14px',
            borderRadius: 8,
            background: 'var(--neg-bg)',
            border: '1px solid var(--neg-line)',
            color: 'var(--neg)',
            fontSize: 12,
          }}
        >
          {errorMessage}
        </div>
      )}

      {/* CTA */}
      <GradientButton
        onClick={handleSubmit}
        disabled={isSubmitting || (isConnected && (numericAmount === 0 || !!inputValidationMessage))}
        fullWidth
        style={{ marginTop: 10, padding: '16px 18px', fontSize: 15 }}
      >
        {ctaLabel}
      </GradientButton>
    </div>
  )
}
