'use client'

import { type FC, useMemo, useState } from 'react'
import loopIcon from '@/assets/icons/boost-page/Loop.svg'
import { usePartnerPositions } from '@/hooks/boost/usePartnerPositions'
import { LOOPING_ROWS } from './data'
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

export const LoopingSection: FC<StrategySectionProps> = ({
  hasTopSpacing = false,
  hasBottomSpacing = false,
}) => {
  const positions = usePartnerPositions()
  const [isExpandedMobile, setIsExpandedMobile] = useState(false)
  const mobileRows = useMemo(
    () => (isExpandedMobile ? LOOPING_ROWS : LOOPING_ROWS.slice(0, 2)),
    [isExpandedMobile],
  )

  return (
    <section className={`${hasTopSpacing ? 'md:mt-[24px]' : ''} ${hasBottomSpacing ? 'md:mb-[27px]' : ''}`.trim() || undefined}>
      <SectionHeader
        icon={loopIcon}
        title='Looping'
        description='Borrow against your sUSD.tel to re-supply and amplify yield.'
        stats={[
          { label: 'Highest APY', value: '—' },
          { label: 'Max leverage', value: '—' },
        ]}
      />
      <SectionColumnHeaders
        columns={[
          { label: 'Pool', widthClass: 'w-[284px]' },
          { label: 'Leverage', widthClass: 'w-[62px]', alignClass: 'text-center' },
          { label: 'TVL', widthClass: 'w-[111px]', alignClass: 'text-center' },
          { label: 'APY', widthClass: 'w-[147px]', alignClass: 'text-center' },
          { label: 'Action', widthClass: 'w-[95px]', alignClass: 'text-center' },
        ]}
      />
      <div className='hidden md:block'>
        {LOOPING_ROWS.map((row) => {
          const position = positions[row.id]
          const isComingSoon = row.apyBreakdown === 'Coming soon'

          return (
            <div
              key={`${row.pool}-${row.leverage}`}
              className='group flex items-center justify-between border-b border-white/6 px-[17px] py-[14px] transition-colors duration-150 last:border-b-0 hover:bg-white/2.5'
            >
              <div className='flex w-[284px] items-center gap-[18px]'>
                <RowVisual protocol={row.protocol} title={row.pool} />
                <div className='min-w-0'>
                  <p className='text-[12px] font-semibold leading-[20px] text-white'>{row.pool}</p>
                  <ProtocolMeta protocol={row.protocol} network={row.network} />
                  <PositionLine position={position} />
                </div>
              </div>
              <span className='w-[62px] text-center text-[12px] font-normal leading-[20px] tracking-[0.24px] text-white/50'>
                {row.leverage}
              </span>
              <span className='w-[111px] text-center text-[12px] font-normal leading-[20px] tracking-[0.24px] text-white/50'>
                {row.tvl}
              </span>
              <div className='flex w-[147px] flex-col items-center'>
                {!isComingSoon && (
                  <span className='text-[12px] font-semibold leading-[20px] text-[#E97B40]'>{row.apy}</span>
                )}
                <span className='text-[12px] font-normal leading-[20px] tracking-[0.24px] text-white/50'>
                  {row.apyBreakdown}
                </span>
              </div>
              <ActionButton status={row.status} hasPosition={!!position} href={row.depositUrl} />
            </div>
          )
        })}
      </div>
      <div className='space-y-[15px] md:hidden'>
        {mobileRows.map((row) => {
          const isComingSoon = row.apyBreakdown === 'Coming soon'

          return (
            <MobileStrategyCard
              key={`${row.pool}-${row.leverage}`}
              protocol={row.protocol}
              title={row.pool}
              network={row.network}
              status={row.status}
              position={positions[row.id]}
              href={row.depositUrl}
            >
              <MobileMetric label='Leverage' value={row.leverage} />
              <MobileMetric label='TVL' value={row.tvl} />
              <MobileMetric
                label='APY'
                value={isComingSoon ? row.apyBreakdown : row.apy}
                breakdown={isComingSoon ? undefined : row.apyBreakdown}
              />
            </MobileStrategyCard>
          )
        })}
        {LOOPING_ROWS.length > 2 ? (
          <MobileShowMoreButton
            expanded={isExpandedMobile}
            onClick={() => setIsExpandedMobile((current) => !current)}
          />
        ) : null}
      </div>
    </section>
  )
}
