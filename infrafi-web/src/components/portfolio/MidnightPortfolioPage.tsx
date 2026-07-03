'use client'

import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import Image, { type StaticImageData } from 'next/image'
import { useRouter } from 'next/navigation'
import { useAppKit, useAppKitAccount } from '@reown/appkit/react'
import { usePortfolioBalances } from '@/hooks/portfolio/usePortfolioBalances'
import { useWalletSectionData } from '@/hooks/portfolio/useWalletSectionData'
import { usePortfolioPoints } from '@/hooks/portfolio/usePortfolioPoints'
import { useVaultUnstake } from '@/hooks/useVaultUnstake'
import { usePartnerPositions } from '@/hooks/boost/usePartnerPositions'
import {
  LENDING_ROWS,
  LIQUIDITY_ROWS,
  LOOPING_ROWS,
  PROTOCOL_ICONS,
  YIELD_TRADING_ROWS,
} from '@/components/boost/data'
import { formatClaimableDate, getDaysUntil } from '@/components/portfolio/formatters'
import { useCompliance } from '@/store'
import { useNav, liveSharePrice } from '@/store'
import { SegmentedToggle } from '@/components/ui/SegmentedToggle'
import { GradientButton } from '@/components/ui/GradientButton'
import { MidnightManageActionsModal } from './MidnightManageActionsModal'
import { MidnightWithdrawConfirmModal } from './MidnightWithdrawConfirmModal'
import SolanaChainIcon from '@/assets/chains/SOLANA'
import BaseChainIcon from '@/assets/chains/BASE'
import usdtelIcon from '@/assets/tokens/USD.tel_token_icon/USD.tel_token_icon.svg'
import susdtelIcon from '@/assets/tokens/sUSD.tel_token_icon/sUSD.tel_token_icon.svg'
import usdcIcon from '@/assets/tokens/usdc.svg'
import goldIcon from '@/assets/icons/portfolio/leaderboard/gold.svg'
import silverIcon from '@/assets/icons/portfolio/leaderboard/silver.svg'
import bronzeIcon from '@/assets/icons/portfolio/leaderboard/bronze.svg'

// ============================================================
// Portfolio — "Your portfolio" detail view
// ============================================================
//
// Layout (per Figma 6447-24170):
//   ┌─ Centered hero (title + subtitle) ───────────────────┐
//   ├─ Total-position card (headline number + yield pill) ─┤
//   ├─ KPI cards: Yield · APY · Efficiency · Season ───────┤
//   └─ Portfolio detail panel ─────────────────────────────┤
//        ├ Position | Leaderboard toggle
//        ├ Position table  /  Leaderboard table
//        └ Footer strip (totals + Explore Boost Strategies)
//
// Real wallet/pending/staked data is computed from the hooks below.
// LP/Lend rows remain illustrative mock until cross-protocol APIs land.

// ----- Strategy groups (drive totals + strategy count) ------------

type GroupId = 'idle' | 'stel' | 'lp' | 'lend' | 'ytrade'
type Cta = {
  route: 'amplify' | 'buy-stake'
  amplifyTab?: 'lp' | 'lend' | 'yieldTrading'
  buyStakeMode?: 'buy' | 'stake'
}
type Group = {
  id: GroupId
  label: string
  swatch: string
  defaultRoute: Cta
}

const PF_GROUPS: Group[] = [
  { id: 'idle', label: 'Idle USD.tel', swatch: '#7A6B9A', defaultRoute: { route: 'buy-stake', buyStakeMode: 'stake' } },
  { id: 'stel', label: 'sUSD.tel', swatch: '#F3A24A', defaultRoute: { route: 'buy-stake', buyStakeMode: 'stake' } },
  { id: 'lp', label: "LP'ing", swatch: '#7ED9A8', defaultRoute: { route: 'amplify', amplifyTab: 'lp' } },
  { id: 'lend', label: 'Borrow & Lending', swatch: '#9B7BFF', defaultRoute: { route: 'amplify', amplifyTab: 'lend' } },
  { id: 'ytrade', label: 'Yield Trading', swatch: '#EA5270', defaultRoute: { route: 'amplify', amplifyTab: 'yieldTrading' } },
]

// Descriptor lookup for cross-protocol (Boost) positions, keyed by the same
// strategy id the partner fetchers emit (see `@/lib/partners`). Lets the
// portfolio render a live partner position — e.g. an Orca LP — as a real row
// in its strategy group with the right label, protocol icon and CTA.
type StrategyDescriptor = { pair: string; protocol: string; group: GroupId; depositUrl?: string }
const STRATEGY_DESCRIPTORS: Record<string, StrategyDescriptor> = {
  ...Object.fromEntries(LIQUIDITY_ROWS.map((r) => [r.id, { pair: r.pair, protocol: r.protocol, group: 'lp' as GroupId, depositUrl: r.depositUrl }])),
  ...Object.fromEntries(LENDING_ROWS.map((r) => [r.id, { pair: r.asset, protocol: r.protocol, group: 'lend' as GroupId, depositUrl: r.depositUrl }])),
  ...Object.fromEntries(LOOPING_ROWS.map((r) => [r.id, { pair: r.pool, protocol: r.protocol, group: 'lend' as GroupId, depositUrl: r.depositUrl }])),
  ...Object.fromEntries(YIELD_TRADING_ROWS.map((r) => [r.id, { pair: r.asset, protocol: r.protocol, group: 'ytrade' as GroupId, depositUrl: r.depositUrl }])),
}

type StatusTone = 'green' | 'blue' | 'amber' | 'gray'
type RowKind = 'idle' | 'pending' | 'deployed'
type RowAction = 'manage' | 'claims' | 'amplify'
type Row = {
  kind: RowKind
  group: GroupId
  id: string
  asset: string
  sub?: string
  chainBadge?: 'solana' | 'base'
  status: string
  statusTone: StatusTone
  balance: string
  balanceSub?: string
  usd: string
  apy: string | null
  action: RowAction
  actionLabel: string
  img: StaticImageData
  // Optional per-row CTA override. When absent, 'amplify' rows fall back to
  // their strategy group's default route.
  cta?: Cta
  // External deposit/position page (e.g. the Orca pool). When set, the row's
  // action opens it in a new tab — same target as the Boost "Manage" button.
  externalUrl?: string
}

// Idle USD.tel, pending deposits and the staked sUSD.tel row are all computed
// at runtime from useWalletSectionData (see component below). LP'ing and
// Borrow & Lending rows are intentionally omitted until cross-protocol APIs
// land — no illustrative/mock positions are shown.

const usdNum = (s: string) => Number(String(s).replace(/[^0-9.]/g, '')) || 0
const numFromBalance = (s: string) => Number(String(s).replace(/[^0-9.]/g, '')) || 0
// Parse an APY string like "11.4%" or "8.70%" into a number. Returns 0 when
// the row has no APY (null/"–") so idle and processing positions naturally
// drag the portfolio-wide weighted APY toward zero.
const parseApyPct = (s: string | null) => {
  if (!s) return 0
  const n = Number(String(s).replace(/[^0-9.-]/g, ''))
  return Number.isFinite(n) ? n : 0
}
const sanitizeWithdrawInput = (value: string) => {
  const cleaned = value.replace(/[^0-9.]/g, '')
  if (!cleaned) return ''
  if (cleaned === '.') return '0.'
  const [whole = '', ...rest] = cleaned.split('.')
  const normalizedWhole = whole.replace(/^0+(?=\d)/, '') || '0'
  const decimal = rest.join('').slice(0, 6)
  return rest.length ? `${normalizedWhole}.${decimal}` : normalizedWhole
}
function computeGroupTotals(rows: Row[]) {
  return PF_GROUPS.map((g) => ({
    ...g,
    value: rows.filter((r) => r.group === g.id).reduce((s, r) => s + usdNum(r.usd), 0),
  }))
}
const formatWallet = (wallet: string) =>
  wallet.length <= 10 ? wallet : `${wallet.slice(0, 4)}...${wallet.slice(-4)}`

// Mobile groups positions into status sections (Figma 6634-12486):
// Available · Deployed · Processing · Locked — each with a count + sum.
type PfSectionId = 'available' | 'deployed' | 'processing' | 'locked'
const PF_SECTION_ORDER: { id: PfSectionId; label: string }[] = [
  { id: 'available', label: 'Available' },
  { id: 'deployed', label: 'Deployed' },
  { id: 'processing', label: 'Processing' },
  { id: 'locked', label: 'Locked' },
]
function sectionForRow(r: Row): PfSectionId {
  const s = r.status.toLowerCase()
  if (s === 'locked') return 'locked'
  if (s === 'deployed') return 'deployed'
  if (s.includes('mint') || s === 'processing') return 'processing'
  return 'available'
}

// Signed USD: keeps the +/- prefix and the dollar sign in the right order
// (e.g. -$19,544.73 instead of the confusing +$-19544.73).
const fmtSignedUsd = (value: number) => `${value < 0 ? '-' : '+'}$${Math.abs(value).toFixed(2)}`

// ----- Cross-screen navigation ------------------------------------

type RouterLike = ReturnType<typeof useRouter>
function applyCta(router: RouterLike, cta: Cta) {
  if (cta.route === 'amplify') {
    router.push('/boost')
    return
  }
  if (cta.buyStakeMode === 'stake') {
    router.push('/buy-stake?tab=stake&mode=stake')
  } else {
    router.push('/buy-stake?tab=buy')
  }
}

// ----- Visual primitives ------------------------------------------

const STATUS_TONES: Record<StatusTone, { fg: string; bg: string; line: string }> = {
  green: { fg: '#7ED9A8', bg: 'rgba(126,217,168,0.10)', line: 'rgba(126,217,168,0.28)' },
  blue: { fg: '#7E93FF', bg: 'rgba(126,147,255,0.10)', line: 'rgba(126,147,255,0.28)' },
  amber: { fg: '#F3A24A', bg: 'rgba(243,162,74,0.10)', line: 'rgba(243,162,74,0.28)' },
  gray: { fg: 'var(--fg-3)', bg: 'rgba(255,255,255,0.03)', line: 'var(--line)' },
}

function StatusPill({ label, tone }: { label: string; tone: StatusTone }) {
  const t = STATUS_TONES[tone]
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '4px 11px',
        borderRadius: 999,
        fontSize: 11,
        fontWeight: 500,
        color: t.fg,
        background: t.bg,
        border: `1px solid ${t.line}`,
        whiteSpace: 'nowrap',
      }}
    >
      {tone !== 'gray' && (
        <span style={{ width: 5, height: 5, borderRadius: '50%', background: t.fg }} />
      )}
      {label}
    </span>
  )
}

function ChainBadge({ kind }: { kind: 'solana' | 'base' }) {
  const name = kind === 'solana' ? 'Solana' : 'Base'
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        padding: '2px 7px 2px 4px',
        borderRadius: 999,
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid var(--line)',
      }}
    >
      <span style={{ display: 'inline-flex', width: 12, height: 12, borderRadius: '50%', overflow: 'hidden' }}>
        <span style={{ transform: 'scale(0.5)', transformOrigin: 'top left', width: 24, height: 24, display: 'block' }}>
          {kind === 'solana' ? <SolanaChainIcon /> : <BaseChainIcon />}
        </span>
      </span>
      <span style={{ fontSize: 10, color: 'var(--fg-3)', letterSpacing: '0.02em' }}>{name}</span>
    </span>
  )
}

function TokenIcon({ src, size = 34 }: { src: StaticImageData; size?: number }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        width: size,
        height: size,
        borderRadius: '50%',
        overflow: 'hidden',
        flexShrink: 0,
        border: '1px solid var(--line)',
        background: 'var(--bg-2)',
      }}
    >
      <Image src={src} alt='' width={size} height={size} style={{ objectFit: 'cover', width: '100%', height: '100%' }} />
    </span>
  )
}

function ActionButton({ label, onClick, accent }: { label: string; onClick: () => void; accent?: boolean }) {
  return (
    <button
      type='button'
      onClick={(e) => {
        e.stopPropagation()
        onClick()
      }}
      style={{
        padding: '9px 22px',
        borderRadius: 999,
        fontSize: 13,
        fontWeight: 500,
        fontFamily: 'inherit',
        color: accent ? 'var(--dawn-amber)' : 'var(--fg)',
        background: 'rgba(255,255,255,0.03)',
        border: `1px solid ${accent ? 'rgba(243,162,74,0.4)' : 'var(--line-strong)'}`,
        cursor: 'pointer',
        transition: 'background 160ms ease, border-color 160ms ease',
        whiteSpace: 'nowrap',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'rgba(255,255,255,0.07)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'rgba(255,255,255,0.03)'
      }}
    >
      {label}
    </button>
  )
}

// Amber count pill shown next to an asset name when it has in-flight vault
// activity (pending stakes and/or unstakes). Matches Figma 6696-9914.
function PendingBadge({ count }: { count: number }) {
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 600,
        padding: '2px 7px',
        borderRadius: 5,
        background: 'rgba(243,162,74,0.14)',
        color: 'var(--dawn-amber)',
        border: '1px solid rgba(243,162,74,0.3)',
      }}
    >
      {count} Pending
    </span>
  )
}

function ExpandChevron({ open }: { open: boolean }) {
  return (
    <svg
      width='10'
      height='10'
      viewBox='0 0 10 6'
      fill='none'
      aria-hidden
      style={{
        transform: open ? 'rotate(180deg)' : 'none',
        transition: 'transform 0.15s ease',
        color: 'var(--fg-3)',
      }}
    >
      <path d='M1 1 L5 5 L9 1' stroke='currentColor' strokeWidth='1.5' strokeLinecap='round' strokeLinejoin='round' />
    </svg>
  )
}

type UnstakeItem = {
  index: number
  sharesLabel: string
  assetsLabel: string
  // Unix seconds when the withdrawal becomes executable. Readiness (Claim vs
  // Cancel) is derived from this against the current time at render, so the row
  // flips Cancel → Claim without needing the position data to refetch.
  readyAtSec: number
  claimableDate: string
}

// Renders the list of a user's pending unstake (transferable withdrawal)
// positions. Executable withdrawals expose a Claim action that settles the
// shares into USD.tel; pending ones can be cancelled before the wait elapses.
function PendingUnstakeList({
  items,
  isSubmitting,
  onClaim,
  onCancel,
}: {
  items: UnstakeItem[]
  isSubmitting: boolean
  onClaim: (index: number) => void
  onCancel: (index: number) => void
}) {
  if (items.length === 0) {
    return <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>No pending unstakes.</div>
  }
  // Derived live from each item's ready timestamp against "now" at render time,
  // so a withdrawal flips Cancel → Claim the moment its wait elapses.
  const nowSec = Math.floor(Date.now() / 1000)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {items.map((item) => {
        const isExecutable = nowSec >= item.readyAtSec
        const daysLeft = getDaysUntil(item.readyAtSec, nowSec)
        return (
        <div
          key={item.index}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 16,
            padding: '12px 16px',
            background: 'var(--bg-1)',
            border: '1px solid var(--line)',
            borderRadius: 10,
          }}
        >
          <span style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
            <span className='mono' style={{ fontSize: 12, color: 'var(--fg-3)' }}>Withdrawal #{item.index + 1}</span>
            <span style={{ fontSize: 11, color: 'var(--fg-4)' }}>
              {item.sharesLabel} sUSD.tel{isExecutable ? '' : ` · ready ${item.claimableDate}`}
            </span>
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 14 }}>
            <span
              className='tabular'
              style={{ fontSize: 13, color: 'var(--dawn-amber)', fontFamily: 'var(--font-display)', whiteSpace: 'nowrap' }}
            >
              ~{item.assetsLabel} USD.tel
            </span>
            {isExecutable ? (
              <button
                type='button'
                onClick={(e) => {
                  e.stopPropagation()
                  onClaim(item.index)
                }}
                disabled={isSubmitting}
                className='btn btn-ghost btn-sm'
                style={{
                  borderColor: 'rgba(243,162,74,0.5)',
                  color: 'var(--dawn-amber)',
                  background: 'rgba(243,162,74,0.08)',
                  opacity: isSubmitting ? 0.5 : 1,
                }}
              >
                Claim
              </button>
            ) : (
              <button
                type='button'
                onClick={(e) => {
                  e.stopPropagation()
                  onCancel(item.index)
                }}
                disabled={isSubmitting}
                className='btn btn-ghost btn-sm'
                style={{ borderColor: 'rgba(243,162,74,0.5)', color: 'var(--dawn-amber)', opacity: isSubmitting ? 0.5 : 1, fontSize: 11, whiteSpace: 'nowrap' }}
              >
                Cancel ({daysLeft}d)
              </button>
            )}
          </span>
        </div>
        )
      })}
    </div>
  )
}

type DepositClaim = {
  index: number
  amount: string
  asset: string
  actionKind: 'claim' | 'cancel'
  isDisabled: boolean
  claimableAtTimestamp: number
}

// Renders a user's in-flight stakes (deposits settling into sUSD.tel). Once the
// delivery wait elapses the stake exposes an active Claim action that mints the
// sUSD.tel into the wallet; while still settling it shows a disabled "Claim (Nd)"
// with the countdown — mirroring the pending-unstake row. Readiness/countdown are
// derived live from the claimable timestamp at render. (Cancelling a pending
// stake is intentionally not offered — the vault's withdraw-from-custody path
// reverts for unsettled deposits, so it would only fail.)
function ProcessingStakeList({
  stakes,
  onClaim,
}: {
  stakes: DepositClaim[]
  onClaim: (index: number) => void
}) {
  if (stakes.length === 0) {
    return <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>No pending stakes.</div>
  }
  const nowSec = Math.floor(Date.now() / 1000)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {stakes.map((stake) => {
        const claimable = nowSec >= stake.claimableAtTimestamp
        const daysLeft = getDaysUntil(stake.claimableAtTimestamp, nowSec)
        return (
          <div
            key={stake.index}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 16,
              padding: '12px 16px',
              background: 'var(--bg-1)',
              border: '1px solid var(--line)',
              borderRadius: 10,
            }}
          >
            <span className='mono' style={{ fontSize: 12, color: 'var(--fg-3)' }}>Stake #{stake.index + 1}</span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 18 }}>
              <span className='tabular' style={{ fontSize: 13, color: 'var(--dawn-amber)', fontFamily: 'var(--font-display)' }}>
                {stake.amount} sUSD.tel
              </span>
              <button
                type='button'
                onClick={(e) => {
                  e.stopPropagation()
                  if (claimable) onClaim(stake.index)
                }}
                disabled={!claimable || stake.isDisabled}
                className='btn btn-ghost btn-sm'
                style={{
                  borderColor: 'rgba(243,162,74,0.5)',
                  color: 'var(--dawn-amber)',
                  background: claimable ? 'rgba(243,162,74,0.08)' : 'transparent',
                  opacity: claimable && !stake.isDisabled ? 1 : 0.5,
                  cursor: claimable && !stake.isDisabled ? 'pointer' : 'not-allowed',
                  whiteSpace: 'nowrap',
                }}
              >
                {claimable ? 'Claim' : `Claim (${daysLeft}d)`}
              </button>
            </span>
          </div>
        )
      })}
    </div>
  )
}

function PfSparkline({ color, points }: { color: string; points: number[] }) {
  const w = 200
  const h = 36
  const pathStr = points.map((y, i) => `${(i / (points.length - 1)) * w},${h - y}`).join(' L')
  const fillPath = `M0,${h} L${pathStr} L${w},${h} Z`
  const linePath = `M${pathStr}`
  const id = `pf-sp-${color.replace(/[^a-z0-9]/gi, '')}`
  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 36 }} preserveAspectRatio='none'>
      <defs>
        <linearGradient id={id} x1='0' y1='0' x2='0' y2='1'>
          <stop offset='0%' stopColor={color} stopOpacity='0.35' />
          <stop offset='100%' stopColor={color} stopOpacity='0' />
        </linearGradient>
      </defs>
      <path d={fillPath} fill={`url(#${id})`} />
      <path d={linePath} fill='none' stroke={color} strokeWidth='1.5' />
    </svg>
  )
}

function KpiCard({ title, children, style }: { title?: ReactNode; children: ReactNode; style?: CSSProperties }) {
  return (
    <div
      className='glow-card'
      style={{
        padding: '20px 22px',
        borderRadius: 16,
        background: 'var(--bg-2)',
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0,
        minHeight: 156,
        ...style,
      }}
    >
      {title != null && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 14, flexWrap: 'wrap', minWidth: 0 }}>
          {typeof title === 'string' ? <span style={{ fontSize: 13, color: 'var(--fg-3)' }}>{title}</span> : title}
        </div>
      )}
      {children}
    </div>
  )
}

const cardPanel: CSSProperties = {
  borderRadius: 16,
  border: '1px solid var(--line)',
  background: 'var(--bg-2)',
}

// Format a season window as "Jan 15 - Apr 15, 2026".
function fmtSeasonRange(start: string | null, end: string | null): string {
  if (!start || !end) return ''
  const s = new Date(start)
  const e = new Date(end)
  if (Number.isNaN(s.getTime()) || Number.isNaN(e.getTime())) return ''
  const from = s.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  const to = e.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  return `${from} - ${to}`
}

// Season picker — matches Figma 6447-26489. Only the current season has data
// today, so earlier seasons render disabled until the backend serves them.
function SeasonSelector({ current }: { current: number }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDocClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [open])

  const seasons = Array.from({ length: current + 1 }, (_, i) => i)

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        type='button'
        onClick={() => setOpen((o) => !o)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 8,
          padding: 0,
          border: 'none',
          background: 'none',
          cursor: 'pointer',
          color: 'var(--dawn-amber)',
          fontSize: 14,
          fontWeight: 600,
          fontFamily: 'var(--font-display)',
        }}
      >
        <svg width='14' height='14' viewBox='0 0 36 36' fill='none' aria-hidden>
          <path d='M18 4 L22 14 L33 15 L25 23 L27 34 L18 28 L9 34 L11 23 L3 15 L14 14 Z' fill='currentColor' />
        </svg>
        Season {current}
        <svg
          width='9'
          height='9'
          viewBox='0 0 10 6'
          fill='none'
          aria-hidden
          style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s ease' }}
        >
          <path d='M1 1 L5 5 L9 1' stroke='currentColor' strokeWidth='1.5' strokeLinecap='round' strokeLinejoin='round' />
        </svg>
      </button>
      {open && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            left: 0,
            zIndex: 20,
            minWidth: 160,
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
            padding: 8,
            borderRadius: 12,
            background: 'var(--bg-3)',
            border: '1px solid var(--line)',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.4)',
          }}
        >
          {seasons.map((n) => {
            const isCurrent = n === current
            return (
              <button
                key={n}
                type='button'
                disabled={!isCurrent}
                onClick={() => setOpen(false)}
                style={{
                  textAlign: 'left',
                  padding: '6px 10px',
                  borderRadius: 8,
                  border: 'none',
                  background: 'none',
                  cursor: isCurrent ? 'pointer' : 'not-allowed',
                  color: isCurrent ? 'var(--dawn-amber)' : 'var(--fg-4)',
                  fontSize: 14,
                  fontWeight: isCurrent ? 600 : 400,
                }}
              >
                Season {n}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ----- Leaderboard ------------------------------------------------

const LB_GRID = '64px 1fr 160px'

function medalFor(rank: number): StaticImageData | null {
  if (rank === 1) return goldIcon
  if (rank === 2) return silverIcon
  if (rank === 3) return bronzeIcon
  return null
}

function LeaderboardPanel({
  entries,
  walletAddress,
  walletPoints,
  walletRank,
  compact = false,
}: {
  entries: { user_wallet: string; total_points: number }[]
  walletAddress: string | null
  walletPoints: number
  walletRank: number | null
  compact?: boolean
}) {
  const fmt = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 0 })
  const topTen = entries.slice(0, 10)
  const hasUser = !!walletAddress
  // On mobile the PTS column shrinks and horizontal padding tightens so the
  // three columns still fit a 360px viewport (Figma 6641-14590).
  const grid = compact ? '34px 1fr auto' : LB_GRID
  const padX = compact ? 16 : 28

  return (
    <div style={{ ...cardPanel, overflow: 'hidden' }}>
      {/* header */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: grid,
          alignItems: 'center',
          padding: `16px ${padX}px`,
          borderBottom: '1px solid var(--line)',
        }}
      >
        <span className='kicker' style={{ fontSize: 11 }}>#</span>
        <span className='kicker' style={{ fontSize: 11 }}>Wallet</span>
        <span className='kicker' style={{ fontSize: 11, textAlign: 'right' }}>PTS</span>
      </div>

      {/* current user */}
      {hasUser && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: grid,
            alignItems: 'center',
            padding: `16px ${padX}px`,
            margin: '12px 16px',
            borderRadius: 10,
            border: '1px solid rgba(243,162,74,0.35)',
            background: 'linear-gradient(90deg, rgba(243,162,74,0.10), rgba(243,162,74,0.02))',
          }}
        >
          <span className='tabular' style={{ color: 'var(--dawn-amber)', fontSize: 13 }}>
            {walletRank && walletRank > 0 ? walletRank : '—'}
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}>
            <span style={{ color: 'var(--dawn-amber)', fontWeight: 600, fontSize: 13 }}>
              {formatWallet(walletAddress)}
            </span>
            <span
              style={{
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: '0.04em',
                padding: '3px 8px',
                borderRadius: 5,
                color: 'var(--dawn-amber)',
                background: 'rgba(243,162,74,0.16)',
              }}
            >
              You
            </span>
          </span>
          <span className='tabular' style={{ textAlign: 'right', color: 'var(--fg)', fontWeight: 600, fontSize: 13 }}>
            {fmt(walletPoints)}
          </span>
        </div>
      )}

      {/* divider */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: `10px ${padX}px 18px` }}>
        <span style={{ flex: 1, height: 1, background: 'var(--line)' }} />
        <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>Top 10</span>
        <span style={{ flex: 1, height: 1, background: 'var(--line)' }} />
      </div>

      {/* rows */}
      {topTen.length === 0 ? (
        <div style={{ padding: `40px ${padX}px 48px`, textAlign: 'center', color: 'var(--fg-3)', fontSize: 13 }}>
          Leaderboard data is not available yet.
        </div>
      ) : (
        <div style={{ padding: `0 ${compact ? 12 : 16}px 16px`, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {topTen.map((entry, i) => {
            const rank = i + 1
            const medal = medalFor(rank)
            return (
              <div
                key={`${entry.user_wallet}-${rank}`}
                style={{
                  display: 'grid',
                  gridTemplateColumns: grid,
                  alignItems: 'center',
                  padding: compact ? '14px 16px' : '14px 28px',
                  borderRadius: 10,
                  border: '1px solid var(--line)',
                  background: rank <= 3 ? 'rgba(255,255,255,0.025)' : 'var(--bg-1)',
                }}
              >
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: compact ? 8 : 12 }}>
                  {medal ? (
                    <Image src={medal} alt='' width={22} height={22} style={{ borderRadius: 5 }} />
                  ) : (
                    <span style={{ width: 22 }} />
                  )}
                  <span className='tabular' style={{ fontSize: 13, color: rank <= 3 ? 'var(--fg-2)' : 'var(--fg-3)' }}>
                    {rank}
                  </span>
                </span>
                <span style={{ fontSize: 13, color: rank <= 3 ? 'var(--fg-2)' : 'var(--fg-3)' }}>
                  {formatWallet(entry.user_wallet)}
                </span>
                <span className='tabular' style={{ textAlign: 'right', fontSize: 13, color: 'var(--fg)', fontWeight: 600 }}>
                  {fmt(entry.total_points)}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ----- Page -------------------------------------------------------

const TABLE_GRID = '2fr 1.05fr 1.15fr 0.8fr 0.7fr 1fr'

export default function MidnightPortfolioPage() {
  const [isSmallScreen, setIsSmallScreen] = useState(false)
  const [isCompactScreen, setIsCompactScreen] = useState(false)
  const router = useRouter()
  const { open } = useAppKit()
  const { address } = useAppKitAccount()
  const balances = usePortfolioBalances()
  const requestWalletConnection = useCompliance((s) => s.requestWalletConnection)
  const { seasonNumber, seasonStartDate, seasonEndDate, walletPoints, walletRank, walletAddress, leaderboardEntries } =
    usePortfolioPoints()
  const { nav, fetchNav, fetchNavHistory, navHistory } = useNav()
  const {
    walletRows,
    pendingPanelData,
    canWithdraw,
    withdrawMaxAmount,
    isWithdrawing,
    withdrawError,
    onWithdraw,
    onClaim,
  } = useWalletSectionData(balances)
  // Pending unstake (transferable withdrawal) positions for the sUSD.tel row —
  // surfaced as a badge + expandable drawer (DAWN-1503). Amount '' keeps the
  // hook in read-only mode (no quote simulation); it still loads vault state and
  // the user's pending withdrawals.
  const unstake = useVaultUnstake('', balances.isConnected)
  // Cross-protocol (Boost) positions — Orca LPs, Loopscale loans, etc. — keyed
  // by strategy id, rendered as real portfolio rows in their strategy group.
  const partnerPositions = usePartnerPositions()

  const [view, setView] = useState<'position' | 'leaderboard'>('position')
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [activeManageModal, setActiveManageModal] = useState<'none' | 'actions' | 'withdraw'>('none')
  const [managePosition, setManagePosition] = useState<{ label: string; value: string } | null>(null)
  const [withdrawAmountInput, setWithdrawAmountInput] = useState('')

  useEffect(() => {
    const media = window.matchMedia('(max-width: 1024px)')
    const sync = () => setIsSmallScreen(media.matches)
    sync()
    media.addEventListener('change', sync)
    return () => media.removeEventListener('change', sync)
  }, [])
  useEffect(() => {
    const media = window.matchMedia('(max-width: 1320px)')
    const sync = () => setIsCompactScreen(media.matches)
    sync()
    media.addEventListener('change', sync)
    return () => media.removeEventListener('change', sync)
  }, [])
  useEffect(() => {
    void fetchNav()
    void fetchNavHistory(30)
  }, [fetchNav, fetchNavHistory])

  // Build the runtime rows: real wallet/pending data drives the idle row,
  // the pending-claim row and the staked sUSD.tel row. LP/Lend rows stay
  // mock until cross-protocol integration lands.
  const usdtelRow = walletRows.find((r) => r.asset === 'USD.tel')
  const susdtelRow = walletRows.find((r) => r.asset === 'sUSD.tel')
  const pendingTotalUsd = pendingPanelData.rows.reduce((s, r) => s + numFromBalance(r.amount), 0)
  const pendingNextLabel = pendingPanelData.nextClaimableLabel
  // sUSD.tel is a yield-bearing share token: 1 sUSD.tel = `exchange_rate`
  // USD.tel (~$1.07), not $1. Value the staked position at NAV, not face.
  const susdtelStakedUsd = susdtelRow
    ? numFromBalance(susdtelRow.balance) * (nav?.exchange_rate ?? 1)
    : 0
  const usdtelIdleUsd = usdtelRow ? numFromBalance(usdtelRow.balance) : 0
  // USDC is a $1-pegged stable, so its wallet balance is its USD value.
  const usdcIdleUsd = numFromBalance(balances.usdcBalance)
  const claims = pendingPanelData.rows
  const hasClaims = claims.length > 0

  // sUSD.tel share holders realize the utilization-discounted vault yield
  // (raw APY × fraction of capital actually deployed), matching the
  // "effective APY" headline shown on the dashboard and top nav chip.
  const vaultEffectiveApyPct = (nav?.apy ?? 0) * (nav?.utilization_rate ?? 0) * 100

  const realRows: Row[] = []
  if (usdcIdleUsd > 0) {
    realRows.push({
      kind: 'idle', group: 'idle', id: 'usdc', asset: 'USDC',
      status: 'Idle', statusTone: 'gray',
      balance: usdcIdleUsd.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
      balanceSub: 'In your wallet',
      usd: `$${usdcIdleUsd.toLocaleString('en-US', { maximumFractionDigits: 2 })}`,
      apy: null,
      action: 'amplify', actionLabel: 'Buy USD.tel', img: usdcIcon,
      cta: { route: 'buy-stake', buyStakeMode: 'buy' },
    })
  }
  realRows.push({
    kind: 'idle', group: 'idle', id: 'idle', asset: 'USD.tel',
    status: 'Idle', statusTone: 'gray',
    balance: usdtelRow?.balance ?? '0',
    balanceSub: 'In your wallet',
    usd: usdtelRow ? `$${usdtelIdleUsd.toLocaleString()}` : '$0',
    apy: null,
    action: 'manage', actionLabel: 'Manage', img: usdtelIcon,
  })
  // The sUSD.tel row is the single home for vault activity: the staked balance
  // plus in-flight stakes (deposits settling into sUSD.tel) and unstakes
  // (withdrawals settling back to USD.tel), shown in an expandable drawer below.
  // It therefore also renders when the user holds no settled shares yet but has
  // a pending stake or unstake. Pending stakes are shown here (not under
  // USD.tel) and roll into the staked balance once claimed.
  const hasPendingWithdrawals = unstake.pendingWithdrawals.length > 0
  const hasPendingStakes = pendingPanelData.pendingCount > 0
  if (susdtelStakedUsd > 0 || hasPendingWithdrawals || hasPendingStakes) {
    const isStakedActive = susdtelStakedUsd > 0
    const pendingSub = hasPendingStakes ? 'pending stake' : 'unstaking'
    realRows.push({
      kind: 'deployed', group: 'stel', id: 'stel-staked', asset: 'sUSD.tel',
      sub: isStakedActive ? 'staked' : pendingSub,
      status: isStakedActive ? 'Deployed' : 'Processing',
      statusTone: isStakedActive ? 'blue' : 'amber',
      balance: susdtelRow?.balance ?? '0',
      balanceSub: 'Staked vault',
      usd: `$${susdtelStakedUsd.toLocaleString('en-US', { maximumFractionDigits: 2 })}`,
      apy: isStakedActive && nav ? `${vaultEffectiveApyPct.toFixed(2)}%` : '–',
      action: 'manage', actionLabel: 'Manage', img: susdtelIcon,
    })
  }

  // Cross-protocol positions (Orca LP, Loopscale, …) from usePartnerPositions.
  // Each is matched to its strategy descriptor for the protocol icon, pair label
  // and group, then rendered as a deployed row that deep-links into Boost.
  for (const [strategyId, pos] of Object.entries(partnerPositions)) {
    const descriptor = STRATEGY_DESCRIPTORS[strategyId]
    if (!descriptor) {
      continue
    }
    const protocolIcon = PROTOCOL_ICONS[descriptor.protocol] ?? usdtelIcon
    realRows.push({
      kind: 'deployed', group: descriptor.group, id: `partner-${strategyId}`,
      asset: descriptor.protocol, sub: descriptor.pair,
      status: 'Deployed', statusTone: 'green',
      balance: pos.balanceLabel,
      balanceSub: 'LP position',
      usd: pos.usdLabel,
      apy: pos.apyLabel ?? null,
      action: 'amplify', actionLabel: 'Manage', img: protocolIcon,
      // Open the partner's pool/position page directly (same as Boost's Manage);
      // fall back to the Boost tab when a strategy has no deposit URL.
      externalUrl: descriptor.depositUrl,
      cta: { route: 'amplify', amplifyTab: descriptor.group === 'lp' ? 'lp' : descriptor.group === 'ytrade' ? 'yieldTrading' : 'lend' },
    })
  }

  const allRows: Row[] = useMemo(
    () => realRows,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [usdtelRow?.balance, susdtelRow?.balance, balances.usdcBalance, pendingPanelData.pendingCount, pendingTotalUsd, pendingNextLabel, hasClaims, claims.length, unstake.pendingWithdrawals.length, partnerPositions],
  )
  const groupTotals = useMemo(() => computeGroupTotals(allRows), [allRows])
  // Pending deposits no longer have their own row, so add their USD back into the
  // idle bucket (and grand total) to keep the headline figures unchanged.
  const grandTotal = groupTotals.reduce((s, g) => s + g.value, 0) + pendingTotalUsd
  const strategyCount = groupTotals.filter((g) => g.value > 0).length
  const idleTotal = (groupTotals.find((g) => g.id === 'idle')?.value ?? 0) + pendingTotalUsd
  const deployedTotal = Math.max(0, grandTotal - idleTotal)
  const capitalEfficiencyPct = grandTotal > 0 ? (deployedTotal / grandTotal) * 100 : 0
  // Per-user realised profit on the staked position (DAWN-1501). sUSD.tel is a
  // share token that mints at par (1 share = 1 USD.tel) and appreciates as vault
  // yield accrues, so the holder's own profit is shares × (sharePrice − 1) —
  // their slice of the yield, not the vault-wide `cumulative_yield`.
  const susdtelShares = susdtelRow ? numFromBalance(susdtelRow.balance) : 0
  const sharePrice = nav ? liveSharePrice(nav) : 1
  const pfYieldAllTime = Math.max(0, susdtelShares * (sharePrice - 1))
  // Portfolio-wide weighted APY: Σ(position.usd × position.apy) blended over
  // the full position. Idle/pending rows have apy = null and contribute zero,
  // which drags the weighted APY below the deployed-only APY when capital
  // sits in USD.tel or unsettled claims.
  const apyUsdSum = allRows.reduce((sum, r) => sum + parseApyPct(r.apy) * usdNum(r.usd), 0)
  const pfWeightedApy = grandTotal > 0 ? apyUsdSum / grandTotal : 0
  const pfDeployedApy = deployedTotal > 0 ? apyUsdSum / deployedTotal : 0
  // Decompose the deployed blended APY into the sUSD.tel vault floor ("Base")
  // and the extra premium amplify positions earn over it ("Boost"). Base is
  // capped at the deployed APY so the two always sum to it and stay ≥ 0; both
  // collapse to 0 when no capital is deployed.
  const pfBaseApy = deployedTotal > 0 ? Math.min((nav?.apy ?? 0) * 100, pfDeployedApy) : 0
  const pfBoostApy = Math.max(0, pfDeployedApy - pfBaseApy)
  const yieldPct = grandTotal > 0 ? (pfYieldAllTime / grandTotal) * 100 : 0
  // The "Yield Earned · All Time" KPI card mirrors the vault-wide cumulative
  // yield shown in the top nav (nav.cumulative_yield), with the 7d delta taken
  // from the same series in history. (The total-position hero pill above keeps
  // the per-user figure so its percentage stays meaningful.)
  const cumulativeYield = nav?.cumulative_yield ?? 0
  const cumulativeYield7d =
    navHistory.length > 1
      ? Math.max(
          0,
          (navHistory[navHistory.length - 1]?.cumulative_yield ?? 0) -
            (navHistory[Math.max(navHistory.length - 8, 0)]?.cumulative_yield ?? 0),
        )
      : 0

  const sparkPoints = useMemo(() => {
    if (navHistory.length > 1) {
      const vals = navHistory.slice(-24).map((h) => h.interest_profit)
      const min = Math.min(...vals)
      const max = Math.max(...vals)
      const range = max - min || 1
      return vals.map((v) => 4 + ((v - min) / range) * 28)
    }
    return [4, 5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 17, 18, 20, 22, 23, 25, 26, 28, 30]
  }, [navHistory])

  // Pending unstake positions surfaced under the sUSD.tel row (DAWN-1503).
  // Each transferable withdrawal locks sUSD.tel shares that settle into USD.tel
  // once the waiting period elapses; before that the user can cancel.
  const unstakeItems = useMemo<UnstakeItem[]>(() => {
    const scale = 10 ** unstake.decimals
    return unstake.pendingWithdrawals.map((w) => {
      const shares = Number(w.pendingSharesRaw) / scale
      const assetsRaw = Number(w.pendingAssetsRaw)
      const assets = assetsRaw > 0 ? assetsRaw / scale : shares * sharePrice
      return {
        index: w.index,
        sharesLabel: shares.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
        assetsLabel: assets.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
        // Readiness is derived from this at render (see PendingUnstakeList), not
        // frozen here, so the row flips Cancel → Claim without a refetch.
        readyAtSec: w.executableAtTimestamp,
        claimableDate: formatClaimableDate(w.executableAtTimestamp),
      }
    })
  }, [unstake.pendingWithdrawals, unstake.decimals, sharePrice])
  const pendingUnstakeCount = unstakeItems.length
  const handleClaimUnstake = (index: number) => {
    void unstake.executeUnstake(index)
  }
  const handleCancelUnstake = (index: number) => {
    void unstake.cancelUnstake(index)
  }

  // ----- handlers -----
  const openManageModal = (label: string, value: string) => {
    setManagePosition({ label, value })
    setActiveManageModal('actions')
  }
  const handleRowAction = (r: Row) => {
    // Partner positions (Orca LP, …) deep-link straight to the partner's
    // pool/position page in a new tab — matching the Boost "Manage" button.
    if (r.externalUrl) {
      window.open(r.externalUrl, '_blank', 'noopener,noreferrer')
      return
    }
    if (r.action === 'manage') {
      openManageModal(r.asset, r.usd)
    } else if (r.action === 'claims') {
      setExpanded((s) => ({ ...s, [r.id]: !s[r.id] }))
    } else {
      const cta = r.cta ?? PF_GROUPS.find((g) => g.id === r.group)?.defaultRoute
      if (cta) applyCta(router, cta)
    }
  }
  const handleCloseManageModal = () => setActiveManageModal('none')
  const handleGoToStake = () => {
    setActiveManageModal('none')
    router.push('/buy-stake?tab=stake&mode=stake')
  }
  const handleGoToUnstake = () => {
    setActiveManageModal('none')
    router.push('/buy-stake?tab=stake&mode=unstake')
  }
  const handleGoToBoost = () => {
    setActiveManageModal('none')
    router.push('/boost')
  }
  const handleOpenWithdrawConfirm = () => {
    setWithdrawAmountInput('')
    setActiveManageModal('withdraw')
  }
  const maxWithdrawAmountNumeric = Number(withdrawMaxAmount) || 0
  const withdrawAmountNumeric = Number(withdrawAmountInput) || 0
  const withdrawAmountError = !withdrawAmountInput.trim()
    ? 'Enter an amount to withdraw.'
    : withdrawAmountNumeric > maxWithdrawAmountNumeric
      ? 'Amount exceeds available balance.'
      : null
  const handleWithdrawConfirm = async (amount: string) => {
    if (withdrawAmountError) return
    await onWithdraw(amount)
    setActiveManageModal('none')
  }

  // ----- not connected -----
  if (!balances.isConnected) {
    return (
      <div className='app-container fade-up' style={{ padding: '120px 32px', textAlign: 'center' }}>
        <h1 className='h-display' style={{ fontSize: 48, marginBottom: 16 }}>
          Connect wallet to view portfolio
        </h1>
        <p style={{ color: 'var(--fg-2)', maxWidth: 440, margin: '0 auto 24px' }}>
          Your positions, points and deployed sUSD.tel will appear here.
        </p>
        <GradientButton
          onClick={() => void requestWalletConnection(() => open())}
          style={{ padding: '12px 22px', fontSize: 14 }}
        >
          Connect wallet
        </GradientButton>
      </div>
    )
  }

  return (
    <div
      data-screen-label='02 Portfolio'
      className='fade-up app-container'
      style={{ width: '100%', padding: isSmallScreen ? '32px 16px 64px' : isCompactScreen ? '56px 20px 96px' : '56px 32px 96px', display: 'flex', flexDirection: 'column', gap: 28 }}
    >
      {/* Hero (desktop) — on mobile the title folds into the total block below
          per Figma 6634-12486 (small "Your portfolio" label · number · caption). */}
      {!isSmallScreen && (
        <div style={{ textAlign: 'center', maxWidth: 560, margin: '0 auto', paddingTop: 12 }}>
          <h1 className='h-display' style={{ fontSize: 46, margin: '0 0 12px', letterSpacing: '-0.025em' }}>
            Your <span className='gradient-text'>portfolio</span>
          </h1>
          <div style={{ color: 'var(--fg-3)', fontSize: 14 }}>
            A live view of where your capital is and what it&apos;s doing.
          </div>
        </div>
      )}

      {/* Total position card */}
      <div style={{ borderRadius: 16, background: 'transparent', border: 'none', padding: isSmallScreen ? '8px 0' : '32px 28px', textAlign: 'center' }}>
        {isSmallScreen ? (
          <div style={{ fontSize: 15, color: 'var(--fg-2)', marginBottom: 8 }}>Your portfolio</div>
        ) : (
          <div className='kicker' style={{ marginBottom: 14 }}>Total position</div>
        )}
        <div style={{ position: 'relative', display: 'flex', justifyContent: 'center' }}>
          <div
            aria-hidden
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              width: 'min(280px, 60%)',
              height: 120,
              background: 'radial-gradient(ellipse at center, rgba(243,162,74,0.28) 0%, transparent 70%)',
              filter: 'blur(28px)',
              pointerEvents: 'none',
              zIndex: 0,
            }}
          />
          <div
            className='tabular'
            style={{
              position: 'relative',
              zIndex: 1,
              fontFamily: 'var(--font-display)',
              fontWeight: 500,
              fontSize: isSmallScreen ? 48 : 60,
              letterSpacing: '-0.03em',
              lineHeight: 1,
            }}
          >
            ${grandTotal.toLocaleString('en-US', { maximumFractionDigits: 0 })}
          </div>
        </div>
        {isSmallScreen && (
          <div className='kicker' style={{ marginTop: 12 }}>Total position</div>
        )}
        <div style={{ marginTop: 18, display: 'inline-flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 7,
              padding: '6px 12px',
              borderRadius: 999,
              background: pfYieldAllTime < 0 ? 'var(--neg-bg)' : 'var(--pos-bg)',
              border: `1px solid ${pfYieldAllTime < 0 ? 'var(--neg-line)' : 'var(--pos-line)'}`,
              color: pfYieldAllTime < 0 ? 'var(--neg)' : 'var(--pos)',
              fontSize: 13,
              fontFamily: 'var(--font-display)',
              fontWeight: 500,
            }}
            className='tabular'
          >
            <svg width='12' height='12' viewBox='0 0 12 12' fill='none' aria-hidden>
              <path
                d={pfYieldAllTime < 0 ? 'M3 4.5L6 7.5L9 4.5' : 'M3 7.5L6 4.5L9 7.5'}
                stroke='currentColor'
                strokeWidth='1.5'
                strokeLinecap='round'
                strokeLinejoin='round'
              />
            </svg>
            {fmtSignedUsd(pfYieldAllTime)} ({yieldPct >= 0 ? '+' : ''}{yieldPct.toFixed(2)}%)
          </span>
          <span style={{ color: 'var(--fg-4)', fontSize: 13 }}>all-time yield earned</span>
        </div>
        <div
          style={{
            marginTop: isSmallScreen ? 16 : 20,
            paddingTop: 0,
            borderTop: 'none',
            display: 'flex',
            justifyContent: 'center',
            gap: 28,
            fontSize: 13,
            color: 'var(--fg-3)',
          }}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}>
            <svg width='11' height='11' viewBox='0 0 11 11' fill='none' xmlns='http://www.w3.org/2000/svg' aria-hidden='true'>
              <path
                d='M10.0825 5.49955H8.94593C8.74565 5.49912 8.55073 5.56431 8.39099 5.68514C8.23126 5.80598 8.1155 5.97581 8.06142 6.16866L6.98443 10C6.97749 10.0238 6.96301 10.0447 6.94318 10.0596C6.92335 10.0745 6.89923 10.0825 6.87444 10.0825C6.84965 10.0825 6.82553 10.0745 6.80569 10.0596C6.78586 10.0447 6.77139 10.0238 6.76445 10L4.23465 0.999085C4.22771 0.975286 4.21324 0.954381 4.19341 0.939507C4.17357 0.924632 4.14945 0.916592 4.12466 0.916592C4.09987 0.916592 4.07575 0.924632 4.05592 0.939507C4.03609 0.954381 4.02161 0.975286 4.01467 0.999085L2.93768 4.83044C2.88381 5.02253 2.76874 5.19181 2.60993 5.31257C2.45113 5.43333 2.25725 5.49898 2.05775 5.49955H0.916592'
                stroke='#F3A24A'
                strokeWidth='0.916592'
                strokeLinecap='round'
                strokeLinejoin='round'
              />
            </svg>
            <span style={{ color: 'var(--fg)', fontWeight: 600 }} className='tabular'>{allRows.length}</span> positions
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}>
            <span style={{ color: 'var(--fg)', fontWeight: 600 }} className='tabular'>{strategyCount}</span> strategies
          </span>
        </div>
      </div>

      {/* KPI cards — single column on mobile, 4-up on desktop (Figma 6634-12486). */}
      <div style={{ display: 'grid', gridTemplateColumns: isSmallScreen ? 'minmax(0, 1fr)' : 'repeat(4, minmax(0, 1fr))', gap: 16 }}>
        {/* Yield earned — vault-wide cumulative yield (matches the top nav). */}
        <KpiCard title='Yield Earned · All Time'>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
            <div className='tabular' style={{ fontFamily: 'var(--font-display)', fontSize: 26, fontWeight: 500, color: cumulativeYield < 0 ? 'var(--neg)' : 'var(--pos)', letterSpacing: '-0.02em' }}>
              {fmtSignedUsd(cumulativeYield)}
            </div>
            <div style={{ color: 'var(--fg-3)', fontSize: 11 }}>
              last 7d <span className='tabular' style={{ color: cumulativeYield7d < 0 ? 'var(--neg)' : 'var(--pos)' }}>{fmtSignedUsd(cumulativeYield7d)}</span>
            </div>
          </div>
          <div style={{ marginTop: 'auto', paddingTop: 14 }}>
            <PfSparkline color='#F3A24A' points={sparkPoints} />
          </div>
        </KpiCard>

        {/* Weighted APY — subtitle decomposes the deployed blended yield into
            the sUSD.tel vault floor ("Base") and the premium amplify positions
            add on top of it ("Boost"), so the user sees where their yield comes
            from rather than a trivially-zero idle bucket. */}
        <KpiCard title='Weighted APY'>
          <div className='tabular' style={{ fontFamily: 'var(--font-display)', fontSize: 26, fontWeight: 500, letterSpacing: '-0.02em' }}>
            {pfWeightedApy.toFixed(2)}<span style={{ color: 'var(--fg-3)', fontSize: 18 }}> %</span>
          </div>
          <div style={{ marginTop: 'auto', paddingTop: 14, display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap', fontSize: 12, color: 'var(--fg-3)' }}>
            <span>Base</span>
            <span className='tabular' style={{ color: 'var(--fg-2)' }}>{pfBaseApy.toFixed(2)}%</span>
            <span style={{ color: 'var(--fg-4)' }}>·</span>
            <span>Boost</span>
            <span className='tabular' style={{ color: 'var(--dawn-rose)' }}>
              +{pfBoostApy.toFixed(2)}%
            </span>
          </div>
        </KpiCard>

        {/* Capital efficiency */}
        <KpiCard title='Capital Efficiency'>
          <div className='tabular' style={{ fontFamily: 'var(--font-display)', fontSize: 26, fontWeight: 500, letterSpacing: '-0.02em' }}>
            {capitalEfficiencyPct.toFixed(0)}<span style={{ color: 'var(--fg-3)', fontSize: 18 }}> %</span>
          </div>
          <div style={{ marginTop: 14, height: 6, background: 'var(--bg-3)', borderRadius: 3, overflow: 'hidden' }}>
            <div style={{ width: `${Math.min(100, capitalEfficiencyPct)}%`, height: '100%', background: 'linear-gradient(90deg, var(--dawn-amber), var(--dawn-coral))' }} />
          </div>
          <div style={{ marginTop: 'auto', paddingTop: 12, display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap', fontSize: 12, color: 'var(--fg-3)' }}>
            <span>Deployed</span>
            <span className='tabular' style={{ color: 'var(--fg-2)' }}>
              ${deployedTotal.toLocaleString('en-US', { maximumFractionDigits: 0 })}
            </span>
            <span>of</span>
            <span className='tabular' style={{ color: 'var(--fg-2)' }}>
              ${grandTotal.toLocaleString('en-US', { maximumFractionDigits: 0 })}
            </span>
          </div>
        </KpiCard>

        {/* Season */}
        <KpiCard
          title={
            <>
              <SeasonSelector current={seasonNumber ?? 1} />
              <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                Rank: <span style={{ color: 'var(--fg)', fontWeight: 600 }}>{walletRank ? `#${walletRank}` : '—'}</span>
              </span>
            </>
          }
        >
          <div className='tabular' style={{ fontFamily: 'var(--font-display)', fontSize: 26, fontWeight: 500, letterSpacing: '-0.02em' }}>
            {walletPoints.toLocaleString('en-US', { maximumFractionDigits: 0 })}
          </div>
          <div style={{ fontSize: 12, color: 'var(--fg-3)', marginTop: 2 }}>season points</div>
          <div style={{ marginTop: 'auto', paddingTop: 12, display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '4px 10px',
                borderRadius: 999,
                background: 'var(--pos-bg)',
                border: '1px solid var(--pos-line)',
                color: 'var(--pos)',
                fontSize: 11,
                fontWeight: 500,
                flexShrink: 0,
              }}
            >
              <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--pos)' }} />
              Active
            </span>
            {fmtSeasonRange(seasonStartDate, seasonEndDate) && (
              <span style={{ fontSize: 12, color: 'var(--fg-3)', whiteSpace: 'nowrap' }}>{fmtSeasonRange(seasonStartDate, seasonEndDate)}</span>
            )}
          </div>
        </KpiCard>
      </div>

      {/* Portfolio detail */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, gap: 16, flexWrap: 'wrap' }}>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, fontWeight: 500, letterSpacing: '-0.01em' }}>
            Portfolio detail
          </div>
          {/* toggle */}
          <SegmentedToggle
            value={view}
            onChange={setView}
            options={[
              { value: 'position', label: 'Position' },
              { value: 'leaderboard', label: 'Leaderboard' },
            ]}
          />
        </div>

        {view === 'leaderboard' ? (
          <LeaderboardPanel
            entries={leaderboardEntries}
            walletAddress={walletAddress ?? address ?? null}
            walletPoints={walletPoints}
            walletRank={walletRank}
            compact={isSmallScreen}
          />
        ) : (
          <>
            {/* Desktop table */}
            <div style={{ ...cardPanel, overflow: 'hidden', display: isSmallScreen ? 'none' : 'block' }}>
              {/* header */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: TABLE_GRID,
                  gap: 16,
                  alignItems: 'center',
                  padding: '16px 28px',
                  borderBottom: '1px solid var(--line)',
                }}
              >
                <span className='kicker' style={{ fontSize: 11 }}>Asset / Venue</span>
                <span className='kicker' style={{ fontSize: 11, textAlign: 'center' }}>Status</span>
                <span className='kicker' style={{ fontSize: 11, textAlign: 'center' }}>Balance</span>
                <span className='kicker' style={{ fontSize: 11, textAlign: 'center' }}>USD</span>
                <span className='kicker' style={{ fontSize: 11, textAlign: 'center' }}>APY</span>
                <span className='kicker' style={{ fontSize: 11, textAlign: 'right' }}>Action</span>
              </div>

              {allRows.map((r) => {
                // The sUSD.tel row hosts both in-flight stakes and unstakes in one
                // expandable drawer (no extra rows).
                const isStelRow = r.id === 'stel-staked'
                const stakeCount = isStelRow ? pendingPanelData.pendingCount : 0
                const unstakeCount = isStelRow ? pendingUnstakeCount : 0
                const badgeCount = stakeCount + unstakeCount
                const isExpandable = badgeCount > 0
                const isOpen = !!expanded[r.id]
                return (
                  <div key={r.id}>
                    <div
                      onClick={isExpandable ? () => setExpanded((s) => ({ ...s, [r.id]: !s[r.id] })) : undefined}
                      style={{
                        display: 'grid',
                        gridTemplateColumns: TABLE_GRID,
                        gap: 16,
                        alignItems: 'center',
                        padding: '18px 28px',
                        borderBottom: '1px solid var(--line)',
                        background: isExpandable && isOpen ? 'rgba(243,162,74,0.04)' : 'transparent',
                        cursor: isExpandable ? 'pointer' : 'default',
                        transition: 'background 160ms ease',
                      }}
                    >
                      {/* asset */}
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 14, minWidth: 0 }}>
                        <TokenIcon src={r.img} />
                        <span style={{ minWidth: 0 }}>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                            <span style={{ color: 'var(--fg)', fontWeight: 500, fontSize: 14 }}>{r.asset}</span>
                            {isExpandable && <PendingBadge count={badgeCount} />}
                            {isExpandable && <ExpandChevron open={isOpen} />}
                          </span>
                          {(r.sub || r.chainBadge) && (
                            <span style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                              {r.sub && <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>{r.sub}</span>}
                              {r.chainBadge && <ChainBadge kind={r.chainBadge} />}
                            </span>
                          )}
                        </span>
                      </span>
                      {/* status */}
                      <span style={{ display: 'flex', justifyContent: 'center' }}>
                        <StatusPill label={r.status} tone={r.statusTone} />
                      </span>
                      {/* balance */}
                      <span style={{ textAlign: 'center' }}>
                        <div className='tabular' style={{ fontSize: 14, color: 'var(--fg)' }}>{r.balance}</div>
                        {r.balanceSub && <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 2 }}>{r.balanceSub}</div>}
                      </span>
                      {/* usd */}
                      <span className='tabular' style={{ textAlign: 'center', fontSize: 14, color: 'var(--fg-2)' }}>{r.usd}</span>
                      {/* apy */}
                      <span className='tabular' style={{ textAlign: 'center', fontSize: 14, color: r.apy ? 'var(--dawn-amber)' : 'var(--fg-4)' }}>
                        {r.apy || '–'}
                      </span>
                      {/* action */}
                      <span style={{ display: 'flex', justifyContent: 'flex-end' }}>
                        <ActionButton label={r.actionLabel} onClick={() => handleRowAction(r)} />
                      </span>
                    </div>

                    {/* sUSD.tel in-flight drawer: pending stakes + unstakes */}
                    {isExpandable && isOpen && (
                      <div
                        style={{
                          padding: '4px 28px 18px',
                          background: 'rgba(243,162,74,0.03)',
                          borderBottom: '1px solid var(--line)',
                          animation: 'fadeIn 200ms ease',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 4,
                        }}
                      >
                        {stakeCount > 0 && (
                          <>
                            <div className='kicker' style={{ margin: '12px 0 10px', color: 'var(--dawn-amber)' }}>Pending stakes</div>
                            <ProcessingStakeList stakes={claims} onClaim={onClaim} />
                          </>
                        )}
                        {unstakeCount > 0 && (
                          <>
                            <div className='kicker' style={{ margin: '12px 0 10px', color: 'var(--dawn-amber)' }}>Pending unstakes</div>
                            <PendingUnstakeList
                              items={unstakeItems}
                              isSubmitting={unstake.isSubmitting}
                              onClaim={handleClaimUnstake}
                              onCancel={handleCancelUnstake}
                            />
                          </>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}

              {/* footer strip */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 16,
                  padding: '20px 28px',
                  background: 'linear-gradient(90deg, rgba(243,162,74,0.06), rgba(232,64,102,0.03))',
                  flexWrap: 'wrap',
                }}
              >
                <span style={{ fontSize: 14, color: 'var(--fg-3)', display: 'inline-flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                  Total portfolio
                  <span className='tabular' style={{ color: 'var(--fg)', fontWeight: 600, fontFamily: 'var(--font-display)' }}>
                    ${grandTotal.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                  </span>
                  <span style={{ color: 'var(--fg-4)' }}>|</span>
                  <span>{allRows.length} positions · {strategyCount} active strategies</span>
                </span>
                <GradientButton
                  size='sm'
                  onClick={() => applyCta(router, { route: 'amplify' })}
                  style={{ padding: '10px 18px' }}
                >
                  Explore Boost Strategies
                </GradientButton>
              </div>
            </div>

            {/* Mobile cards — grouped into status sections with count + sum
                headers, per Figma 6634-12486. */}
            {isSmallScreen && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
                {PF_SECTION_ORDER.map((section) => {
                  const rows = allRows.filter((r) => sectionForRow(r) === section.id)
                  if (rows.length === 0) return null
                  const sectionTotal = rows.reduce((s, r) => s + usdNum(r.usd), 0)
                  return (
                    <div key={section.id} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                      {/* Section header: label + count badge · total */}
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '0 1px' }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}>
                          <span style={{ fontFamily: 'var(--font-display)', fontSize: 16, fontWeight: 500, color: 'var(--fg)' }}>
                            {section.label}
                          </span>
                          <span
                            className='tabular'
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              minWidth: 18,
                              height: 18,
                              padding: '0 5px',
                              borderRadius: 6,
                              fontSize: 11,
                              fontWeight: 600,
                              color: 'var(--dawn-amber)',
                              background: 'rgba(243,162,74,0.12)',
                            }}
                          >
                            {rows.length}
                          </span>
                        </span>
                        <span className='tabular' style={{ fontFamily: 'var(--font-display)', fontSize: 16, fontWeight: 500, color: 'var(--fg)' }}>
                          ${sectionTotal.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                        </span>
                      </div>

                      {rows.map((r) => {
                        const isStelRow = r.id === 'stel-staked'
                        const stakeCount = isStelRow ? pendingPanelData.pendingCount : 0
                        const unstakeCount = isStelRow ? pendingUnstakeCount : 0
                        const badgeCount = stakeCount + unstakeCount
                        const isExpandable = badgeCount > 0
                        const isOpen = !!expanded[r.id]
                        return (
                        <div key={`m-${r.id}`} style={{ ...cardPanel, padding: 20 }}>
                          {/* Header: asset + status inline, action button on the right. */}
                          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
                              <TokenIcon src={r.img} size={32} />
                              <span style={{ minWidth: 0 }}>
                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                                  <span style={{ color: 'var(--fg)', fontWeight: 500, fontSize: 14 }}>{r.asset}</span>
                                  <StatusPill label={r.status} tone={r.statusTone} />
                                  {isExpandable && <PendingBadge count={badgeCount} />}
                                </span>
                                {(r.sub || r.chainBadge) && (
                                  <span style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                                    {r.sub && <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>{r.sub}</span>}
                                    {r.chainBadge && <ChainBadge kind={r.chainBadge} />}
                                  </span>
                                )}
                              </span>
                            </span>
                            <ActionButton label={r.actionLabel} onClick={() => handleRowAction(r)} />
                          </div>
                          <div style={{ height: 1, background: 'var(--line)', margin: '16px 0' }} />
                          {/* Metrics: USD / (APY) / Balance as labelled columns. */}
                          <div style={{ display: 'grid', gridTemplateColumns: r.apy ? '1fr 1fr 1.4fr' : '1fr 1.4fr', gap: 14 }}>
                            <div style={{ minWidth: 0 }}>
                              <div className='kicker' style={{ fontSize: 11, marginBottom: 5 }}>USD</div>
                              <div className='tabular' style={{ fontSize: 15, color: 'var(--fg)' }}>{r.usd}</div>
                            </div>
                            {r.apy && (
                              <div style={{ minWidth: 0 }}>
                                <div className='kicker' style={{ fontSize: 11, marginBottom: 5 }}>APY</div>
                                <div className='tabular' style={{ fontSize: 15, color: 'var(--dawn-amber)' }}>{r.apy}</div>
                              </div>
                            )}
                            <div style={{ minWidth: 0 }}>
                              <div className='kicker' style={{ fontSize: 11, marginBottom: 5 }}>Balance</div>
                              <div className='tabular' style={{ fontSize: 15, color: 'var(--fg)' }}>
                                {r.balance}
                                {r.balanceSub && (
                                  <span style={{ fontSize: 11, color: 'var(--fg-3)', marginLeft: 6, fontWeight: 400 }}>
                                    {r.balanceSub}
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>

                          {/* sUSD.tel in-flight drawer: pending stakes + unstakes */}
                          {isExpandable && (
                            <>
                              <button
                                type='button'
                                onClick={() => setExpanded((s) => ({ ...s, [r.id]: !s[r.id] }))}
                                style={{
                                  marginTop: 16,
                                  width: '100%',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  gap: 6,
                                  padding: '10px 14px',
                                  borderRadius: 10,
                                  border: '1px solid rgba(243,162,74,0.3)',
                                  background: 'rgba(243,162,74,0.06)',
                                  color: 'var(--dawn-amber)',
                                  fontSize: 12,
                                  fontWeight: 500,
                                  fontFamily: 'inherit',
                                  cursor: 'pointer',
                                }}
                              >
                                {isOpen ? 'Hide' : 'View'} pending {stakeCount > 0 && unstakeCount > 0 ? 'activity' : stakeCount > 0 ? 'stakes' : 'unstakes'}
                                <ExpandChevron open={isOpen} />
                              </button>
                              {isOpen && (
                                <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
                                  {stakeCount > 0 && (
                                    <>
                                      <div className='kicker' style={{ color: 'var(--dawn-amber)' }}>Pending stakes</div>
                                      <ProcessingStakeList stakes={claims} onClaim={onClaim} />
                                    </>
                                  )}
                                  {unstakeCount > 0 && (
                                    <>
                                      <div className='kicker' style={{ color: 'var(--dawn-amber)' }}>Pending unstakes</div>
                                      <PendingUnstakeList
                                        items={unstakeItems}
                                        isSubmitting={unstake.isSubmitting}
                                        onClaim={handleClaimUnstake}
                                        onCancel={handleCancelUnstake}
                                      />
                                    </>
                                  )}
                                </div>
                              )}
                            </>
                          )}
                        </div>
                        )
                      })}
                    </div>
                  )
                })}

                {/* Footer strip: total + positions/strategies · CTA */}
                <div
                  style={{
                    ...cardPanel,
                    padding: 20,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 14,
                    background: 'linear-gradient(90deg, rgba(243,162,74,0.06), rgba(232,64,102,0.03))',
                  }}
                >
                  <div>
                    <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 8 }}>
                      <span style={{ fontSize: 13, color: 'var(--fg-3)' }}>Total</span>
                      <span className='tabular' style={{ fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 600, color: 'var(--fg)' }}>
                        ${grandTotal.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                      </span>
                    </span>
                    <div style={{ fontSize: 12, color: 'var(--fg-3)', marginTop: 4 }}>
                      {allRows.length} positions · {strategyCount} active strategies
                    </div>
                  </div>
                  <GradientButton
                    size='sm'
                    onClick={() => applyCta(router, { route: 'amplify' })}
                    style={{ padding: '12px 18px' }}
                  >
                    Explore Boost Strategies
                  </GradientButton>
                </div>
              </div>
            )}
          </>
        )}

        {withdrawError ? (
          <div
            style={{
              marginTop: 12,
              padding: '8px 12px',
              borderRadius: 8,
              border: '1px solid rgba(220, 38, 38, 0.5)',
              background: 'rgba(127, 29, 29, 0.3)',
              color: 'rgb(252, 165, 165)',
              fontSize: 12,
            }}
          >
            {withdrawError}
          </div>
        ) : null}
      </div>

      <MidnightManageActionsModal
        isOpen={activeManageModal === 'actions'}
        assetLabel={managePosition?.label}
        assetValue={managePosition?.value}
        onClose={handleCloseManageModal}
        onStake={handleGoToStake}
        onUnstake={handleGoToUnstake}
        onBoost={handleGoToBoost}
        onWithdrawSelect={handleOpenWithdrawConfirm}
      />
      <MidnightWithdrawConfirmModal
        isOpen={activeManageModal === 'withdraw'}
        isWithdrawDisabled={!canWithdraw || !!withdrawAmountError}
        isWithdrawing={isWithdrawing}
        withdrawAmount={withdrawAmountInput}
        maxWithdrawAmount={withdrawMaxAmount || '0'}
        withdrawAmountError={withdrawAmountError}
        onClose={handleCloseManageModal}
        onWithdrawAmountChange={(value) => setWithdrawAmountInput(sanitizeWithdrawInput(value))}
        onMaxAmount={() => setWithdrawAmountInput(withdrawMaxAmount || '')}
        onContinue={handleWithdrawConfirm}
      />
    </div>
  )
}
