'use client'

import { BuyMode } from '@/hooks/buy-stake/types'
import { useBuyForm } from '@/hooks/buy-stake/useBuyForm'
import { GradientButton } from '@/components/ui/GradientButton'
import { TokenInput, SwitchArrow } from './TokenInput'

type Props = {
  mode: BuyMode
  onTxStart?: (info: { amountIn: number; amountOut: number }) => void
  onTxResult?: (result: { ok: boolean; signature?: string | null }) => void
  // Mobile sizing pass — forwarded to the token inputs / switch (Figma 6605-6124).
  compact?: boolean
}

export function MidnightBuyForm({ mode, onTxStart, onTxResult, compact }: Props) {
  const {
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
    isSwapping,
    isQuoteLoading,
    payDollarValue,
    quoteError,
    receiveDollarValue,
    swapError,
  } = useBuyForm(mode)

  const isWithdraw = mode === BuyMode.Withdraw
  const fromToken = isWithdraw ? 'USD.tel' : 'USDC'
  const toToken = isWithdraw ? 'USDC' : 'USD.tel'
  const numericFromAmount = Number(fromAmount.replace(/,/g, '')) || 0
  const availableFromBalance = Number(displayFromBalance.replace(/,/g, '')) || 0
  const isUsdcBuyInput = !isWithdraw
  const balanceExceededError =
    isConnected && isUsdcBuyInput && fromAmount.trim() && numericFromAmount > availableFromBalance
      ? 'Balance exceeded.'
      : null

  const onCta = async () => {
    if (!isConnected) {
      handleConnectWallet()
      return
    }
    const numericIn = numericFromAmount
    const numericOut = Number(displayReceiveAmount.replace(/,/g, '')) || 0
    onTxStart?.({ amountIn: numericIn, amountOut: numericOut })
    const result = await handleBuy()
    if (!result) {
      onTxResult?.({ ok: false })
      return
    }
    onTxResult?.({ ok: true, signature: result.signatures[0] ?? null })
  }

  const errorMessage = quoteError || swapError

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <TokenInput
        label='You pay'
        value={fromAmount}
        onChange={handleAmountChange}
        token={fromToken}
        balance={displayFromBalance}
        showMax={isConnected}
        onMaxClick={handleMaxClick}
        sub={payDollarValue}
        invalid={!!balanceExceededError}
        validationMessage={balanceExceededError}
        compact={compact}
      />

      <SwitchArrow disabled compact={compact} />

      <div style={{ height: 6 }} />

      <TokenInput
        label='You receive'
        value={displayReceiveAmount}
        token={toToken}
        balance={displayToBalance}
        sub={receiveDollarValue}
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
          1 {fromToken} = 1 {toToken}
        </span>
      </div>

      {/* Settlement notice (Figma 6575-5093). */}
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
          Transactions typically settle within minutes. Larger transactions can take up to
          30 minutes to settle.
        </span>
      </div>

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

      <GradientButton
        onClick={onCta}
        disabled={isConnected && (!canSubmit || !!balanceExceededError)}
        fullWidth
        style={{ marginTop: 10, padding: '16px 18px', fontSize: 15 }}
      >
        {isSwapping ? 'Swapping…' : isQuoteLoading ? 'Fetching quote…' : buttonLabel}
      </GradientButton>
    </div>
  )
}
