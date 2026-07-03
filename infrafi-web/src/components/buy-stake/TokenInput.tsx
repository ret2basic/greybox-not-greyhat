'use client'

import type { ReactNode } from 'react'
import SolMark from '@/assets/chains/SOL'
import { UsdcCoin, UsdTelCoin } from '@/components/ui/primitives'

export type MidnightTokenId = 'USDC' | 'USD.tel' | 'sUSD.tel'

type Props = {
  label: string
  value: string
  onChange?: (value: string) => void
  token: MidnightTokenId
  balance: string
  onMaxClick?: () => void
  showMax?: boolean
  sub?: ReactNode
  disabled?: boolean
  invalid?: boolean
  validationMessage?: ReactNode
  // Mobile-only sizing pass (Figma 6605-6124). Tightens padding, radius,
  // and type scale so the card matches the phone layout 1:1. Desktop leaves
  // this off, so its dimensions are unchanged.
  compact?: boolean
}

function TokenPill({ token, compact }: { token: MidnightTokenId; compact?: boolean }) {
  const iconSize = compact ? 18 : 20
  const Icon =
    token === 'USDC' ? (
      <UsdcCoin size={iconSize} />
    ) : (
      <UsdTelCoin size={iconSize} sub={token === 'sUSD.tel'} />
    )
  return (
    <span
      style={{
        display: 'inline-flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
        gap: compact ? 3 : 4,
      }}
    >
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: compact ? 6 : 8,
          padding: compact ? '6px 11px' : '8px 12px',
          background: 'var(--bg-3)',
          borderRadius: 999,
          border: '1px solid var(--line)',
        }}
      >
        {Icon}
        <span style={{ fontWeight: 500, fontSize: compact ? 13 : 14 }}>{token}</span>
      </span>
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: compact ? 4 : 5,
          fontWeight: 500,
          fontSize: compact ? 11 : 12,
          color: 'var(--fg)',
          paddingRight: compact ? 11 : 12,
        }}
      >
        <SolMark size={compact ? 13 : 14} />
        Solana
      </span>
    </span>
  )
}

export function TokenInput({
  label,
  value,
  onChange,
  token,
  balance,
  onMaxClick,
  showMax,
  sub,
  disabled,
  invalid,
  validationMessage,
  compact,
}: Props) {
  return (
    <div style={{ position: 'relative' }}>
      <div
        style={{
          padding: compact ? '15px 16px' : '20px 22px',
          background: 'var(--bg-1)',
          border: `1px solid ${invalid ? 'var(--neg-line)' : 'var(--line)'}`,
          borderRadius: compact ? 12 : 14,
          transition: 'border-color 180ms, box-shadow 180ms',
          boxShadow: invalid ? '0 0 0 1px color-mix(in srgb, var(--neg-line) 50%, transparent)' : 'none',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginBottom: compact ? 11 : 14,
            alignItems: 'center',
          }}
        >
        <span
          style={{
            textTransform: 'capitalize',
            fontSize: 12,
            letterSpacing: '0.07em',
            color: 'var(--fg-2)',
            fontWeight: 400,
          }}
        >
          {label}
        </span>
        <span
          style={{
            fontSize: 12,
            color: 'var(--fg-3)',
          }}
        >
          Balance:{' '}
          <span
            className='tabular'
            style={{ color: 'var(--fg)', fontWeight: 500 }}
          >
            {balance}
          </span>
        </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: compact ? 10 : 14 }}>
          <input
            type='text'
            inputMode='decimal'
            value={value}
            disabled={disabled}
            placeholder='0'
            onChange={(e) => onChange?.(e.target.value)}
            style={{
              flex: 1,
              minWidth: 0,
              background: 'none',
              border: 'none',
              outline: 'none',
              fontFamily: 'var(--font-display)',
              fontWeight: 500,
              fontSize: compact ? 32 : 36,
              color: 'var(--fg)',
              letterSpacing: '-0.025em',
            }}
          />
          {showMax && (
            <button
              type='button'
              onClick={onMaxClick}
              style={{
                padding: '5px 10px',
                background: 'rgba(243,162,74,0.12)',
                border: '1px solid rgba(243,162,74,0.28)',
                borderRadius: 6,
                color: 'var(--dawn-amber)',
                fontFamily: 'var(--font-mono)',
                fontSize: 10,
                letterSpacing: '0.14em',
              }}
            >
              MAX
            </button>
          )}
          <TokenPill token={token} compact={compact} />
        </div>
        <div
          className='tabular'
          style={{
            marginTop: 8,
            fontSize: compact ? 14 : 13,
            color: 'var(--fg-2)',
            fontWeight: 500,
          }}
        >
          {sub}
        </div>
      </div>

      {invalid && validationMessage && (
        <div
          role='alert'
          aria-live='polite'
          style={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            left: 0,
            zIndex: 20,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '6px 10px',
            borderRadius: 8,
            background: 'var(--neg-bg)',
            border: '1px solid var(--neg-line)',
            color: 'var(--neg)',
            fontSize: 12,
            lineHeight: 1.35,
          }}
        >
          <span>{validationMessage}</span>
        </div>
      )}
    </div>
  )
}

type SwitchProps = { onClick?: () => void; disabled?: boolean; compact?: boolean }
export function SwitchArrow({ onClick, disabled, compact }: SwitchProps) {
  const dim = compact ? 30 : 36
  return (
    <div
      style={{
        position: 'relative',
        height: 0,
        display: 'flex',
        justifyContent: 'center',
        zIndex: 30,
      }}
    >
      <button
        type='button'
        onClick={onClick}
        disabled={disabled}
        aria-label='Switch direction'
        style={{
          position: 'absolute',
          top: compact ? -10 : -12,
          zIndex: 31,
          width: dim,
          height: dim,
          borderRadius: compact ? 7 : 8,
          background: 'var(--bg-3)',
          border: '1px solid var(--line-strong)',
          color: 'var(--fg-2)',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 14,
        }}
      >
        ↓
      </button>
    </div>
  )
}
