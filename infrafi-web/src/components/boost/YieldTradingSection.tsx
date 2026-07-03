'use client'

import { type FC, useMemo, useState } from 'react'
import yieldIcon from '@/assets/icons/boost-page/Yield.svg'
import { usePartnerPositions } from '@/hooks/boost/usePartnerPositions'
import { YIELD_TRADING_ROWS } from './data'
import {
  ActionButton,
  MobileMetric,
  MobileShowMoreButton,
  MobileStrategyCard,
  PositionLine,
  ProtocolMeta,
  RowVisual,
  SectionColumnHeaders,
  SectionHeader,
} from './BoostSectionParts'
import type { StrategySectionProps } from './types'

export const YieldTradingSection: FC<StrategySectionProps> = ({
  hasTopSpacing = false,
  hasBottomSpacing = false,
}) => {
  const positions = usePartnerPositions()
  const [isExpandedMobile, setIsExpandedMobile] = useState(false)
  const mobileRows = useMemo(
    () => (isExpandedMobile ? YIELD_TRADING_ROWS : YIELD_TRADING_ROWS.slice(0, 2)),
    [isExpandedMobile],
  )

  return (
    <section className={`${hasTopSpacing ? 'md:mt-[24px]' : ''} ${hasBottomSpacing ? 'md:mb-[27px]' : ''}`.trim() || undefined}>
      <SectionHeader
        icon={yieldIcon}
        title='Yield Trading'
        description='Split yield-bearing assets into principal and yield tokens to lock fixed rates or speculate on variable returns.'
        stats={[
          { label: 'Fixed rate', value: '—' },
          { label: 'Max variable', value: '—' },
        ]}
      />
      <SectionColumnHeaders
        columns={[
          { label: 'Asset', widthClass: 'w-[284px]' },
          { label: 'Maturity', widthClass: 'w-[62px]', alignClass: 'text-center' },
          { label: 'TVL', widthClass: 'w-[111px]', alignClass: 'text-center' },
          { label: 'APY', widthClass: 'w-[147px]', alignClass: 'text-center' },
          { label: 'Type', widthClass: 'w-[55px]', alignClass: 'text-center' },
          { label: 'Action', widthClass: 'w-[95px]', alignClass: 'text-center' },
        ]}
      />
      <div className='hidden md:block'>
        {YIELD_TRADING_ROWS.map((row) => {
          const position = positions[row.id]

          return (
            <div
              key={`${row.asset}-${row.protocol}-${row.maturity}`}
              className='group flex items-center justify-between border-b border-white/6 px-[17px] py-[14px] transition-colors duration-150 last:border-b-0 hover:bg-white/2.5'
            >
              <div className='flex w-[284px] items-center gap-[18px]'>
                <RowVisual protocol={row.protocol} title={row.asset} />
                <div className='min-w-0'>
                  <p className='text-[12px] font-semibold leading-[20px] text-white'>{row.asset}</p>
                  <ProtocolMeta protocol={row.protocol} network={row.network} />
                  <PositionLine position={position} />
                </div>
              </div>
              <span className='w-[62px] text-center text-[12px] font-normal leading-[20px] tracking-[0.24px] text-white/50'>
                {row.maturity}
              </span>
              <span className='w-[111px] text-center text-[12px] font-normal leading-[20px] tracking-[0.24px] text-white/50'>
                {row.tvl}
              </span>
              <span
                className={`w-[147px] text-center text-[12px] font-semibold leading-[20px] ${
                  row.type === 'Fixed' ? 'text-[#7ED9B6]' : 'text-[#E97B40]'
                }`}
              >
                {row.apy}
              </span>
              <div className='flex w-[55px] justify-center'>
                <span
                  className={`inline-flex h-[21px] items-center justify-center rounded-[15px] border-[0.2px] text-[10px] font-medium leading-[14px] ${
                    row.type === 'Fixed'
                      ? 'w-[45px] border-[rgba(126,217,168,0.6)] bg-[rgba(126,217,168,0.05)] text-[#7ED9A8]'
                      : 'w-[55px] border-[rgba(243,162,74,0.6)] bg-[rgba(243,162,74,0.06)] text-[#F3A24A]'
                  }`}
                >
                  {row.type}
                </span>
              </div>
              <ActionButton status={row.status} hasPosition={!!position} href={row.depositUrl} />
            </div>
          )
        })}
      </div>
      <div className='space-y-[15px] md:hidden'>
        {mobileRows.map((row) => (
          <MobileStrategyCard
            key={`${row.asset}-${row.protocol}-${row.maturity}`}
            protocol={row.protocol}
            title={row.asset}
            network={row.network}
            status={row.status}
            position={positions[row.id]}
            href={row.depositUrl}
          >
            <MobileMetric label='Maturity' value={row.maturity} />
            <MobileMetric label='TVL' value={row.tvl} />
            <MobileMetric label='APY' value={row.apy} />
            <MobileMetric label='Type'>
              <div className='flex h-[20px] items-center'>
                <span
                  className={`inline-flex h-[18px] items-center justify-center rounded-[15px] border-[0.2px] px-[6px] text-[9px] font-medium leading-[12px] ${
                    row.type === 'Fixed'
                      ? 'border-[rgba(126,217,168,0.6)] bg-[rgba(126,217,168,0.05)] text-[#7ED9A8]'
                      : 'border-[rgba(243,162,74,0.6)] bg-[rgba(243,162,74,0.06)] text-[#F3A24A]'
                  }`}
                >
                  {row.type}
                </span>
              </div>
            </MobileMetric>
          </MobileStrategyCard>
        ))}
        {YIELD_TRADING_ROWS.length > 2 ? (
          <MobileShowMoreButton
            expanded={isExpandedMobile}
            onClick={() => setIsExpandedMobile((current) => !current)}
          />
        ) : null}
      </div>
    </section>
  )
}
