'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { MidnightBuyForm } from '@/components/buy-stake/MidnightBuyForm'
import { MidnightStakeForm } from '@/components/buy-stake/MidnightStakeForm'
import { TxOverlay, type TxState } from '@/components/buy-stake/TxOverlay'
import { SegmentedToggle } from '@/components/ui/SegmentedToggle'
import { useBuyStakePage, BuyStakeTab } from '@/hooks/buy-stake/useBuyStakePage'
import { BuyMode, StakeMode } from '@/hooks/buy-stake/types'

const IDLE_TX: TxState = {
  phase: 'idle',
  mode: 'stake',
  stakeMode: 'stake',
  amountIn: 0,
  amountOut: 0,
  inToken: '',
  outToken: '',
  signature: null,
}

export default function BuyStakePageContent() {
  const [isSmallScreen, setIsSmallScreen] = useState(false)
  const { activeTab, buyMode, buyStakeTabs, setActiveTab, setStakeMode, stakeMode } =
    useBuyStakePage()

  useEffect(() => {
    const media = window.matchMedia('(max-width: 1024px)')
    const sync = () => setIsSmallScreen(media.matches)
    sync()
    media.addEventListener('change', sync)
    return () => media.removeEventListener('change', sync)
  }, [])

  // Tx overlay state — drives submit/confirm/success animation that sits on
  // top of the form panel. Lifted to this level so the overlay covers the
  // entire card-strong (including ModeTabs), not just the form internals.
  const [tx, setTx] = useState<TxState>(IDLE_TX)
  const [stakePendingCount, setStakePendingCount] = useState(0)
  const submittingTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Flips the overlay to `processing` if the tx has not finalized within this
  // many ms of submission. The tx is still in flight — this is a UI affordance
  // to let users navigate away (Figma 6575-6512). Transactions that settle
  // inside this window go straight to the success receipt (Figma 6575-6196).
  const processingTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const PROCESSING_AFTER_MS = 5000

  const clearTimers = () => {
    if (submittingTimer.current) {
      clearTimeout(submittingTimer.current)
      submittingTimer.current = null
    }
    if (processingTimer.current) {
      clearTimeout(processingTimer.current)
      processingTimer.current = null
    }
  }

  const dismiss = () => {
    clearTimers()
    setTx(IDLE_TX)
  }

  const beginTx = (info: {
    mode: 'buy' | 'stake'
    stakeMode: 'stake' | 'unstake'
    amountIn: number
    amountOut: number
    inToken: string
    outToken: string
  }) => {
    setTx({ phase: 'submitting', signature: null, ...info })
    clearTimers()
    submittingTimer.current = setTimeout(() => {
      setTx((s) => (s.phase === 'submitting' ? { ...s, phase: 'confirming' } : s))
    }, 900)
    // If the tx is still pending after the threshold, surface the processing
    // screen so the user can navigate away. finishTx clears this timer when
    // the tx settles first.
    processingTimer.current = setTimeout(() => {
      setTx((s) =>
        s.phase === 'submitting' || s.phase === 'confirming'
          ? { ...s, phase: 'processing' }
          : s,
      )
    }, PROCESSING_AFTER_MS)
  }

  const finishTx = (result: { ok: boolean; signature?: string | null }) => {
    clearTimers()
    if (!result.ok) {
      setTx(IDLE_TX)
      return
    }
    setTx((s) => ({ ...s, phase: 'success', signature: result.signature ?? null }))
  }

  const handleStakeTxStart = (info: {
    stakeMode: StakeMode
    amountIn: number
    amountOut: number
  }) => {
    const isUnstake = info.stakeMode === StakeMode.Unstake
    beginTx({
      mode: 'stake',
      stakeMode: isUnstake ? 'unstake' : 'stake',
      amountIn: info.amountIn,
      amountOut: info.amountOut,
      inToken: isUnstake ? 'sUSD.tel' : 'USD.tel',
      outToken: isUnstake ? 'USD.tel' : 'sUSD.tel',
    })
  }

  const handleBuyTxStart = (info: { amountIn: number; amountOut: number }) => {
    const isWithdraw = buyMode === BuyMode.Withdraw
    beginTx({
      mode: 'buy',
      stakeMode: 'stake',
      amountIn: info.amountIn,
      amountOut: info.amountOut,
      inToken: isWithdraw ? 'USD.tel' : 'USDC',
      outToken: isWithdraw ? 'USDC' : 'USD.tel',
    })
  }

  return (
    <div
      data-screen-label='01 Buy & Stake'
      className='fade-up'
      // 30px bottom gap so the container never butts up against the footer.
      style={{ position: 'relative', paddingBottom: 30 }}
    >
      {/* Hero — centered headline above the form card (Figma 6540-32890). */}
      <div
        className='app-container'
        style={{
          padding: isSmallScreen ? '28px 16px 0' : '40px 32px 0',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          position: 'relative',
          zIndex: 1,
        }}
      >
        <h1
          className='h-display'
          style={{
            fontSize: isSmallScreen ? 28 : 48,
            margin: 0,
            marginBottom: isSmallScreen ? 18 : 24,
            lineHeight: isSmallScreen ? 1.18 : 1.05,
            letterSpacing: isSmallScreen ? '-0.035em' : '-0.025em',
            textAlign: 'center',
            maxWidth: isSmallScreen ? 300 : undefined,
            color: 'var(--fg)',
          }}
        >
          Broadband-backed <span className='gradient-text'>onchain&nbsp;yield.</span>
        </h1>

        {/* Form panel — centered, fixed max width */}
        <div
          className='card-strong'
          style={{
            padding: 0,
            overflow: 'hidden',
            position: 'relative',
            width: '100%',
            maxWidth: 520,
            borderRadius: isSmallScreen ? 20 : undefined,
          }}
        >
            {/* Segmented control — active tab is a filled gradient pill, other
                tabs are plain labels, Bridge carries a "Soon" badge
                (Figma 6575-5093). */}
            <div
              style={{
                padding: isSmallScreen ? '20px 20px 0' : '20px 24px 0',
                display: 'flex',
                justifyContent: 'center',
              }}
            >
              <SegmentedToggle
                value={activeTab}
                onChange={setActiveTab}
                options={buyStakeTabs.map((t) => {
                  const disabled = 'isDisabled' in t && t.isDisabled
                  return {
                    value: t.id,
                    label: t.label,
                    disabled,
                    badge: disabled ? (
                      <span
                        style={{
                          padding: '2px 6px',
                          background: 'var(--bg-2)',
                          border: '0.5px solid var(--line-strong)',
                          borderRadius: 4,
                          fontSize: 8,
                          fontWeight: 400,
                          color: 'var(--fg-3)',
                        }}
                      >
                        Soon
                      </span>
                    ) : undefined,
                  }
                })}
              />
            </div>

            <div style={{ padding: isSmallScreen ? '14px 20px 4px' : '14px 24px 4px' }}>
              <div
                style={{
                  fontSize: 14,
                  color: 'var(--fg-2)',
                  lineHeight: 1.5,
                  textAlign: 'center',
                }}
              >
                {activeTab === BuyStakeTab.Buy &&
                  (buyMode === BuyMode.Withdraw
                    ? 'Swap USD.tel back to USDC via M0 orchestration.'
                    : 'Purchase USD.tel and earn yield from telecom infrastructure.')}
                {activeTab === BuyStakeTab.Stake &&
                  (stakeMode === StakeMode.Unstake
                    ? 'Unstake sUSD.tel to receive USD.tel at current NAV. 28 day lockup per deposit.'
                    : 'Stake USD.tel to earn yield from telecom subscriber revenue.')}
              </div>
            </div>

            {/* Stake/Unstake sub-tabs always rendered with opacity-controlled
                visibility, so the form card height stays identical when the
                user toggles between Buy and Stake modes. */}
            <div
              style={{
                // Collapse to zero height in Buy mode so the form sits right
                // under the description — no dead space (the red-box gap). The
                // sub-tabs expand back in only when Stake is the active tab.
                paddingLeft: isSmallScreen ? 20 : 24,
                paddingRight: isSmallScreen ? 20 : 24,
                paddingTop: activeTab === BuyStakeTab.Stake ? 12 : 0,
                maxHeight: activeTab === BuyStakeTab.Stake ? 60 : 0,
                overflow: 'hidden',
                transition: 'max-height 220ms ease, padding-top 220ms ease',
              }}
              aria-hidden={activeTab !== BuyStakeTab.Stake}
            >
              <div
                className='tabs'
                style={{
                  width: '100%',
                  opacity: activeTab === BuyStakeTab.Stake ? 1 : 0,
                  pointerEvents:
                    activeTab === BuyStakeTab.Stake ? 'auto' : 'none',
                  transition: 'opacity 220ms ease',
                }}
              >
                <button
                  type='button'
                  className={`tab ${stakeMode === StakeMode.Stake ? 'active' : ''}`}
                  style={{ flex: 1 }}
                  onClick={() => setStakeMode(StakeMode.Stake)}
                  tabIndex={activeTab === BuyStakeTab.Stake ? 0 : -1}
                >
                  Stake
                </button>
                <button
                  type='button'
                  className={`tab ${stakeMode === StakeMode.Unstake ? 'active' : ''}`}
                  style={{ flex: 1 }}
                  onClick={() => setStakeMode(StakeMode.Unstake)}
                  tabIndex={activeTab === BuyStakeTab.Stake ? 0 : -1}
                >
                  Unstake
                </button>
              </div>
            </div>

            <div style={{ padding: isSmallScreen ? '12px 20px 20px' : '12px 24px 24px' }}>
              {activeTab === BuyStakeTab.Buy ? (
                <MidnightBuyForm
                  mode={buyMode}
                  onTxStart={handleBuyTxStart}
                  onTxResult={finishTx}
                  compact={isSmallScreen}
                />
              ) : (
                <MidnightStakeForm
                  mode={stakeMode}
                  onModeChange={setStakeMode}
                  onTxStart={handleStakeTxStart}
                  onTxResult={finishTx}
                  onPendingDepositCountChange={setStakePendingCount}
                  compact={isSmallScreen}
                />
              )}
            </div>
            <TxOverlay
              state={tx}
              onDone={dismiss}
              pendingFooter={
                tx.mode === 'stake' &&
                tx.stakeMode === 'stake' &&
                stakePendingCount > 0 ? (
                  <OverlayPendingDepositFooter count={stakePendingCount} />
                ) : null
              }
            />
        </div>
      </div>

    </div>
  )
}

// In-overlay footer surfaced during the Stake submitting/confirming phases
// (Figma 6575-9515, 6575-9800). Hidden when no pending deposits exist —
// no mock data ever rendered.
function OverlayPendingDepositFooter({ count }: { count: number }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
        padding: '10px 14px',
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid var(--line)',
        borderRadius: 8,
        fontSize: 12,
        color: 'var(--fg-3)',
      }}
    >
      <span>
        You have{' '}
        <span style={{ color: 'var(--dawn-amber)' }}>
          {count} pending deposit{count === 1 ? '' : 's'}
        </span>
      </span>
      <Link href='/portfolio' className='link-arrow' style={{ fontSize: 12 }}>
        View in Portfolio →
      </Link>
    </div>
  )
}
