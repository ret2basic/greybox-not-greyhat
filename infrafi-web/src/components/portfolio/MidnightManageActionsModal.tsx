'use client'

import { useState, type FC, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import Image from 'next/image'
import usdtelIcon from '@/assets/tokens/USD.tel_token_icon/USD.tel_token_icon.svg'
import susdtelIcon from '@/assets/tokens/sUSD.tel_token_icon/sUSD.tel_token_icon.svg'

type MidnightManageActionsModalProps = {
  isOpen: boolean
  assetLabel?: string
  assetValue?: string
  onClose: () => void
  onStake: () => void
  onUnstake: () => void
  onBoost: () => void
  onWithdrawSelect: () => void
}

type Option = {
  id: 'stake' | 'unstake' | 'boost' | 'withdraw'
  title: string
  desc: string
  accent: string
  glow: string
  glowEllipse: string
  icon: ReactNode
  onSelect: () => void
}

export const MidnightManageActionsModal: FC<MidnightManageActionsModalProps> = ({
  isOpen,
  assetLabel,
  assetValue,
  onClose,
  onStake,
  onUnstake,
  onBoost,
  onWithdrawSelect,
}) => {
  const [hovered, setHovered] = useState<Option['id'] | null>(null)
  if (!isOpen || typeof document === 'undefined') return null

  const label = assetLabel ?? 'USD.tel'
  const isSusd = label.toLowerCase().includes('susd')
  const icon = isSusd ? susdtelIcon : usdtelIcon

  const stakeOption: Option = {
    id: 'stake',
    title: 'Stake',
    desc: 'Add more USD.tel to this position and earn additional yield and season points.',
    accent: '#F3A24A',
    glow: 'rgba(243,162,74,0.5)',
    glowEllipse: 'radial-gradient(60% 90% at 100% 0%, rgba(243,162,74,0.22) 0%, rgba(243,162,74,0) 70%)',
    onSelect: onStake,
    icon: (
      <svg width='17' height='17' viewBox='0 0 15.0002 8.00035' fill='none'>
        <path d='M14.5002 4.8748V0.5H10.1254' stroke='currentColor' strokeWidth='1' strokeLinecap='round' strokeLinejoin='round' />
        <path
          d='M14.4994 0.500662L10.1246 4.87546C9.35198 5.64806 8.96612 6.03391 8.49277 6.07679C8.41402 6.08379 8.33527 6.08379 8.25653 6.07679C7.78317 6.03304 7.39731 5.64806 6.62472 4.87546C5.85213 4.10287 5.46628 3.71702 4.99292 3.67414C4.91434 3.66704 4.83527 3.66704 4.75668 3.67414C4.28333 3.71789 3.89747 4.10287 3.12488 4.87546L0.5 7.50035'
          stroke='currentColor'
          strokeWidth='1'
          strokeLinecap='round'
          strokeLinejoin='round'
        />
      </svg>
    ),
  }

  const unstakeOption: Option = {
    id: 'unstake',
    title: 'Unstake',
    desc: 'Convert sUSD.tel back to USD.tel. A cooldown may apply before funds are claimable.',
    accent: '#E84066',
    glow: 'rgba(232,64,102,0.5)',
    glowEllipse: 'radial-gradient(60% 90% at 100% 0%, rgba(232,64,102,0.2) 0%, rgba(232,64,102,0) 70%)',
    onSelect: onUnstake,
    icon: (
      <svg width='17' height='17' viewBox='0 0 15.0002 8.00035' fill='none' style={{ transform: 'rotate(180deg)' }}>
        <path d='M14.5002 4.8748V0.5H10.1254' stroke='currentColor' strokeWidth='1' strokeLinecap='round' strokeLinejoin='round' />
        <path
          d='M14.4994 0.500662L10.1246 4.87546C9.35198 5.64806 8.96612 6.03391 8.49277 6.07679C8.41402 6.08379 8.33527 6.08379 8.25653 6.07679C7.78317 6.03304 7.39731 5.64806 6.62472 4.87546C5.85213 4.10287 5.46628 3.71702 4.99292 3.67414C4.91434 3.66704 4.83527 3.66704 4.75668 3.67414C4.28333 3.71789 3.89747 4.10287 3.12488 4.87546L0.5 7.50035'
          stroke='currentColor'
          strokeWidth='1'
          strokeLinecap='round'
          strokeLinejoin='round'
        />
      </svg>
    ),
  }

  const restOptions: Option[] = [
    {
      id: 'boost',
      title: 'Boost',
      desc: 'Amplify your yield with leverage. Higher potential returns at increased risk.',
      accent: '#ED7C5B',
      glow: 'rgba(237,124,91,0.5)',
      glowEllipse: 'radial-gradient(60% 90% at 100% 0%, rgba(237,124,91,0.2) 0%, rgba(237,124,91,0) 70%)',
      onSelect: onBoost,
      icon: (
        <svg width='16' height='16' viewBox='0 0 16 16' fill='none'>
          <path
            d='M5.80673 15.9602C5.70441 15.917 5.61938 15.841 5.56506 15.7441C5.51073 15.6472 5.49021 15.535 5.50673 15.4252L6.41673 9.50018H4.00173C3.92517 9.50224 3.84915 9.48668 3.77956 9.45471C3.70996 9.42274 3.64864 9.3752 3.60032 9.31577C3.55201 9.25635 3.51799 9.18661 3.50089 9.11196C3.4838 9.0373 3.48409 8.95971 3.50173 8.88518L5.00173 2.38518C5.02812 2.27331 5.09225 2.17396 5.18332 2.10384C5.27439 2.03371 5.38683 1.99711 5.50173 2.00018H10.5017C10.5764 1.99992 10.6502 2.01641 10.7177 2.04842C10.7852 2.08044 10.8447 2.12717 10.8917 2.18518C10.9395 2.24384 10.9732 2.31257 10.9906 2.38619C11.0079 2.4598 11.0083 2.53639 10.9917 2.61018L10.1267 6.50018H12.5017C12.5954 6.49999 12.6873 6.52614 12.7669 6.57565C12.8464 6.62516 12.9105 6.69603 12.9517 6.78018C12.9876 6.86095 13.0013 6.94977 12.9917 7.0376C12.982 7.12543 12.9493 7.20913 12.8967 7.28018L6.39673 15.7802C6.3528 15.8453 6.29414 15.8992 6.22552 15.9374C6.15689 15.9756 6.08022 15.9971 6.00173 16.0002C5.93484 15.9988 5.86875 15.9853 5.80673 15.9602ZM8.87673 7.50018L9.87673 3.00018H5.90173L4.63173 8.50018H7.58673L6.79173 13.6402L11.5017 7.50018H8.87673Z'
            fill='currentColor'
          />
        </svg>
      ),
    },
    {
      id: 'withdraw',
      title: 'Withdraw',
      desc: 'Remove liquidity from this protocol and return capital to your wallet.',
      accent: '#E84066',
      glow: 'rgba(232,64,102,0.5)',
      glowEllipse: 'radial-gradient(60% 90% at 100% 0%, rgba(232,64,102,0.2) 0%, rgba(232,64,102,0) 70%)',
      onSelect: onWithdrawSelect,
      icon: (
        <svg width='16' height='16' viewBox='0 0 12.7011 11.9007' fill='none'>
          <path
            d='M10.4387 7.13913L10.0434 4.90987C9.87227 3.94678 9.78672 3.46524 9.44863 3.18047C9.11055 2.8957 8.62437 2.89509 7.65261 2.89509H5.04118C4.06941 2.89509 3.58383 2.89509 3.24516 3.18047C2.90707 3.46524 2.82152 3.94678 2.65041 4.90987L2.2551 7.13913C1.90109 9.13802 1.72349 10.1378 2.26926 10.7935C2.81503 11.4504 3.82397 11.4504 5.84066 11.4504H6.85313C8.86982 11.4504 9.87876 11.4504 10.4245 10.7941C10.9703 10.1378 10.7933 9.13802 10.4387 7.13974V7.13913Z'
            stroke='currentColor'
            strokeWidth='0.9'
            strokeLinecap='round'
          />
          <path
            d='M6.3476 5.03368V9.00579M4.87255 7.7836L6.3476 9.31133L7.82265 7.7836'
            stroke='currentColor'
            strokeWidth='0.9'
            strokeLinecap='round'
            strokeLinejoin='round'
          />
          <path
            d='M11.6607 5.33909C11.7519 5.29199 11.8346 5.22894 11.905 5.15271C12.2508 4.78239 12.2508 4.18413 12.2508 2.98761C12.2508 1.79109 12.2508 1.19344 11.905 0.821895C11.5593 0.45035 11.0035 0.45035 9.89068 0.45035H2.81043C1.69765 0.45035 1.14185 0.45035 0.796101 0.821895C0.450349 1.19344 0.450349 1.7917 0.450349 2.98761C0.450349 4.18352 0.450349 4.78178 0.796101 5.15271C0.866904 5.2293 0.948327 5.29143 1.04037 5.33909'
            stroke='currentColor'
            strokeWidth='0.9'
            strokeLinecap='round'
          />
        </svg>
      ),
    },
  ]

  const [boostOption, withdrawOption] = restOptions
  // sUSD.tel is already staked, so it offers Unstake + Boost. USD.tel (and any
  // other idle asset) keeps the Stake / Boost / Withdraw set.
  const options: Option[] = isSusd
    ? [unstakeOption, boostOption]
    : [stakeOption, boostOption, withdrawOption]

  return createPortal(
    <div
      className='fixed inset-0 z-90 flex items-center justify-center px-4'
      style={{ background: 'rgba(7,8,11,0.82)', backdropFilter: 'blur(6px)', WebkitBackdropFilter: 'blur(6px)' }}
      onClick={onClose}
    >
      <div
        role='dialog'
        aria-modal='true'
        aria-label='Manage position'
        onClick={(event) => event.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: 480,
          borderRadius: 20,
          border: '1px solid var(--line-strong)',
          background: 'var(--bg-2)',
          padding: 24,
          boxShadow: '0 24px 90px -24px rgba(0,0,0,0.8)',
        }}
      >
        {/* header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
          <div>
            <h3 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 20, fontWeight: 600, color: 'var(--fg)' }}>
              What would you like to do
            </h3>
            <p style={{ margin: '6px 0 0', fontSize: 13, color: 'var(--fg-3)' }}>
              Choose how you&apos;d like to manage this position
            </p>
          </div>
          <button
            type='button'
            onClick={onClose}
            aria-label='Close manage actions'
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 28,
              height: 28,
              borderRadius: 8,
              border: '1px solid var(--line)',
              background: 'transparent',
              color: 'var(--fg-3)',
              cursor: 'pointer',
              fontSize: 15,
              lineHeight: 1,
              flexShrink: 0,
            }}
          >
            ×
          </button>
        </div>

        {/* position summary */}
        <div
          style={{
            marginTop: 20,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            padding: '14px 16px',
            borderRadius: 15,
            border: '1px solid rgba(243,162,74,0.3)',
            background: 'rgba(243,162,74,0.03)',
          }}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 12 }}>
            <span style={{ display: 'inline-flex', width: 28, height: 28, borderRadius: 7, overflow: 'hidden', border: '1px solid var(--line)' }}>
              <Image src={icon} alt='' width={28} height={28} style={{ objectFit: 'cover', width: '100%', height: '100%' }} />
            </span>
            <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg)' }}>{label}</span>
          </span>
          {assetValue && (
            <span
              className='tabular'
              style={{
                fontSize: 14,
                fontWeight: 600,
                fontFamily: 'var(--font-display)',
                backgroundImage: 'linear-gradient(90deg, var(--dawn-amber) 0%, var(--dawn-rose) 100%)',
                WebkitBackgroundClip: 'text',
                backgroundClip: 'text',
                color: 'transparent',
              }}
            >
              {assetValue}
            </span>
          )}
        </div>

        {/* options */}
        <div style={{ marginTop: 14, display: 'grid', gap: 10 }}>
          {options.map((opt) => {
            const isHover = hovered === opt.id
            return (
              <button
                key={opt.id}
                type='button'
                onClick={opt.onSelect}
                onMouseEnter={() => setHovered(opt.id)}
                onMouseLeave={() => setHovered(null)}
                style={{
                  position: 'relative',
                  overflow: 'hidden',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 16,
                  width: '100%',
                  textAlign: 'left',
                  padding: 20,
                  borderRadius: 20,
                  border: `1px solid ${isHover ? opt.glow : 'var(--line-strong)'}`,
                  background: 'var(--bg-2)',
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  boxShadow: isHover ? `0 12px 40px -16px ${opt.glow}` : 'none',
                  transition: 'border-color 160ms ease, box-shadow 200ms ease',
                }}
              >
                <span
                  aria-hidden
                  style={{
                    position: 'absolute',
                    inset: 0,
                    backgroundImage: opt.glowEllipse,
                    opacity: isHover ? 1 : 0.7,
                    transition: 'opacity 200ms ease',
                    pointerEvents: 'none',
                  }}
                />
                <span
                  style={{
                    position: 'relative',
                    display: 'inline-flex',
                    width: 30,
                    height: 30,
                    borderRadius: 8,
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    color: opt.accent,
                    background: 'var(--bg-1)',
                    border: '1px solid var(--line-strong)',
                  }}
                >
                  {opt.icon}
                </span>
                <span style={{ position: 'relative', flex: 1, minWidth: 0 }}>
                  <span style={{ display: 'block', fontSize: 14, fontWeight: 600, color: 'var(--fg)' }}>{opt.title}</span>
                  <span style={{ display: 'block', fontSize: 12, color: 'var(--fg-3)', marginTop: 5, lineHeight: 1.4 }}>{opt.desc}</span>
                </span>
                <svg width='8' height='12' viewBox='0 0 8 12' fill='none' style={{ position: 'relative', flexShrink: 0, color: 'var(--fg-3)' }} aria-hidden>
                  <path d='M1.5 1.5L6 6L1.5 10.5' stroke='currentColor' strokeWidth='1.5' strokeLinecap='round' strokeLinejoin='round' />
                </svg>
              </button>
            )
          })}
        </div>
      </div>
    </div>,
    document.body,
  )
}
