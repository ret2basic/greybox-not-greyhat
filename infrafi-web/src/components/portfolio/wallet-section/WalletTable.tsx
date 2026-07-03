import Image from 'next/image'
import type { FC } from 'react'
import susdtelIcon from '@/assets/tokens/sUSD.tel_token_icon/sUSD.tel_token_icon.svg'
import usdtelIcon from '@/assets/tokens/USD.tel_token_icon/USD.tel_token_icon.svg'
import type { PortfolioAsset, PortfolioNetwork } from '@/components/portfolio/types'
import { SECTION_GRADIENT_CLASS, SUSD_ICON_BACKGROUND_CLASS } from '@/components/portfolio/wallet-section/constants'

// Portfolio detail table (Figma node 6696:7688). Rows are built from the user's
// real on-chain holdings (see useWalletSectionData.positionRows). infrafi-api
// has no per-venue / per-position feed, so the optional venue/chain/subtitle
// fields stay unused until such a feed exists. The Manage button keeps the real
// manage/withdraw wiring; View rows are read-only.

type PositionStatus = 'idle' | 'available' | 'deployed' | 'locked' | 'minting' | 'processing'

export type PositionRow = {
  id: string
  token: PortfolioAsset
  asset: string
  venue?: string
  chain?: PortfolioNetwork
  subtitle?: string
  claims?: string
  status: PositionStatus
  balance: string
  balanceSub: string
  usd: string
  apy: string
  apyAccent?: boolean
  action: 'manage' | 'view'
}

const TOKEN_ICONS: Record<PortfolioAsset, typeof usdtelIcon> = {
  'USD.tel': usdtelIcon,
  'sUSD.tel': susdtelIcon,
}

const STATUS_STYLE: Record<PositionStatus, { label: string; color: string; bg: string; border: string }> = {
  idle: { label: 'Idle', color: '#8c8a84', bg: 'rgba(140,138,132,0.05)', border: 'rgba(140,138,132,0.3)' },
  available: { label: 'Available', color: '#7bdc8d', bg: 'rgba(123,220,141,0.04)', border: 'rgba(123,220,141,0.2)' },
  deployed: { label: 'Deployed', color: '#7dd1ff', bg: 'rgba(125,209,255,0.04)', border: 'rgba(125,209,255,0.2)' },
  locked: { label: 'Locked', color: '#8c8a84', bg: 'rgba(140,138,132,0.05)', border: 'rgba(140,138,132,0.3)' },
  minting: { label: 'Mint in progress', color: '#7bdcca', bg: 'rgba(123,220,202,0.04)', border: 'rgba(123,220,202,0.2)' },
  processing: { label: 'Processing', color: '#f3a24a', bg: 'rgba(243,162,74,0.08)', border: 'rgba(243,162,74,0.2)' },
}

const GRID_COLS =
  'grid-cols-[minmax(200px,2.4fr)_minmax(120px,1.1fr)_minmax(110px,1.1fr)_minmax(70px,0.8fr)_minmax(70px,0.8fr)_minmax(110px,1fr)]'

function ChainBadge({ chain }: { chain: PortfolioNetwork }) {
  const dot =
    chain === 'Base'
      ? 'bg-[#5b7cff]'
      : 'bg-[linear-gradient(135deg,#9945ff_0%,#14f195_100%)]'
  return (
    <span className='inline-flex h-[16px] items-center gap-[4px] rounded-[15px] border-[0.3px] border-[rgba(251,247,243,0.15)] bg-[#21242c] px-[5px]'>
      <span className={`size-[9px] rounded-full ${dot}`} />
      <span className='text-[9px] leading-[12px] text-white/60'>{chain}</span>
    </span>
  )
}

function StatusPill({ status }: { status: PositionStatus }) {
  const s = STATUS_STYLE[status]
  return (
    <span
      className='inline-flex h-[22px] items-center justify-center rounded-[7px] border-[0.575px] px-[10px] text-[10.56px] leading-[14px] whitespace-nowrap'
      style={{ color: s.color, background: s.bg, borderColor: s.border }}
    >
      {s.label}
    </span>
  )
}

function AssetCell({ row }: { row: PositionRow }) {
  const isSUsd = row.token === 'sUSD.tel'
  return (
    <div className='flex min-w-0 items-center gap-[15px]'>
      <div
        className={`flex size-[28px] shrink-0 items-center justify-center overflow-hidden rounded-[5px] ${isSUsd ? SUSD_ICON_BACKGROUND_CLASS : 'bg-[#171717]'}`}
      >
        <Image src={TOKEN_ICONS[row.token]} alt={row.asset} width={26} height={26} className='shrink-0 rounded-[5px]' />
      </div>
      <div className='flex min-w-0 flex-col gap-[2px]'>
        <span className='truncate text-[12px] font-semibold leading-[20px] text-[#fbf7f3]'>{row.asset}</span>
        {row.subtitle ? (
          <span className='inline-flex items-center gap-[8px]'>
            <span className='text-[11px] leading-[14px] text-[#8c8a84]'>{row.subtitle}</span>
            {row.claims ? (
              <span className='inline-flex h-[16px] items-center rounded-[15px] border-[0.2px] border-[rgba(243,162,74,0.6)] bg-[rgba(243,162,74,0.1)] px-[6px] text-[9px] font-medium leading-[16px] text-[#f3a24a]'>
                {row.claims}
              </span>
            ) : null}
          </span>
        ) : row.chain ? (
          <span className='inline-flex items-center gap-[6px]'>
            {row.venue ? (
              <span className='text-[12px] leading-[20px] tracking-[0.24px] text-[#8c8a84]'>{row.venue}</span>
            ) : null}
            <ChainBadge chain={row.chain} />
          </span>
        ) : null}
      </div>
    </div>
  )
}

export function WalletHeader() {
  return (
    <div
      className={`grid w-full ${GRID_COLS} items-center rounded-t-[20px] border border-[#26272b] bg-[#13151a] px-[24px] py-[17px] text-[10.324px] font-medium uppercase leading-none tracking-[1.45px] text-[#8c8a85]`}
    >
      <span>Asset / Venue</span>
      <span className='text-center'>Status</span>
      <span className='text-center'>Balance</span>
      <span className='text-center'>USD</span>
      <span className='text-center'>APY</span>
      <span className='text-center'>Action</span>
    </div>
  )
}

type WalletRowCardProps = {
  row: PositionRow
  onManage: () => void
}

export const WalletRowCard: FC<WalletRowCardProps> = ({ row, onManage }) => {
  return (
    <div
      className={`grid h-[59px] w-full ${GRID_COLS} items-center border-x border-b border-[#26272b] bg-[#13151a] px-[24px] last:rounded-b-[20px]`}
    >
      <AssetCell row={row} />
      <div className='flex justify-center'>
        <StatusPill status={row.status} />
      </div>
      <div className='flex flex-col items-center gap-[4px] text-center'>
        <span className='text-[12px] font-medium leading-none text-[#fbf7f3]'>{row.balance}</span>
        <span className='text-[10px] font-normal leading-none text-[#8c8a84]'>{row.balanceSub}</span>
      </div>
      <span className='text-center text-[12px] font-medium leading-none text-[#fbf7f3]'>{row.usd}</span>
      <span
        className={`text-center text-[12px] leading-none ${row.apyAccent ? 'font-medium text-[#f3a24a]' : 'font-normal text-[#8c8a84]'}`}
      >
        {row.apy}
      </span>
      <div className='flex justify-center'>
        <button
          type='button'
          onClick={row.action === 'manage' ? onManage : undefined}
          className='inline-flex h-[36px] w-[96px] shrink-0 items-center justify-center rounded-[22.788px] border-[0.76px] border-[#26272b] bg-[#13151a] text-[12px] font-semibold leading-[14.585px] text-white transition-colors hover:border-[#3a3b40]'
        >
          {row.action === 'manage' ? 'Manage' : 'View'}
        </button>
      </div>
    </div>
  )
}

export const WalletMobileRowCard: FC<WalletRowCardProps> = ({ row, onManage }) => {
  return (
    <div className='rounded-[16px] border border-[#26272b] bg-[#13151a] px-[18px] py-[16px]'>
      <div className='flex items-center justify-between gap-[12px]'>
        <AssetCell row={row} />
        <StatusPill status={row.status} />
      </div>
      <div className='mt-[16px] grid grid-cols-3 gap-[12px]'>
        <div className='flex flex-col gap-[2px]'>
          <span className='text-[10px] uppercase tracking-[1px] text-[#8c8a84]'>Balance</span>
          <span className='text-[13px] font-medium text-[#fbf7f3]'>{row.balance}</span>
        </div>
        <div className='flex flex-col gap-[2px]'>
          <span className='text-[10px] uppercase tracking-[1px] text-[#8c8a84]'>USD</span>
          <span className='text-[13px] font-medium text-[#fbf7f3]'>{row.usd}</span>
        </div>
        <div className='flex flex-col gap-[2px]'>
          <span className='text-[10px] uppercase tracking-[1px] text-[#8c8a84]'>APY</span>
          <span className={`text-[13px] font-medium ${row.apyAccent ? 'text-[#f3a24a]' : 'text-[#fbf7f3]'}`}>{row.apy}</span>
        </div>
      </div>
      <button
        type='button'
        onClick={row.action === 'manage' ? onManage : undefined}
        className='mt-[16px] inline-flex h-[36px] w-full items-center justify-center rounded-[22.788px] border-[0.76px] border-[#26272b] bg-[#13151a] text-[12px] font-semibold text-white'
      >
        {row.action === 'manage' ? 'Manage' : 'View'}
      </button>
    </div>
  )
}

export function SectionGradientBar() {
  return <div className={`flex h-[20px] w-full items-center gap-[10px] px-[10px] md:h-[25px] ${SECTION_GRADIENT_CLASS}`} />
}
