'use client'

import { type FC, useMemo, useState } from 'react'
import lendingIcon from '@/assets/icons/boost-page/Lending.svg'
import { composeNetApy, parsePct } from '@/lib/boost/apy'
import { useEffectiveBaseApy } from '@/hooks/boost/useEffectiveBaseApy'
import { usePartnerPositions } from '@/hooks/boost/usePartnerPositions'
import { LENDING_ROWS } from './data'
import type { LendingRow } from './types'
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

export const LendingSection: FC<StrategySectionProps> = ({
  hasTopSpacing = false,
  hasBottomSpacing = false,
}) => {
  const positions = usePartnerPositions()
  const baseApyPct = useEffectiveBaseApy()
  const [isExpandedMobile, setIsExpandedMobile] = useState(false)
  const mobileRows = useMemo(
    () => (isExpandedMobile ? LENDING_ROWS : LENDING_ROWS.slice(0, 2)),
    [isExpandedMobile],
  )

  // Recomputes NET APY off the shared live base for every live row; pending
  // rows (no numeric lend rate) keep their static "Coming soon" data.
  const resolveRow = (row: LendingRow) => {
    const lendPct = parsePct(row.lendRate)
    const composed =
      row.status === 'live' && lendPct !== null
        ? composeNetApy({
            verb: 'lend',
            componentLabel: row.lendRate,
            componentPct: lendPct,
            baseApyPct,
          })
        : null

    return {
      netApy: composed?.netApy ?? row.netApy,
      breakdown: composed?.breakdown ?? row.breakdown,
    }
  }

  return (
    <section className={`${hasTopSpacing ? 'md:mt-[24px]' : ''} ${hasBottomSpacing ? 'md:mb-[27px]' : ''}`.trim() || undefined}>
      <SectionHeader
        icon={lendingIcon}
        title='Lending'
        description='Lend your sUSD.tel across DeFi markets to earn base yield with optional protocol incentives.'
        stats={[
          { label: 'Lending TVL', value: '—' },
          { label: 'Top APY', value: '—' },
        ]}
      />
      <SectionColumnHeaders
        columns={[
          { label: 'Asset', widthClass: 'w-[212px]' },
          { label: 'Market Type', widthClass: 'w-[128px]', alignClass: 'text-center' },
          { label: 'Lend Rate', widthClass: 'w-[111px]', alignClass: 'text-center' },
          { label: 'TVL', widthClass: 'w-[111px]', alignClass: 'text-center' },
          { label: 'Net APY', widthClass: 'w-[188px]', alignClass: 'text-center' },
          { label: 'Action', widthClass: 'w-[95px]', alignClass: 'text-center' },
        ]}
      />
      <div className='hidden md:block'>
        {LENDING_ROWS.map((row) => {
          const position = positions[row.id]
          const { netApy, breakdown } = resolveRow(row)
          const isComingSoon = breakdown === 'Coming soon'

          return (
            <div
              key={`${row.asset}-${row.protocol}-${row.marketType}`}
              className='group flex items-center justify-between border-b border-white/6 px-[17px] py-[14px] transition-colors duration-150 last:border-b-0 hover:bg-white/2.5'
            >
              <div className='flex w-[212px] items-center gap-[18px]'>
                <RowVisual protocol={row.protocol} title={row.asset} />
                <div className='min-w-0'>
                  <p className='text-[12px] font-semibold leading-[20px] text-white'>{row.asset}</p>
                  <ProtocolMeta protocol={row.protocol} network={row.network} />
                  <PositionLine position={position} />
                </div>
              </div>
              <span className='w-[128px] text-center text-[12px] font-normal leading-[20px] tracking-[0.24px] text-white/50'>
                {row.marketType}
              </span>
              <span className='w-[111px] text-center text-[12px] font-normal leading-[20px] tracking-[0.24px] text-white/50'>
                {row.lendRate}
              </span>
              <span className='w-[111px] text-center text-[12px] font-normal leading-[20px] tracking-[0.24px] text-white/50'>
                {row.tvl}
              </span>
              <div className='flex w-[188px] flex-col items-center'>
                {!isComingSoon && (
                  <span className='text-[12px] font-semibold leading-[20px] text-[#E97B40]'>{netApy}</span>
                )}
                <span className='whitespace-nowrap text-center text-[12px] font-normal leading-[20px] tracking-[0.24px] text-white/50'>
                  {breakdown}
                </span>
              </div>
              <ActionButton status={row.status} hasPosition={!!position} href={row.depositUrl} />
            </div>
          )
        })}
      </div>
      <div className='space-y-[15px] md:hidden'>
        {mobileRows.map((row) => {
          const { netApy, breakdown } = resolveRow(row)
          const isComingSoon = breakdown === 'Coming soon'

          return (
            <MobileStrategyCard
              key={`${row.asset}-${row.protocol}-${row.marketType}`}
              protocol={row.protocol}
              title={row.asset}
              network={row.network}
              status={row.status}
              position={positions[row.id]}
              href={row.depositUrl}
            >
              <MobileMetric label='Market Type' value={row.marketType} />
              <MobileMetric label='Lend Rate' value={row.lendRate} />
              <MobileMetric label='TVL' value={row.tvl} />
              <MobileMetric
                label='Net APY'
                value={isComingSoon ? breakdown : netApy}
                breakdown={isComingSoon ? undefined : breakdown}
              />
            </MobileStrategyCard>
          )
        })}
        {LENDING_ROWS.length > 2 ? (
          <MobileShowMoreButton
            expanded={isExpandedMobile}
            onClick={() => setIsExpandedMobile((current) => !current)}
          />
        ) : null}
      </div>
    </section>
  )
}
