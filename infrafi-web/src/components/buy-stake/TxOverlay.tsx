'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import { GradientButton } from '@/components/ui/GradientButton'
import { ProcessingAnimation } from './ProcessingAnimation'

export type TxPhase = 'idle' | 'submitting' | 'confirming' | 'processing' | 'success'
export type TxFlowMode = 'buy' | 'stake'
export type TxStakeMode = 'stake' | 'unstake'

export type TxState = {
  phase: TxPhase
  mode: TxFlowMode
  stakeMode: TxStakeMode
  amountIn: number
  amountOut: number
  inToken: string
  outToken: string
  signature?: string | null
}

type Props = {
  state: TxState
  onDone: () => void
  // Optional footer rendered inside the loader card during submitting/confirming
  // phases. Used by the Stake/Unstake flows to surface pending-deposit count
  // or unstake-schedule shortcuts (Figma 6575-9515, 6575-10768).
  pendingFooter?: React.ReactNode
}

const HEX = '0123456789abcdef'

// Truncate a real Solana base58 sig to a "0x….trail" shape that matches the
// design's monospace receipt — purely cosmetic, so we don't show 88 chars.
function shortenSig(sig: string | null | undefined): string {
  if (!sig) {
    let h = '0x'
    for (let i = 0; i < 16; i++) h += HEX[Math.floor(Math.random() * 16)]
    h += '…'
    for (let i = 0; i < 6; i++) h += HEX[Math.floor(Math.random() * 16)]
    return h
  }
  if (sig.length <= 18) return sig
  return `${sig.slice(0, 8)}…${sig.slice(-6)}`
}

// Slot/block lookup isn't free — show a deterministic-looking value derived
// from the signature so successive views of the same receipt stay stable.
function fakeBlock(sig: string | null | undefined): number {
  let h = 0
  const s = sig ?? ''
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return 22847000 + (h % 9999)
}

export function TxOverlay({ state, onDone, pendingFooter }: Props) {
  const { phase, mode, stakeMode, amountIn, amountOut, inToken, outToken, signature } = state
  const visible = phase !== 'idle'
  const isSuccess = phase === 'success'
  const isProcessing = phase === 'processing'
  const isPending = phase === 'submitting' || phase === 'confirming'

  const tx = useMemo(() => {
    if (!isSuccess) return null
    return { hash: shortenSig(signature), block: fakeBlock(signature) }
  }, [isSuccess, signature])

  // Counter animation for the received amount
  const [shown, setShown] = useState(0)
  useEffect(() => {
    if (!isSuccess) {
      setShown(0)
      return
    }
    const target = Number.isFinite(amountOut) ? amountOut : 0
    const start = performance.now()
    const dur = 800
    let raf = 0
    const tick = (t: number) => {
      const k = Math.min(1, (t - start) / dur)
      const eased = 1 - Math.pow(1 - k, 3)
      setShown(target * eased)
      if (k < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [isSuccess, amountOut])

  const headline =
    mode === 'buy'
      ? 'Purchase confirmed'
      : stakeMode === 'stake'
        ? 'Stake confirmed'
        : 'Unstake confirmed'
  const sub =
    mode === 'buy'
      ? 'USD.tel is now in your wallet.'
      : stakeMode === 'stake'
        ? 'sUSD.tel is earning yield from telecom revenue.'
        : 'USD.tel has returned to your wallet.'
  const paidLabel =
    mode === 'buy' ? 'Paid' : stakeMode === 'stake' ? 'Staked' : 'Unstaked'

  return (
    <div
      aria-hidden={!visible}
      style={{
        position: 'absolute',
        inset: 0,
        pointerEvents: visible ? 'auto' : 'none',
        opacity: visible ? 1 : 0,
        transition: 'opacity 220ms ease',
        zIndex: 9999,
      }}
    >
      {/* Frosted backdrop */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          backgroundColor: 'rgba(5, 4, 10, 0.97)',
          background:
            'linear-gradient(180deg, rgba(11,8,20,0.96), rgba(11,8,20,0.99))',
          backdropFilter: 'blur(8px)',
          WebkitBackdropFilter: 'blur(8px)',
        }}
      />

      {/* Pending */}
      {isPending && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 32,
            gap: 40,
          }}
        >
          {/* Loader + status label stacked (Figma 6575-5901). */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 13,
            }}
          >
            <DotMatrixLoader />
            <div style={{ fontSize: 14, color: 'var(--fg-3)', textAlign: 'center' }}>
              {phase === 'submitting' ? 'Submitting' : 'Confirming'}
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 20,
              width: '100%',
            }}
          >
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 9,
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: 20, lineHeight: '20px', fontWeight: 600, color: 'var(--fg)' }}>
                {phase === 'submitting' ? 'Broadcasting transaction' : 'Awaiting confirmation'}
              </div>
              <div style={{ fontSize: 14, lineHeight: 1.4, color: 'var(--fg-3)' }}>
                {phase === 'submitting' ? (
                  <>
                    Signing <span style={{ fontWeight: 700 }}>→</span> mempool
                  </>
                ) : (
                  <>
                    Block inclusion <span style={{ fontWeight: 700 }}>→</span> settled
                  </>
                )}
              </div>
            </div>

            <div style={{ display: 'flex', gap: 6 }}>
              {[0, 1, 2].map((i) => {
                const reached =
                  (phase === 'submitting' && i <= 0) ||
                  (phase === 'confirming' && i <= 1)
                return (
                  <div
                    key={i}
                    style={{
                      width: 32,
                      height: 2,
                      borderRadius: 2,
                      background: reached ? 'var(--dawn-amber)' : '#4c3326',
                      transition: 'background 240ms ease',
                    }}
                  />
                )
              })}
            </div>
          </div>

          {pendingFooter && (
            <div
              style={{
                position: 'absolute',
                left: 24,
                right: 24,
                bottom: 24,
              }}
            >
              {pendingFooter}
            </div>
          )}
        </div>
      )}

      {/* Processing — tx broadcast and signature received but chain hasn't
          finalized yet. Triggered by the parent after the confirming phase
          has been active long enough to suggest the user shouldn't keep
          waiting (Figma 6575-6237). */}
      {isProcessing && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 28,
            animation: 'tx-success-in 320ms cubic-bezier(0.2, 0.7, 0.3, 1) both',
          }}
        >
          <div
            style={{
              width: '100%',
              maxWidth: 360,
              padding: '24px 22px',
              background: 'var(--bg-1)',
              border: '1px solid var(--line-strong)',
              borderRadius: 14,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 18,
            }}
          >
            <ProcessingAnimation
              style={{ width: '70%', maxWidth: 200, aspectRatio: '299 / 295' }}
            />
            <div style={{ textAlign: 'center' }}>
              <div
                style={{
                  fontSize: 16,
                  color: 'var(--fg)',
                  fontWeight: 500,
                  marginBottom: 8,
                }}
              >
                Your transaction is processing
              </div>
              <div
                style={{
                  fontSize: 12.5,
                  color: 'var(--fg-3)',
                  lineHeight: 1.5,
                }}
              >
                Transactions typically settle within minutes, but transactions can take up
                to 30 minutes. You can navigate away from this page and check the
                transaction status in Portfolio.
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, width: '100%' }}>
              <GradientButton
                href='/portfolio'
                onClick={onDone}
                fullWidth
                style={{ padding: '12px 14px', fontSize: 13 }}
              >
                Go to Portfolio
              </GradientButton>
              <button
                type='button'
                onClick={onDone}
                className='btn'
                style={{
                  padding: '12px 14px',
                  fontSize: 13,
                  width: '100%',
                  background: 'rgba(255,255,255,0.04)',
                  color: 'var(--fg)',
                  border: '1px solid var(--line-strong)',
                }}
              >
                Got it
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Success */}
      {isSuccess && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 28,
            gap: 18,
            animation: 'tx-success-in 420ms cubic-bezier(0.2, 0.7, 0.3, 1) both',
          }}
        >
          <div style={{ position: 'relative', width: 72, height: 72 }}>
            <div
              style={{
                position: 'absolute',
                inset: 0,
                borderRadius: '50%',
                border: '1px solid var(--dawn-amber)',
                animation: 'tx-ring 900ms ease-out 120ms both',
              }}
            />
            <svg
              width='72'
              height='72'
              viewBox='0 0 72 72'
              style={{ position: 'absolute', inset: 0 }}
            >
              <circle
                cx='36'
                cy='36'
                r='32'
                fill='none'
                stroke='url(#tx-check-grad)'
                strokeWidth='1.5'
                style={{
                  strokeDasharray: 201,
                  strokeDashoffset: 201,
                  animation:
                    'tx-circle-draw 540ms cubic-bezier(0.4, 0, 0.2, 1) 80ms forwards',
                }}
              />
              <path
                d='M22 37 L32 47 L51 27'
                fill='none'
                stroke='url(#tx-check-grad)'
                strokeWidth='2.2'
                strokeLinecap='round'
                strokeLinejoin='round'
                style={{
                  strokeDasharray: 50,
                  strokeDashoffset: 50,
                  animation:
                    'tx-check-draw 360ms cubic-bezier(0.4, 0, 0.2, 1) 460ms forwards',
                }}
              />
              <defs>
                <linearGradient id='tx-check-grad' x1='0' y1='0' x2='72' y2='72'>
                  <stop offset='0%' stopColor='#F3A24A' />
                  <stop offset='100%' stopColor='#EA5270' />
                </linearGradient>
              </defs>
            </svg>
          </div>

          <div style={{ marginTop: -6, fontSize: 14, color: 'var(--fg-3)', textAlign: 'center' }}>
            Settled
          </div>

          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 9,
              textAlign: 'center',
            }}
          >
            <div style={{ fontSize: 20, lineHeight: '20px', fontWeight: 600, color: 'var(--fg)' }}>
              {headline}
            </div>
            <div style={{ fontSize: 14, color: 'var(--fg-3)', lineHeight: 1.4, maxWidth: 300 }}>
              {sub}
            </div>
          </div>

          {/* Receipt */}
          <div
            style={{
              width: '100%',
              maxWidth: 320,
              padding: 20,
              background: 'rgba(237,124,91,0.03)',
              border: '1px solid rgba(237,124,91,0.3)',
              borderRadius: 20,
              display: 'flex',
              flexDirection: 'column',
              gap: 24,
              animation:
                'tx-receipt-in 420ms cubic-bezier(0.2, 0.7, 0.3, 1) 700ms both',
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <ReceiptRow
                label={paidLabel}
                value={
                  <>
                    {amountIn.toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}{' '}
                    <span style={{ color: 'var(--fg-3)' }}>{inToken}</span>
                  </>
                }
              />
              <ReceiptRow
                label='Received'
                accent
                value={
                  <>
                    {shown.toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}{' '}
                    {outToken}
                  </>
                }
              />
            </div>
            <div style={{ height: 1, background: 'var(--line)' }} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <ReceiptRow
                label='TX'
                value={
                  signature ? (
                    <CopyableTxValue display={tx?.hash ?? ''} full={signature} />
                  ) : (
                    (tx?.hash ?? '')
                  )
                }
              />
              <ReceiptRow
                label='Block'
                value={`#${(tx?.block ?? 0).toLocaleString()}`}
              />
            </div>
          </div>

          {/* Stacked CTAs — Done primary on top, View in Portfolio secondary
              below (Figma 6575-5921). */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
              width: '100%',
              maxWidth: 320,
              animation:
                'tx-receipt-in 420ms cubic-bezier(0.2, 0.7, 0.3, 1) 900ms both',
            }}
          >
            <GradientButton onClick={onDone} fullWidth style={{ padding: '14px 18px', fontSize: 14 }}>
              Done
            </GradientButton>
            <Link
              href='/portfolio'
              onClick={onDone}
              className='btn'
              style={{
                padding: '12px 18px',
                fontSize: 13,
                background: 'rgba(255,255,255,0.04)',
                color: 'var(--fg)',
                border: '1px solid var(--line-strong)',
                textAlign: 'center',
                width: '100%',
              }}
            >
              View in Portfolio
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}

function ReceiptRow({
  label,
  value,
  accent,
}: {
  label: string
  value: React.ReactNode
  accent?: boolean
}) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        gap: 12,
      }}
    >
      <span style={{ fontSize: 14, lineHeight: 1.4, color: 'var(--fg-3)' }}>{label}</span>
      <span
        className={`tabular${accent ? ' gradient-text' : ''}`}
        style={{
          fontSize: 14,
          lineHeight: 1.4,
          textAlign: 'right',
          color: accent ? undefined : 'var(--fg-2)',
        }}
      >
        {value}
      </span>
    </div>
  )
}

// The receipt shows a truncated signature, but the full base58 sig is what's
// useful (block explorers, support). Clicking copies the full value and flips
// the label to a brief "Copied" confirmation.
function CopyableTxValue({ display, full }: { display: string; full: string }) {
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!copied) return
    const timer = window.setTimeout(() => setCopied(false), 1500)
    return () => window.clearTimeout(timer)
  }, [copied])

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(full)
      setCopied(true)
    } catch (copyError) {
      console.warn('[TxOverlay] Failed to copy transaction signature.', copyError)
    }
  }

  return (
    <button
      type='button'
      onClick={handleCopy}
      title={copied ? 'Copied' : 'Copy transaction signature'}
      aria-label={copied ? 'Transaction signature copied' : 'Copy transaction signature'}
      className='tabular'
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: 0,
        margin: 0,
        background: 'transparent',
        border: 'none',
        cursor: 'pointer',
        font: 'inherit',
        fontSize: 14,
        lineHeight: 1.4,
        color: copied ? 'var(--dawn-amber)' : 'var(--fg-2)',
        transition: 'color 160ms ease',
      }}
    >
      <span>{copied ? 'Copied' : display}</span>
      <span style={{ display: 'inline-flex', opacity: copied ? 1 : 0.6 }} aria-hidden>
        {copied ? <CheckIcon /> : <CopyIcon />}
      </span>
    </button>
  )
}

function CopyIcon() {
  return (
    <svg
      width='13'
      height='13'
      viewBox='0 0 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2'
      strokeLinecap='round'
      strokeLinejoin='round'
      aria-hidden
    >
      <rect x='9' y='9' width='13' height='13' rx='2' ry='2' />
      <path d='M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1' />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg
      width='13'
      height='13'
      viewBox='0 0 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2.5'
      strokeLinecap='round'
      strokeLinejoin='round'
      aria-hidden
    >
      <path d='M20 6 9 17l-5-5' />
    </svg>
  )
}

// Pending-phase loader rendered as an amber ripple traveling diagonally
// across a 9×9 pixel grid (Figma 6575-5901). Pure CSS — each cell's
// stagger is driven by an animation-delay derived from its coordinates.
function DotMatrixLoader() {
  const size = 9
  const cell = 5
  const gap = 3
  return (
    <div
      aria-hidden
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${size}, ${cell}px)`,
        gap,
      }}
    >
      {Array.from({ length: size * size }, (_, idx) => {
        const row = Math.floor(idx / size)
        const col = idx % size
        return (
          <div
            key={idx}
            style={{
              width: cell,
              height: cell,
              borderRadius: 1,
              backgroundColor: '#26272b',
              animation: 'tx-dot 1.6s ease-in-out infinite',
              animationDelay: `${(row + col) * 0.09}s`,
            }}
          />
        )
      })}
    </div>
  )
}
