'use client'

import { type FC, useMemo, useState } from 'react'
import liquidityIcon from '@/assets/icons/boost-page/Liquidity.svg'
import { composeNetApy, formatPct, parsePct } from '@/lib/boost/apy'
import { formatUsdCompact } from '@/lib/partners/orca'
import { useEffectiveBaseApy } from '@/hooks/boost/useEffectiveBaseApy'
import { useOrcaPoolStats } from '@/hooks/boost/useOrcaPoolStats'
import { usePartnerPositions } from '@/hooks/boost/usePartnerPositions'
import { LIQUIDITY_ROWS } from './data'
import type { LiquidityRow } from './types'
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

export const LiquiditySection: FC<StrategySectionProps> = ({ hasTopSpacing = false }) => {
  const positions = usePartnerPositions()
  const orcaStats = useOrcaPoolStats()
  const baseApyPct = useEffectiveBaseApy()
  const [isExpandedMobile, setIsExpandedMobile] = useState(false)
  const mobileRows = useMemo(
    () => (isExpandedMobile ? LIQUIDITY_ROWS : LIQUIDITY_ROWS.slice(0, 2)),
    [isExpandedMobile],
  )

  // Overlays live Orca pool data (fee APR / TVL) and recomputes NET APY off the
  // shared live base for every live row; pending/failed rows keep static data.
  const resolveRow = (row: LiquidityRow) => {
    const raw = orcaStats[row.id]
    const feeApr = raw ? formatPct(raw.feeAprPct) : row.feeApr
    const feePct = raw ? raw.feeAprPct : parsePct(row.feeApr)
    const composed =
      row.status === 'live' && feePct !== null
        ? composeNetApy({ verb: 'fees', componentLabel: feeApr, componentPct: feePct, baseApyPct })
        : null

    return {
      feeApr,
      tvl: raw?.tvl ?? row.tvl,
      netApy: composed?.netApy ?? row.netApy,
      breakdown: composed?.breakdown ?? row.breakdown,
    }
  }

  // Section "LP TVL" = sum of the live pool TVLs we have (Orca); "—" until any
  // pool loads. "Pools" is a real count of the listed strategies.
  const liveOrcaTvl = Object.values(orcaStats).reduce((sum, raw) => sum + raw.tvlUsd, 0)
  const lpTvl = Object.keys(orcaStats).length > 0 ? formatUsdCompact(liveOrcaTvl) : '—'

  return (
    <section className={hasTopSpacing ? 'md:mt-[24px]' : undefined}>
      <SectionHeader
        icon={liquidityIcon}
        title='Liquidity'
        description='Provide liquidity to sUSD.tel pools and earn trading fees plus base yield.'
        marginBottomClass={hasTopSpacing ? 'mb-[10px] md:mb-[27px]' : undefined}
        stats={[
          { label: 'LP TVL', value: lpTvl },
          { label: 'Pools', value: String(LIQUIDITY_ROWS.length) },
        ]}
      />
      <SectionColumnHeaders
        columns={[
          { label: 'Pair', widthClass: 'w-[212px]' },
          { label: 'Pool Type', widthClass: 'w-[128px]', alignClass: 'text-center' },
          { label: 'Fee APR', widthClass: 'w-[111px]', alignClass: 'text-center' },
          { label: 'TVL', widthClass: 'w-[111px]', alignClass: 'text-center' },
          { label: 'Net APY', widthClass: 'w-[188px]', alignClass: 'text-center' },
          { label: 'Action', widthClass: 'w-[95px]', alignClass: 'text-center' },
        ]}
      />
      <div className='hidden md:block'>
        {LIQUIDITY_ROWS.map((row) => {
          const position = positions[row.id]
          const { feeApr, tvl, netApy, breakdown } = resolveRow(row)
          const isComingSoon = breakdown === 'Coming soon'

          return (
            <div
              key={`${row.pair}-${row.protocol}-${row.poolType}`}
              className='group flex items-center justify-between border-b border-white/6 px-[17px] py-[14px] transition-colors duration-150 last:border-b-0 hover:bg-white/2.5'
            >
              <div className='flex w-[212px] items-center gap-[18px]'>
                <RowVisual protocol={row.protocol} title={row.pair} />
                <div className='min-w-0'>
                  <p className='text-[12px] font-semibold leading-[20px] text-white'>{row.pair}</p>
                  <ProtocolMeta protocol={row.protocol} network={row.network} />
                  <PositionLine position={position} />
                </div>
              </div>
              <span className='w-[128px] text-center text-[12px] font-normal leading-[20px] tracking-[0.24px] text-white/50'>
                {row.poolType}
              </span>
              <span className='w-[111px] text-center text-[12px] font-normal leading-[20px] tracking-[0.24px] text-white/50'>
                {feeApr}
              </span>
              <span className='w-[111px] text-center text-[12px] font-normal leading-[20px] tracking-[0.24px] text-white/50'>
                {tvl}
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
          const { feeApr, tvl, netApy, breakdown } = resolveRow(row)
          const isComingSoon = breakdown === 'Coming soon'

          return (
            <MobileStrategyCard
              key={`${row.pair}-${row.protocol}-${row.poolType}`}
              protocol={row.protocol}
              title={row.pair}
              network={row.network}
              status={row.status}
              position={positions[row.id]}
              href={row.depositUrl}
            >
              <MobileMetric label='Pool Type' value={row.poolType} />
              <MobileMetric label='Fee APR' value={feeApr} />
              <MobileMetric label='TVL' value={tvl} />
              <MobileMetric
                label='Net APY'
                value={isComingSoon ? breakdown : netApy}
                breakdown={isComingSoon ? undefined : breakdown}
              />
            </MobileStrategyCard>
          )
        })}
        {LIQUIDITY_ROWS.length > 2 ? (
          <MobileShowMoreButton
            expanded={isExpandedMobile}
            onClick={() => setIsExpandedMobile((current) => !current)}
          />
        ) : null}
      </div>
    </section>
  )
}
