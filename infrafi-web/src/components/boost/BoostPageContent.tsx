'use client'

import { Fragment, type FC } from 'react'
import { BoostStrategyTabs } from './BoostStrategyTabs'
import { GradientBar } from './BoostSectionParts'
import { BoostCtaBanner } from './BoostCtaBanner'
import { LoopingSection } from './LoopingSection'
import { YieldTradingSection } from './YieldTradingSection'
import { LendingSection } from './LendingSection'
import { LiquiditySection } from './LiquiditySection'
import { useBoostPage } from '@/hooks/boost/useBoostPage'

const SECTION_COMPONENTS = {
  'looping': LoopingSection,
  'yield-trading': YieldTradingSection,
  'lending': LendingSection,
  'liquidity': LiquiditySection,
} as const

export const BoostPageContent: FC = () => {
  const { activeTab, contentSections, setActiveTab } = useBoostPage()

  return (
    <div className='relative z-0 -mt-[60px] min-h-screen pt-[60px] pb-[80px]'>
      <div className='app-container relative z-10 flex w-full flex-col items-center'>
        <header className='w-full pt-[56px] pb-[28px] text-center md:pt-[87px] md:pb-[44px]'>
          <h1
            className='text-[32px] font-semibold leading-[1.08] tracking-[-0.02em] text-white md:text-[44px]'
            style={{ fontFamily: 'var(--font-display)' }}
          >
            Amplify your <span className='gradient-text'>yield.</span>
          </h1>
          <p className='mx-auto mt-[14px] max-w-[520px] text-[13px] font-normal leading-normal text-white/55 md:text-[15px]'>
            Once minted, sUSD.tel is yours. Deploy it across audited DeFi venues — loop for leverage,
            lock fixed-rate yield, lend, or LP. Base vault APY stacks on top.
          </p>
        </header>

        <div className='w-full'>
          <div className='mx-auto flex w-full flex-col items-stretch'>
            <BoostStrategyTabs activeTab={activeTab} onTabChange={setActiveTab} />

            <div className='mt-[20px] flex flex-col gap-[24px] md:mt-[20px] md:gap-[16px]'>
              {contentSections.map((section, index) => {
                const Component = SECTION_COMPONENTS[section.id]

                return (
                  <Fragment key={section.id}>
                    {/* Mobile only: a gradient rule separates stacked sections.
                        Desktop wraps each section in its own card instead. */}
                    {index > 0 && (
                      <div className='md:hidden'>
                        <GradientBar />
                      </div>
                    )}
                    <div className='w-full md:rounded-[10px] md:border md:border-white/[0.07] md:bg-[#13151A] md:px-[24px] md:py-[22px]'>
                      <Component />
                    </div>
                  </Fragment>
                )
              })}
            </div>

            <BoostCtaBanner />
          </div>
        </div>
      </div>
    </div>
  )
}
