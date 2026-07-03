'use client'

import Link from 'next/link'
import Image from 'next/image'
import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { usePathname } from 'next/navigation'
import { useAppKitAccount, useDisconnect } from '@reown/appkit/react'
import logoLight from '@/assets/logo/logo-light.png'
import walletIcon from '@/assets/icons/portfolio/portfolio-deployed/wallet-outline.svg'
import { useNavbar } from '@/hooks/ui/useNavbar'
import { useNav, useProjects, historySharePrice, liveSharePrice } from '@/store'
import { useVault } from '@/store/vault'
import { GradientButton } from '@/components/ui/GradientButton'
import {
  MiniSpark,
  fmt$,
} from '@/components/ui/primitives'
import { ChartModal } from '@/components/dashboard/ChartModal'
import { KPIModal } from '@/components/dashboard/KPIModal'
import type { SourceRect } from '@/components/dashboard/ExpandableCard'
import { RANGE_DAYS, type RangeKey, type ValueKind } from '@/components/dashboard/utils'

// App version shown in the mobile menu footer (mirrors package.json).
const APP_VERSION = '0.3.0'

function InfoDot({ title }: { title: string }) {
  const ref = useRef<HTMLSpanElement>(null)
  const [tip, setTip] = useState<{ left: number; top: number } | null>(null)

  const show = () => {
    const el = ref.current
    if (!el) return
    const r = el.getBoundingClientRect()
    setTip({ left: r.left + r.width / 2, top: r.top })
  }
  const hide = () => setTip(null)

  return (
    <span
      ref={ref}
      aria-label={title}
      tabIndex={0}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
      style={{
        width: 12,
        height: 12,
        borderRadius: 6,
        border: '1px solid var(--fg-3)',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        cursor: 'help',
      }}
    >
      <span className='mono' style={{ fontSize: 8, lineHeight: 1, color: 'var(--fg-3)' }}>i</span>
      {tip &&
        createPortal(
          <span className='dash-info-tip' style={{ left: tip.left, top: tip.top }}>
            {title}
          </span>,
          document.body,
        )}
    </span>
  )
}

// Which nav metric a stat chip expands into — used to derive the real series
// from fetched history.
type StatMetric = 'tvl' | 'apy' | 'price'

// Chart-expansion payload emitted when a stat chip is clicked — drives the
// shared ChartModal (FLIP morph) anchored to the clicked chip's rect, with a
// KPIModal body (summary stats + range tabs + chart + About).
type StatChart = {
  originRect: SourceRect
  title: string
  kicker: string
  metric: StatMetric
  color: string
  kind: ValueKind
  about: string
  // Optional: when the live snapshot value is unavailable (e.g. APY's
  // client-side recompute returns null), leave undefined so the modal falls
  // back to the chart series' last point instead of pinning "Current" to 0.
  currentValue?: number
}

type StatBase = {
  label: string
  value: string
  info: string
  data: number[]
  color: string
}
type StatBarChipProps = StatBase & {
  title: string
  metric: StatMetric
  kind: ValueKind
  about: string
  currentValue?: number
  onExpand: (chart: StatChart) => void
}
// Clickable stat chip — opens a morphing chart expansion of the metric's
// history. Mirrors the StatChipButton design: hover lifts a bg-3 chip with a
// line-strong border and rounded corners.
function StatBarChip({ label, value, info, data, color, title, metric, kind, about, currentValue, onExpand }: StatBarChipProps) {
  const ref = useRef<HTMLButtonElement>(null)
  const [hover, setHover] = useState(false)
  const handleClick = () => {
    const r = ref.current?.getBoundingClientRect()
    if (!r) return
    onExpand({
      originRect: { left: r.left, top: r.top, width: r.width, height: r.height },
      title,
      kicker: label,
      metric,
      color,
      kind,
      about,
      currentValue,
    })
  }
  return (
    <button
      ref={ref}
      type='button'
      onClick={handleClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      aria-label={`Open ${label} chart`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        padding: '4px 8px',
        background: hover ? 'var(--bg-3)' : 'transparent',
        border: `1px solid ${hover ? 'var(--line-strong)' : 'transparent'}`,
        borderRadius: 8,
        color: 'inherit',
        cursor: 'pointer',
        transition: 'background 160ms ease, border-color 160ms ease',
        font: 'inherit',
      }}
    >
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <span
          className='mono'
          style={{
            fontSize: 10,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            color: 'var(--fg-3)',
          }}
        >
          {label}
        </span>
        <InfoDot title={info} />
        <span
          className='tabular'
          style={{ fontWeight: 500, fontSize: 14, color: 'var(--fg)', letterSpacing: '-0.01em' }}
        >
          {value}
        </span>
      </span>
      <MiniSpark data={data} width={36} height={16} color={color} fill={false} />
    </button>
  )
}

// Live cumulative-yield ticker — extrapolates `seedYield` forward at apy/sec
// since mount. Cents change at ~$0.07/s on real data, so 10 fps is plenty;
// using setInterval (instead of rAF) keeps the main thread free for click
// dispatch, which matters when other parts of the page (e.g. the Reserves
// globe) are also running rAF loops.
function CumulativeYield({ seedYield, apy }: { seedYield: number; apy: number }) {
  const [val, setVal] = useState(seedYield)
  useEffect(() => {
    const t0 = performance.now()
    const ratePerMs = (Math.max(seedYield, 1) * apy) / (365.25 * 24 * 60 * 60 * 1000)
    const id = setInterval(() => {
      setVal(seedYield + ratePerMs * (performance.now() - t0))
    }, 100)
    return () => clearInterval(id)
  }, [seedYield, apy])
  const whole = Math.floor(val)
  const cents = Math.floor((val - whole) * 100)
    .toString()
    .padStart(2, '0')
  return (
    <span
      className='tabular'
      style={{
        display: 'inline-flex',
        alignItems: 'baseline',
        gap: 6,
        fontSize: 11,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
      }}
    >
      <span style={{ color: 'var(--fg-3)' }}>CUMULATIVE YIELD:</span>
      <span style={{ color: 'var(--fg-2)', fontVariantNumeric: 'tabular-nums' }}>
        ${whole.toLocaleString()}.{cents}
      </span>
    </span>
  )
}

function NotifBell() {
  return (
    <button
      type='button'
      aria-label='Notifications'
      style={{
        position: 'relative',
        width: 32,
        height: 32,
        borderRadius: 8,
        border: '1px solid var(--line-strong)',
        background: 'var(--bg-1)',
        color: 'var(--fg-2)',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        flexShrink: 0,
      }}
    >
      <svg width='15' height='15' viewBox='0 0 24 24' fill='none' aria-hidden>
        <path
          d='M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9'
          stroke='currentColor'
          strokeWidth='1.6'
          strokeLinecap='round'
          strokeLinejoin='round'
        />
        <path
          d='M13.73 21a2 2 0 0 1-3.46 0'
          stroke='currentColor'
          strokeWidth='1.6'
          strokeLinecap='round'
          strokeLinejoin='round'
        />
      </svg>
      <span
        style={{
          position: 'absolute',
          top: 6,
          right: 6,
          width: 7,
          height: 7,
          borderRadius: 2,
          background: '#F3A24A',
        }}
      />
    </button>
  )
}

type WalletButtonProps = {
  isConnected: boolean
  shortAddress: string
  onConnect: () => void
  onAccount: () => void
}
function WalletButton({ isConnected, shortAddress, onConnect, onAccount }: WalletButtonProps) {
  if (!isConnected) {
    return (
      <GradientButton size='sm' onClick={onConnect} style={{ padding: '8px 16px' }}>
        Connect wallet
      </GradientButton>
    )
  }
  return (
    <button
      type='button'
      onClick={onAccount}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        height: 30,
        padding: '6px 12px 6px 6px',
        background: 'var(--bg-1)',
        border: '1px solid var(--line-strong)',
        borderRadius: 999,
        color: 'var(--fg)',
        lineHeight: 1,
      }}
    >
      <span
        style={{
          width: 18,
          height: 18,
          borderRadius: '50%',
          background: 'linear-gradient(135deg, #6B3F8F, #C73E7C)',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 9,
          fontFamily: 'var(--font-mono)',
          color: '#fff',
          flex: '0 0 18px',
        }}
      >
        ◇
      </span>
      <span
        className='mono'
        style={{
          fontSize: 9.5,
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          color: 'var(--fg-3)',
        }}
      >
        Wallet
      </span>
      <span style={{ width: 1, height: 12, background: 'var(--line-strong)' }} />
      <span
        className='mono tabular'
        style={{ fontSize: 11, letterSpacing: '0.04em', color: 'var(--fg)' }}
      >
        {shortAddress}
      </span>
    </button>
  )
}

export const TopNav = () => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const [isSmallScreen, setIsSmallScreen] = useState(false)
  const [isCompactScreen, setIsCompactScreen] = useState(false)
  const [isTinyScreen, setIsTinyScreen] = useState(false)
  const [copied, setCopied] = useState(false)
  const [chart, setChart] = useState<StatChart | null>(null)
  const [chartRange, setChartRange] = useState<RangeKey>('30D')
  const pathname = usePathname()
  const {
    navigationItems,
    isWalletConnected,
    walletLabel,
    connectedWalletShortLabel,
    connectedWalletIcon,
    handleConnectWalletClick,
    handleOpenAccountClick,
  } = useNavbar()
  const { address } = useAppKitAccount()
  const { disconnect } = useDisconnect()
  const { nav, navHistory, navRangeHistory, fetchNav, fetchNavHistory, fetchNavRangeHistory } = useNav()
  const { projects, projectMetrics, fetchProjects, fetchProjectMetrics } = useProjects()
  const dryPowder = useVault((s) => s.dryPowder)
  const fetchDryPowder = useVault((s) => s.fetchDryPowder)

  const handleCopyAddress = () => {
    if (!address) return
    try {
      void navigator.clipboard?.writeText(address)
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    } catch {
      /* clipboard unavailable — no-op */
    }
  }

  useEffect(() => {
    fetchNav()
    fetchNavHistory(30)
  }, [fetchNav, fetchNavHistory])

  useEffect(() => {
    fetchProjects()
    fetchProjectMetrics()
    fetchDryPowder()
  }, [fetchProjects, fetchProjectMetrics, fetchDryPowder])

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
    const media = window.matchMedia('(max-width: 449px)')
    const sync = () => setIsTinyScreen(media.matches)
    sync()
    media.addEventListener('change', sync)
    return () => media.removeEventListener('change', sync)
  }, [])

  useEffect(() => {
    if (!isSmallScreen) {
      setIsMobileMenuOpen(false)
      document.body.style.overflow = ''
      return
    }
    if (!isMobileMenuOpen) {
      document.body.style.overflow = ''
      return
    }
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = ''
    }
  }, [isMobileMenuOpen, isSmallScreen])

  useEffect(() => {
    setIsMobileMenuOpen(false)
  }, [pathname])

  // Pull real history for the expanded chip's selected range. Kept in the
  // store's navRangeHistory slice so it never disturbs the header sparklines.
  useEffect(() => {
    if (!chart) return
    fetchNavRangeHistory(RANGE_DAYS[chartRange])
  }, [chart, chartRange, fetchNavRangeHistory])

  // Real series for the expansion, derived from the fetched range history.
  const chartData = useMemo(() => {
    if (!chart) return []
    switch (chart.metric) {
      case 'tvl':
        return navRangeHistory.map((h) => h.net_asset_value)
      case 'apy':
        // Apply the same utilization discount as the header chip
        // (deployed capital / total capital) so the chart matches the chip's
        // "effective APY" metric rather than the raw deployed-only yield.
        return navRangeHistory.map((h) => h.apy * h.utilization_rate * 100)
      case 'price':
        return navRangeHistory.map(historySharePrice)
    }
  }, [chart, navRangeHistory])

  const chartDates = useMemo(
    () => (chart ? navRangeHistory.map((h) => h.date) : []),
    [chart, navRangeHistory],
  )

  const openChart = (next: StatChart) => {
    setChartRange('30D')
    setChart(next)
  }

  // Live stat values and sparklines from real API history.
  const tvlRaw = nav?.net_asset_value_raw ?? null
  const tvlValue = tvlRaw !== null ? fmt$(tvlRaw) : '—'
  const apyRaw = useMemo<number | null>(() => {
    const totalDeployed = projectMetrics.reduce((s, m) => s + m.deployed_value, 0)
    const activeIds = new Set(projects.filter((p) => p.status === 'ACTIVE').map((p) => p.id))
    const active = projectMetrics.filter((m) => activeIds.has(m.project_id))
    const activeDeployed = active.reduce((s, m) => s + m.deployed_value, 0)
    if (activeDeployed <= 0) return null
    const weighted = active.reduce((s, m) => s + m.deployed_value * m.yield_rate, 0) / activeDeployed
    const totalCapital = totalDeployed + (dryPowder ?? 0)
    const utilization = totalCapital > 0 ? totalDeployed / totalCapital : 0
    return weighted * utilization * 100
  }, [projects, projectMetrics, dryPowder])
  const tvlSpark = navHistory.map((h) => h.net_asset_value)
  const apySpark = navHistory.map((h) => h.apy * h.utilization_rate * 100)
  // Fall back to the latest history point when the client-side recompute is
  // unavailable (no active deployed projects yet) so the pill matches the
  // expanded modal's "Current" instead of showing '—'.
  const apyCurrent = apyRaw ?? (apySpark.length ? apySpark[apySpark.length - 1] : null)
  const apyValue = apyCurrent !== null ? `${apyCurrent.toFixed(1)}%` : '—'
  const priceRaw = nav ? liveSharePrice(nav) : null
  const priceValue = priceRaw !== null && priceRaw > 0 ? `$${priceRaw.toFixed(3)}` : '—'
  const priceSpark = navHistory.map(historySharePrice)

  const mobileMenu = isSmallScreen && isMobileMenuOpen && typeof document !== 'undefined'
    ? createPortal(
        <>
          <button
            type='button'
            aria-label='Close mobile menu'
            onClick={() => setIsMobileMenuOpen(false)}
            style={{
              position: 'fixed',
              inset: 0,
              border: 'none',
              background: 'rgba(5, 3, 10, 0.56)',
              zIndex: 20000,
              cursor: 'pointer',
            }}
          />
          <div
            style={{
              position: 'fixed',
              top: 0,
              right: 0,
              bottom: 0,
              width: 'min(92vw, 388px)',
              background: '#08060F',
              borderLeft: '1px solid var(--line)',
              padding: '16px 18px 20px',
              zIndex: 20001,
              display: 'flex',
              flexDirection: 'column',
              gap: 18,
              overflowY: 'auto',
              boxShadow: '-14px 0 40px rgba(0, 0, 0, 0.55)',
            }}
          >
            {/* Header: brand + close */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Image
                src={logoLight}
                alt='DAWN'
                width={671}
                height={146}
                style={{ height: 26, width: 'auto', display: 'block' }}
              />
              <span
                className='mono'
                style={{
                  fontSize: 9.5,
                  letterSpacing: '0.2em',
                  textTransform: 'uppercase',
                  fontWeight: 600,
                  background: 'var(--dawn-gradient-h)',
                  WebkitBackgroundClip: 'text',
                  backgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  color: 'transparent',
                  padding: '3px 8px',
                  border: '1px solid rgba(243, 162, 74, 0.35)',
                  borderRadius: 4,
                }}
              >
                InfraFi
              </span>
              <div style={{ flex: 1 }} />
              <button
                type='button'
                aria-label='Close menu'
                onClick={() => setIsMobileMenuOpen(false)}
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 8,
                  border: '1px solid var(--line-strong)',
                  background: 'var(--bg-1)',
                  color: 'var(--fg)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  flexShrink: 0,
                }}
              >
                <svg viewBox='0 0 24 24' width='15' height='15' fill='none' aria-hidden>
                  <path d='M6 6l12 12M18 6L6 18' stroke='currentColor' strokeWidth='1.8' strokeLinecap='round' />
                </svg>
              </button>
            </div>

            {/* Wallet card */}
            {isWalletConnected ? (
              <div
                style={{
                  border: '1px solid var(--line-strong)',
                  background: 'rgba(255, 255, 255, 0.02)',
                  borderRadius: 14,
                  padding: 14,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 12,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
                  <span
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: '50%',
                      overflow: 'hidden',
                      background: 'linear-gradient(135deg, #6B3F8F, #C73E7C)',
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    {connectedWalletIcon ? (
                      <Image src={connectedWalletIcon} alt='' width={36} height={36} style={{ width: 36, height: 36, objectFit: 'cover' }} />
                    ) : (
                      <Image src={walletIcon} alt='' width={16} height={16} style={{ opacity: 0.9 }} />
                    )}
                  </span>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                    <span
                      className='mono'
                      style={{ fontSize: 10, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--fg-3)' }}
                    >
                      Connected
                    </span>
                    <span
                      className='mono tabular'
                      style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg)', letterSpacing: '0.02em' }}
                    >
                      {walletLabel}
                    </span>
                  </div>
                  <div style={{ flex: 1 }} />
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 5,
                      padding: '3px 8px',
                      borderRadius: 999,
                      border: '1px solid rgba(74, 222, 128, 0.3)',
                      background: 'rgba(74, 222, 128, 0.1)',
                      fontSize: 11,
                      color: '#6EE7A0',
                      flexShrink: 0,
                    }}
                  >
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#4ADE80' }} />
                    Live
                  </span>
                </div>
                <div style={{ display: 'flex', gap: 10 }}>
                  <button
                    type='button'
                    onClick={handleCopyAddress}
                    style={{
                      flex: 1,
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 7,
                      minHeight: 40,
                      borderRadius: 10,
                      border: '1px solid var(--line-strong)',
                      background: 'var(--bg-1)',
                      color: 'var(--fg)',
                      fontSize: 13,
                      cursor: 'pointer',
                    }}
                  >
                    <svg viewBox='0 0 24 24' width='15' height='15' fill='none' aria-hidden>
                      <rect x='9' y='9' width='11' height='11' rx='2' stroke='currentColor' strokeWidth='1.6' />
                      <path d='M5 15V5a2 2 0 0 1 2-2h10' stroke='currentColor' strokeWidth='1.6' strokeLinecap='round' />
                    </svg>
                    {copied ? 'Copied' : 'Copy address'}
                  </button>
                  <button
                    type='button'
                    onClick={() => {
                      setIsMobileMenuOpen(false)
                      void disconnect()
                    }}
                    style={{
                      flex: 1,
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 7,
                      minHeight: 40,
                      borderRadius: 10,
                      border: '1px solid rgba(232, 64, 102, 0.4)',
                      background: 'rgba(232, 64, 102, 0.12)',
                      color: '#F26d8a',
                      fontSize: 13,
                      cursor: 'pointer',
                    }}
                  >
                    <svg viewBox='0 0 24 24' width='15' height='15' fill='none' aria-hidden>
                      <path d='M15 17l5-5-5-5M20 12H9M9 21H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3' stroke='currentColor' strokeWidth='1.6' strokeLinecap='round' strokeLinejoin='round' />
                    </svg>
                    Disconnect
                  </button>
                </div>
              </div>
            ) : (
              <GradientButton
                onClick={() => {
                  setIsMobileMenuOpen(false)
                  handleConnectWalletClick()
                }}
                fullWidth
                style={{ minHeight: 44 }}
              >
                Connect wallet
              </GradientButton>
            )}

            {/* Navigate */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div className='mono' style={{ fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--fg-3)', marginBottom: 6 }}>
                Navigate
              </div>
              {navigationItems.map((r) => {
                const active = !r.isExternal && pathname === r.href
                const rowStyle = {
                  display: 'flex',
                  alignItems: 'center',
                  width: '100%',
                  minHeight: active ? 50 : 44,
                  borderRadius: active ? 12 : 0,
                  border: active ? '1px solid rgba(243, 162, 74, 0.5)' : '1px solid transparent',
                  background: active ? 'rgba(243, 162, 74, 0.08)' : 'transparent',
                  color: active ? 'var(--fg)' : 'var(--fg-2)',
                  padding: active ? '0 16px' : '0 4px',
                  fontSize: 15,
                  fontWeight: active ? 600 : 400,
                } as const
                const content = (
                  <span style={rowStyle}>
                    <span>{r.label}{r.isExternal && ' ↗'}</span>
                    <span style={{ flex: 1 }} />
                    {active && <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#F3A24A' }} />}
                  </span>
                )
                return r.isExternal ? (
                  <a
                    key={r.href}
                    href={r.href}
                    target='_blank'
                    rel='noreferrer'
                    onClick={() => setIsMobileMenuOpen(false)}
                    style={{ display: 'block', width: '100%' }}
                  >
                    {content}
                  </a>
                ) : (
                  <Link
                    key={r.href}
                    href={r.href}
                    onClick={() => setIsMobileMenuOpen(false)}
                    style={{ display: 'block', width: '100%' }}
                  >
                    {content}
                  </Link>
                )
              })}
            </div>

            {/* More */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div className='mono' style={{ fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--fg-3)', marginBottom: 6 }}>
                More
              </div>
              <button type='button' className='topnav-more-row'>
                <span>Notifications</span>
                <span style={{ flex: 1 }} />
                <span
                  className='mono'
                  style={{
                    minWidth: 18,
                    height: 18,
                    padding: '0 5px',
                    borderRadius: 5,
                    background: 'rgba(243, 162, 74, 0.16)',
                    border: '1px solid rgba(243, 162, 74, 0.32)',
                    color: '#F4B57F',
                    fontSize: 11,
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  3
                </span>
              </button>
              <a
                href='https://dawninternet.com/terms'
                target='_blank'
                rel='noreferrer'
                className='topnav-more-row'
                onClick={() => setIsMobileMenuOpen(false)}
              >
                <span>Terms &amp; Conditions</span>
              </a>
              <a
                href='https://dawninternet.com/privacy'
                target='_blank'
                rel='noreferrer'
                className='topnav-more-row'
                onClick={() => setIsMobileMenuOpen(false)}
              >
                <span>Privacy Policy</span>
              </a>
            </div>

            <div style={{ flex: 1 }} />
            <div className='mono' style={{ fontSize: 11, letterSpacing: '0.1em', color: 'var(--fg-4)' }}>
              V{APP_VERSION}
            </div>
          </div>
        </>,
        document.body,
      )
    : null

  return (
    <header
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 50,
        background: 'rgba(11, 8, 20, 0.78)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        borderBottom: '1px solid var(--line)',
      }}
    >
      <div
        className='app-container'
        style={{
          padding: isSmallScreen ? '16px 16px' : isCompactScreen ? '16px 20px' : '16px 32px',
          display: 'flex',
          alignItems: 'center',
          gap: 18,
          minWidth: 0,
        }}
      >
        {/* Logo */}
        <Link
          href='/buy-stake'
          style={{ display: 'inline-flex', alignItems: 'center', flexShrink: 0 }}
          aria-label='InfraFi home'
        >
          <Image
            src={logoLight}
            alt='DAWN'
            priority
            width={671}
            height={146}
            style={{ height: 28, width: 'auto', display: 'block' }}
          />
        </Link>

        {/* InfraFi sub-brand — gradient text inside an orange-tinted border */}
        <span
          className='mono'
          style={{
            fontSize: 10.5,
            letterSpacing: '0.2em',
            textTransform: 'uppercase',
            fontWeight: 600,
            background: 'var(--dawn-gradient-h)',
            WebkitBackgroundClip: 'text',
            backgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            color: 'transparent',
            padding: '3px 9px',
            border: '1px solid rgba(243, 162, 74, 0.35)',
            borderRadius: 4,
          }}
        >
          InfraFi
        </span>

        {/* Nav links */}
        <nav
          style={{
            display: isSmallScreen ? 'none' : 'flex',
            gap: isCompactScreen ? 0 : 4,
            marginLeft: 8,
            minWidth: 0,
            flexShrink: 1,
          }}
        >
          {navigationItems.map((r) => {
            const active = !r.isExternal && pathname === r.href
            const link = (
              <span
                style={{
                  position: 'relative',
                  display: 'inline-block',
                  padding: isCompactScreen ? '10px 8px' : '10px 12px',
                  fontSize: isCompactScreen ? 12 : 13,
                  fontWeight: active ? 500 : 400,
                  color: active ? 'var(--fg)' : 'var(--fg-3)',
                  letterSpacing: '-0.005em',
                  whiteSpace: 'nowrap',
                  transition: 'color 160ms',
                }}
              >
                {r.label}
                {r.isExternal && ' ↗'}
                {active && (
                  <span
                    style={{
                      position: 'absolute',
                      left: 12,
                      right: 12,
                      bottom: -17,
                      height: 1.5,
                      background: 'var(--dawn-gradient-h)',
                    }}
                  />
                )}
              </span>
            )
            return r.isExternal ? (
              <a key={r.href} href={r.href} target='_blank' rel='noreferrer' className='hover-fg-2'>
                {link}
              </a>
            ) : (
              <Link key={r.href} href={r.href} className='hover-fg-2'>
                {link}
              </Link>
            )
          })}
        </nav>

        <div style={{ flex: 1 }} />

        {!isSmallScreen && (
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 18 }}>
            {isWalletConnected && <NotifBell />}
            <WalletConnectButton
              isConnected={isWalletConnected}
              onConnect={handleConnectWalletClick}
              onAccount={handleOpenAccountClick}
            />
          </div>
        )}

        {isSmallScreen && (
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            {isTinyScreen ? null : isWalletConnected ? (
              <button
                type='button'
                onClick={handleOpenAccountClick}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 7,
                  height: 34,
                  padding: '0 12px',
                  background: 'var(--bg-1)',
                  border: '1px solid var(--line-strong)',
                  borderRadius: 999,
                  color: 'var(--fg)',
                  cursor: 'pointer',
                  maxWidth: '46vw',
                }}
              >
                <span
                  style={{
                    width: 18,
                    height: 18,
                    borderRadius: '50%',
                    overflow: 'hidden',
                    background: 'linear-gradient(135deg, #6B3F8F, #C73E7C)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flex: '0 0 18px',
                  }}
                >
                  {connectedWalletIcon ? (
                    <Image src={connectedWalletIcon} alt='' width={18} height={18} style={{ width: 18, height: 18, objectFit: 'cover' }} />
                  ) : (
                    <Image src={walletIcon} alt='' width={11} height={11} style={{ opacity: 0.9 }} />
                  )}
                </span>
                <span
                  className='mono tabular'
                  style={{ fontSize: 11, letterSpacing: '0.04em', color: 'var(--fg)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                >
                  {connectedWalletShortLabel || walletLabel}
                </span>
              </button>
            ) : (
              <GradientButton size='sm' onClick={handleConnectWalletClick} style={{ padding: '8px 14px' }}>
                Connect
              </GradientButton>
            )}
            <button
              type='button'
              aria-label='Toggle menu'
              aria-expanded={isMobileMenuOpen}
              onClick={() => setIsMobileMenuOpen((prev) => !prev)}
              style={{
                width: 34,
                height: 34,
                borderRadius: 8,
                border: '1px solid var(--line-strong)',
                background: 'var(--bg-1)',
                color: 'var(--fg)',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
              }}
            >
              <span style={{ position: 'relative', width: 14, height: 12, display: 'block' }}>
                <span style={{ position: 'absolute', left: 0, top: 0, width: 14, height: 1.5, background: 'currentColor', transform: isMobileMenuOpen ? 'translateY(5px) rotate(45deg)' : 'none', transition: 'transform 160ms ease' }} />
                <span style={{ position: 'absolute', left: 0, top: 5, width: 14, height: 1.5, background: 'currentColor', opacity: isMobileMenuOpen ? 0 : 1, transition: 'opacity 160ms ease' }} />
                <span style={{ position: 'absolute', left: 0, top: 10, width: 14, height: 1.5, background: 'currentColor', transform: isMobileMenuOpen ? 'translateY(-5px) rotate(-45deg)' : 'none', transition: 'transform 160ms ease' }} />
              </span>
            </button>
          </div>
        )}
      </div>

      {/* Status bar: left = TVL/APY/price stat pill, right = cumulative yield */}
      <div
        className='app-container'
        style={{
          padding: isCompactScreen ? '8px 20px' : '8px 32px',
          borderTop: '1px solid var(--line)',
          display: isSmallScreen ? 'none' : 'flex',
          alignItems: 'center',
          gap: 16,
        }}
      >
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '2px 7px',
            background: 'rgba(255, 255, 255, 0.02)',
            border: '1px solid var(--line-strong)',
            borderRadius: 999,
          }}
        >
          <StatBarChip
            label='TVL'
            value={tvlValue}
            info='Total value locked across the USD.tel vault — capital deployed to fund telecom infrastructure.'
            data={tvlSpark}
            color='#F3A24A'
            title='Total value locked'
            metric='tvl'
            kind='$$'
            about='Aggregate USD value of all assets held in the sUSD.tel InfraFi vault.'
            currentValue={tvlRaw ?? 0}
            onExpand={openChart}
          />
          <span style={{ width: 1, height: 16, background: 'var(--line-strong)' }} />
          <StatBarChip
            label='APY'
            value={apyValue}
            info='Trailing 30-day annualized yield on sUSD.tel from telecom revenue.'
            data={apySpark}
            color='#ED7C5B'
            title='Annual percentage yield'
            metric='apy'
            kind='%'
            about='Annualized yield on sUSD.tel generated by telecom infrastructure revenue.'
            currentValue={apyRaw ?? undefined}
            onExpand={openChart}
          />
          <span style={{ width: 1, height: 16, background: 'var(--line-strong)' }} />
          <StatBarChip
            label='sUSD.tel'
            value={priceValue}
            info='Current NAV (mint/redeem price) of sUSD.tel. Increases over time as yield accrues.'
            data={priceSpark}
            color='#E84066'
            title='sUSD.tel price'
            metric='price'
            kind='$'
            about='Current NAV (mint/redeem price) of sUSD.tel. Increases over time as yield accrues.'
            currentValue={priceRaw ?? 0}
            onExpand={openChart}
          />
        </span>

        <div style={{ flex: 1 }} />

        <CumulativeYield
          seedYield={nav?.cumulative_yield ?? 0}
          apy={nav?.apy ?? 0}
        />
      </div>

      {/* Mobile stats strip — horizontally scrollable TVL / APY / sUSD.tel pills
          (Figma 6605-4819 nav mobile). Shown only when the desktop status bar
          above is hidden, i.e. at ≤1024px (isSmallScreen). Anything wider keeps
          the desktop bar so we don't end up with two stacked status rows. */}
      {isSmallScreen && (
        <div
          className='topnav-mobile-stats'
          style={{
            display: 'flex',
            gap: 8,
            padding: '8px 16px',
            borderTop: '1px solid var(--line)',
            overflowX: 'auto',
          }}
        >
          <MobileStatPill
            label='TVL'
            value={tvlValue}
            info='Total value locked across the USD.tel vault — capital deployed to fund telecom infrastructure.'
            data={tvlSpark}
            color='#F3A24A'
            title='Total value locked'
            metric='tvl'
            kind='$$'
            about='Aggregate USD value of all assets held in the sUSD.tel InfraFi vault.'
            currentValue={tvlRaw ?? 0}
            onExpand={openChart}
          />
          <MobileStatPill
            label='APY'
            value={apyValue}
            info='Trailing 30-day annualized yield on sUSD.tel from telecom revenue.'
            data={apySpark}
            color='#ED7C5B'
            title='Annual percentage yield'
            metric='apy'
            kind='%'
            about='Annualized yield on sUSD.tel generated by telecom infrastructure revenue.'
            currentValue={apyRaw ?? undefined}
            onExpand={openChart}
          />
          <MobileStatPill
            label='sUSD.tel'
            value={priceValue}
            info='Current NAV (mint/redeem price) of sUSD.tel. Increases over time as yield accrues.'
            data={priceSpark}
            color='#E84066'
            title='sUSD.tel price'
            metric='price'
            kind='$'
            about='Current NAV (mint/redeem price) of sUSD.tel. Increases over time as yield accrues.'
            currentValue={priceRaw ?? 0}
            onExpand={openChart}
          />
          {/* Cumulative yield — same ticker as the desktop status bar, shown
              as the last pill in the scrollable strip (right after sUSD.tel). */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '6px 11px',
              flexShrink: 0,
              whiteSpace: 'nowrap',
            }}
          >
            <CumulativeYield
              seedYield={nav?.cumulative_yield ?? 0}
              apy={nav?.apy ?? 0}
            />
          </div>
        </div>
      )}

      <ChartModal
        open={!!chart}
        onClose={() => setChart(null)}
        title={chart?.title ?? ''}
        kicker={chart?.kicker ?? ''}
        originRect={chart?.originRect ?? null}
      >
        {chart && (
          <KPIModal
            data={chartData}
            dates={chartDates}
            range={chartRange}
            onRangeChange={setChartRange}
            color={chart.color}
            kind={chart.kind}
            about={chart.about}
            currentValue={chart.currentValue}
          />
        )}
      </ChartModal>

      {mobileMenu}
    </header>
  )
}

// One stat as a self-contained rounded pill for the mobile stats strip.
// Clickable — opens the same morphing chart expansion as the desktop chips
// (FLIP morph anchored to the pill's rect, KPIModal body).
function MobileStatPill({
  label,
  value,
  info,
  data,
  color,
  title,
  metric,
  kind,
  about,
  currentValue,
  onExpand,
}: StatBarChipProps) {
  const ref = useRef<HTMLButtonElement>(null)
  const handleClick = () => {
    const r = ref.current?.getBoundingClientRect()
    if (!r) return
    onExpand({
      originRect: { left: r.left, top: r.top, width: r.width, height: r.height },
      title,
      kicker: label,
      metric,
      color,
      kind,
      about,
      currentValue,
    })
  }
  return (
    <button
      ref={ref}
      type='button'
      onClick={handleClick}
      aria-label={`Open ${label} chart`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 7,
        padding: '6px 11px',
        background: 'rgba(255, 255, 255, 0.02)',
        border: '1px solid var(--line-strong)',
        borderRadius: 999,
        flexShrink: 0,
        color: 'inherit',
        cursor: 'pointer',
        font: 'inherit',
      }}
    >
      <span
        className='mono'
        style={{ fontSize: 9.5, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--fg-3)' }}
      >
        {label}
      </span>
      <InfoDot title={info} />
      <span
        className='tabular'
        style={{ fontWeight: 500, fontSize: 13, color: 'var(--fg)', letterSpacing: '-0.01em' }}
      >
        {value}
      </span>
      <MiniSpark data={data} width={32} height={14} color={color} fill={false} />
    </button>
  )
}

// Pulls the existing useNavbar walletLabel and reformats into the design's 6+…+4 shape.
function WalletConnectButton({
  isConnected,
  onConnect,
  onAccount,
}: {
  isConnected: boolean
  onConnect: () => void
  onAccount: () => void
}) {
  const { walletLabel } = useNavbar()
  // useNavbar returns "0x1234...abcd" with three dots; replace with unicode ellipsis
  const shortAddress = isConnected ? walletLabel.replace('...', '…') : ''
  return (
    <WalletButton
      isConnected={isConnected}
      shortAddress={shortAddress}
      onConnect={onConnect}
      onAccount={onAccount}
    />
  )
}
