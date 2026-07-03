'use client'

import { type FC } from 'react'
import { createPortal } from 'react-dom'
import { GradientButton } from '@/components/ui/GradientButton'
import { WithdrawAnimation } from '@/components/portfolio/WithdrawAnimation'

type MidnightWithdrawConfirmModalProps = {
  isOpen: boolean
  isWithdrawDisabled: boolean
  isWithdrawing: boolean
  withdrawAmount: string
  maxWithdrawAmount: string
  withdrawAmountError?: string | null
  onClose: () => void
  onWithdrawAmountChange: (value: string) => void
  onMaxAmount: () => void
  onContinue: (amount: string) => void
}

export const MidnightWithdrawConfirmModal: FC<MidnightWithdrawConfirmModalProps> = ({
  isOpen,
  isWithdrawDisabled,
  isWithdrawing,
  withdrawAmount,
  maxWithdrawAmount,
  withdrawAmountError,
  onClose,
  onWithdrawAmountChange,
  onMaxAmount,
  onContinue,
}) => {
  if (!isOpen || typeof document === 'undefined') return null

  return createPortal(
    <div
      className='fixed inset-0 z-90 flex items-center justify-center px-4'
      style={{ background: 'rgba(7,8,11,0.82)', backdropFilter: 'blur(6px)', WebkitBackdropFilter: 'blur(6px)' }}
      onClick={onClose}
    >
      <div
        role='dialog'
        aria-modal='true'
        aria-label='Confirm withdrawal'
        onClick={(event) => event.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: 460,
          borderRadius: 18,
          border: '1px solid var(--line-strong)',
          background: 'var(--bg-2)',
          padding: 28,
          boxShadow: '0 24px 90px -24px rgba(0,0,0,0.8)',
          textAlign: 'center',
        }}
      >
        {/* illustration */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 4 }}>
          <WithdrawAnimation />
        </div>

        <h3 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 600, color: 'var(--fg)' }}>
          Confirm withdrawal
        </h3>
        <p style={{ margin: '8px auto 0', maxWidth: 360, fontSize: 13, lineHeight: 1.5, color: 'var(--fg-3)' }}>
          You&apos;re about to start the withdrawal process for this position.
        </p>

        {/* amount */}
        <div style={{ marginTop: 22, textAlign: 'left' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span className='kicker' style={{ fontSize: 10 }}>Amount (USD.tel)</span>
            <button
              type='button'
              onClick={onMaxAmount}
              className='btn btn-ghost btn-sm'
              style={{ padding: '2px 10px', fontSize: 11, borderColor: 'var(--line)' }}
            >
              Max
            </button>
          </div>
          <input
            value={withdrawAmount}
            onChange={(event) => onWithdrawAmountChange(event.target.value)}
            inputMode='decimal'
            placeholder='0.00'
            aria-label='Withdraw amount'
            style={{
              width: '100%',
              padding: '14px 16px',
              borderRadius: 12,
              border: `1px solid ${withdrawAmountError ? 'var(--neg-line)' : 'var(--line)'}`,
              background: 'var(--bg-1)',
              color: 'var(--fg)',
              fontSize: 15,
              outline: 'none',
            }}
          />
          <div style={{ marginTop: 6, fontSize: 11, color: withdrawAmountError ? 'var(--neg)' : 'var(--fg-3)' }}>
            {withdrawAmountError || `Available: ${maxWithdrawAmount || '0'} USD.tel`}
          </div>
        </div>

        {/* actions */}
        <div style={{ marginTop: 22, display: 'grid', gap: 10 }}>
          <GradientButton
            onClick={() => onContinue(withdrawAmount)}
            disabled={isWithdrawDisabled || isWithdrawing}
            fullWidth
            style={{ padding: '14px', fontSize: 14 }}
          >
            {isWithdrawing ? 'Withdrawing…' : 'Continue to withdraw'}
          </GradientButton>
          <button type='button' onClick={onClose} className='btn btn-ghost' style={{ width: '100%', padding: '14px', fontSize: 14 }}>
            Cancel
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
