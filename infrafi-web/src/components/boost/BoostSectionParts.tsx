'use client'

import { Fragment, type FC, type ReactNode } from 'react'
import Image from 'next/image'
import arrowRightWhiteIcon from '@/assets/icons/arrow-right-white.svg'
import { STRATEGY_GRADIENT_CLASS } from './constants'
import { NETWORK_ICONS, PROTOCOL_ICONS, resolveFallbackTokenIcon } from './data'
import type {
  ColumnHeader,
  BoostNetwork,
  RowVisualProps,
  SectionHeaderProps,
  SectionStat,
  StrategyStatus,
  UserPosition,
} from './types'

const SectionStatBlock: FC<SectionStat> = ({ label, value }) => {
  return (
    <div className='flex w-auto items-center gap-[4px] md:w-[88px] md:flex-col md:items-start md:gap-0'>
      <span className='whitespace-nowrap text-[12px] font-normal leading-[15px] text-[#8c8a84] md:text-[12px] md:text-white/50'>
        {label}:
      </span>
      <span className='whitespace-nowrap text-[12px] font-semibold leading-[15px] text-white'>{value}</span>
    </div>
  )
}

export const SectionHeader: FC<SectionHeaderProps> = ({
  icon,
  title,
  description,
  stats,
  marginBottomClass = 'mb-[14px] md:mb-[18px]',
}) => {
  return (
    <div className={`${marginBottomClass ?? ''} flex flex-col gap-[40px] md:flex-row md:items-start md:justify-between md:gap-0`.trim()}>
      <div className='flex max-w-[610px] flex-col gap-[9px]'>
        <div className='flex items-center gap-[10px]'>
          <Image src={icon} alt='' width={15} height={15} className='size-[15px]' />
          <h2 className='text-[16px] font-semibold leading-[20px] text-white'>{title}</h2>
        </div>
        <p className='text-[13px] font-normal leading-[18px] text-white/50 md:text-[12px] md:leading-[16.8px]'>{description}</p>
      </div>

      <div className='flex flex-nowrap items-center gap-[15px] self-start md:self-auto'>
        {stats.map((stat, index) => (
          <Fragment key={stat.label}>
            {index > 0 && <div className='h-[12px] w-px bg-white/20 md:h-[38px]' />}
            <SectionStatBlock label={stat.label} value={stat.value} />
          </Fragment>
        ))}
      </div>
    </div>
  )
}

type SectionColumnHeadersProps = {
  columns: ColumnHeader[]
}

export const SectionColumnHeaders: FC<SectionColumnHeadersProps> = ({ columns }) => {
  return (
    <div className='hidden items-center justify-between border-b border-white/6 px-[17px] pb-[12px] md:flex'>
      {columns.map((column) => (
        <span
          key={column.label}
          className={`text-[12px] font-normal leading-[20px] tracking-[0.24px] text-[#999999] ${column.widthClass} ${
            column.alignClass ?? ''
          }`}
        >
          {column.label}
        </span>
      ))}
    </div>
  )
}

export const GradientBar: FC = () => {
  return <div className={`mb-[10px] flex h-[20px] w-full items-center px-0 md:mb-[5px] md:h-[25px] md:px-[10px] ${STRATEGY_GRADIENT_CLASS}`} />
}

type ProtocolMetaProps = {
  protocol: string
  network: BoostNetwork
}

export const ProtocolMeta: FC<ProtocolMetaProps> = ({ protocol, network }) => {
  const NetworkIcon = NETWORK_ICONS[network]

  return (
    <div className='flex items-center gap-[4px]'>
      <span className='text-[11px] font-normal leading-[15px] tracking-[0.2px] text-white/50 md:text-[12px] md:leading-[20px] md:tracking-[0.24px]'>
        {protocol}
      </span>
      <div className='flex h-[16px] w-[52px] items-center justify-center rounded-[15px] bg-[#2B2B2B] md:h-[18px] md:w-[56px]'>
        <span className='flex items-center gap-[4px]'>
          <span className='flex size-[10px] shrink-0 items-center justify-center [&_img]:size-[10px] [&_img]:object-contain [&_svg]:size-[10px]'>
            <NetworkIcon />
          </span>
          <span className='text-[10px] font-normal leading-[14px] text-white/60'>{network}</span>
        </span>
      </div>
    </div>
  )
}

export const RowVisual: FC<RowVisualProps> = ({ protocol, title }) => {
  const src = PROTOCOL_ICONS[protocol] ?? resolveFallbackTokenIcon(title)

  return (
    <Image
      src={src}
      alt={protocol}
      width={32}
      height={32}
      className='size-[32px] shrink-0 rounded-[5px] object-cover'
    />
  )
}

// --- Mobile strategy card (Figma 6611-10020) ---------------------------------
// On mobile each table row collapses into a standalone card: protocol header +
// Enter button on top, a divider, then a 2-column grid of labelled metrics.

type MobileStrategyCardProps = {
  protocol: string
  title: string
  network: BoostNetwork
  children: ReactNode
  status?: StrategyStatus
  position?: UserPosition
  href?: string
}

export const MobileStrategyCard: FC<MobileStrategyCardProps> = ({
  protocol,
  title,
  network,
  children,
  status = 'live',
  position,
  href,
}) => {
  return (
    <div className='rounded-[20px] border border-[#26272B] bg-[#13151A] p-[20px]'>
      <div className='flex items-center justify-between gap-[12px]'>
        <div className='flex min-w-0 items-center gap-[18px]'>
          <RowVisual protocol={protocol} title={title} />
          <div className='min-w-0'>
            <p className='truncate text-[14px] font-semibold leading-[20px] text-[#FBF7F3]'>{title}</p>
            <ProtocolMeta protocol={protocol} network={network} />
          </div>
        </div>
        <ActionButton status={status} hasPosition={!!position} href={href} />
      </div>
      <div className='mt-[18px] h-px w-full bg-[#26272B]' />
      <div className='mt-[18px] grid grid-cols-2 gap-x-[16px] gap-y-[15px]'>
        {children}
        {position ? (
          <MobileMetric
            label='Your position'
            value={position.balanceLabel}
            breakdown={position.usdLabel}
          />
        ) : null}
      </div>
    </div>
  )
}

type PositionLineProps = {
  position?: UserPosition
}

/** Desktop-only highlight of the connected wallet's position under the row name. */
export const PositionLine: FC<PositionLineProps> = ({ position }) => {
  if (!position) return null

  return (
    <p className='mt-[2px] whitespace-nowrap text-[11px] font-normal leading-[15px] text-[#7ED9A8]'>
      You: {position.balanceLabel} · {position.usdLabel}
      {position.apyLabel ? ` · ${position.apyLabel}` : ''}
    </p>
  )
}

type MobileMetricProps = {
  label: string
  value?: string
  breakdown?: string
  children?: ReactNode
}

export const MobileMetric: FC<MobileMetricProps> = ({ label, value, breakdown, children }) => {
  return (
    <div className='flex min-w-0 flex-col gap-[2px]'>
      <span className='text-[12px] font-normal leading-[20px] tracking-[0.24px] text-[#8C8A84]'>
        {label}
      </span>
      {children ?? (
        <span className='text-[14px] font-normal leading-[20px] text-[#FBF7F3]'>
          {value}
          {breakdown ? (
            <span className='ml-[4px] text-[10px] leading-[20px] text-[#8C8A84]'>({breakdown})</span>
          ) : null}
        </span>
      )}
    </div>
  )
}

type MobileShowMoreButtonProps = {
  expanded: boolean
  onClick: () => void
}

export const MobileShowMoreButton: FC<MobileShowMoreButtonProps> = ({ expanded, onClick }) => {
  return (
    <button
      type='button'
      onClick={onClick}
      className='flex h-[47px] w-full items-center justify-center rounded-[20px] border border-[#26272B] bg-[#13151A] px-[18px] text-[13px] font-medium leading-[20px] text-[#C6C2BB]'
    >
      {expanded ? 'Show less' : 'Show more'}
    </button>
  )
}

const ACTION_BUTTON_CLASS =
  'flex h-[38px] w-[78px] items-center justify-center gap-[6px] rounded-full border-[0.6px] border-[#26272B] bg-[#13151A] px-[10px] text-[12px] font-semibold leading-[16px] text-white transition-colors duration-150 cursor-pointer md:h-[34px] md:w-[95px] md:gap-[10px] md:px-[12px] md:py-[6px] md:text-[12px] md:leading-[15px] group-hover:border-transparent group-hover:bg-[linear-gradient(90deg,var(--dawn-amber),var(--dawn-coral))] group-hover:text-[#0B0814] group-hover:shadow-[0_1px_0_rgba(255,255,255,0.25)_inset,0_8px_30px_-8px_rgba(234,82,112,0.5)]'

type ActionButtonProps = {
  status?: StrategyStatus
  hasPosition?: boolean
  href?: string
}

/**
 * Row action: "Soon" (disabled) for pending strategies, "Manage" when the
 * connected wallet holds a position, otherwise "Enter". Opens the partner
 * deposit link when `href` is provided.
 */
export const ActionButton: FC<ActionButtonProps> = ({
  status = 'live',
  hasPosition = false,
  href,
}) => {
  if (status === 'pending') {
    return (
      <button
        type='button'
        disabled
        className='flex h-[38px] w-[78px] cursor-not-allowed items-center justify-center rounded-full border-[0.6px] border-[#26272B] bg-[#13151A] px-[10px] text-[12px] font-semibold leading-[16px] text-white/40 md:h-[34px] md:w-[95px] md:px-[12px] md:py-[6px]'
      >
        Soon
      </button>
    )
  }

  const content = (
    <>
      <span>{hasPosition ? 'Manage' : 'Enter'}</span>
      <Image
        src={arrowRightWhiteIcon}
        alt=''
        width={9}
        height={6}
        className='h-[5.5px] w-[8px] shrink-0 transition-[filter] duration-150 group-hover:brightness-0 md:h-[6px] md:w-[9px]'
      />
    </>
  )

  if (href) {
    return (
      <a href={href} target='_blank' rel='noopener noreferrer' className={ACTION_BUTTON_CLASS}>
        {content}
      </a>
    )
  }

  return (
    <button type='button' className={ACTION_BUTTON_CLASS}>
      {content}
    </button>
  )
}
