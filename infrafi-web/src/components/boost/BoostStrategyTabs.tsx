'use client'

import { type FC } from 'react'
import { STRATEGY_TABS } from './data'
import { type BoostTab } from './types'

type BoostStrategyTabsProps = {
  activeTab: BoostTab
  onTabChange: (tab: BoostTab) => void
}

export const BoostStrategyTabs: FC<BoostStrategyTabsProps> = ({ activeTab, onTabChange }) => {
  return (
    <>
      {/* Mobile: scrollable pill tabs (Figma 6610-9289). Active pill uses an
          amber-tinted fill with gradient label text. */}
      <div
        role='tablist'
        className='scrollbar-none flex w-full items-center gap-[10px] overflow-x-auto md:hidden'
      >
        {STRATEGY_TABS.map((tab) => {
          const isActive = activeTab === tab.id

          return (
            <button
              key={tab.id}
              role='tab'
              aria-selected={isActive}
              onClick={() => onTabChange(tab.id)}
              className={`flex h-[38px] shrink-0 items-center justify-center whitespace-nowrap rounded-[10px] border-[0.6px] px-[18px] text-center text-[14px] leading-[21px] transition-colors ${
                isActive
                  ? 'border-[#f1994f] bg-[rgba(243,162,74,0.05)] font-semibold'
                  : 'border-[#26272b] bg-[#13151a] font-normal text-[#c6c2bb]'
              }`}
            >
              {isActive ? <span className='gradient-text'>{tab.label}</span> : tab.label}
            </button>
          )
        })}
      </div>

      {/* Desktop: underline tabs. */}
      <div
        role='tablist'
        className='scrollbar-none hidden w-full items-center gap-[6px] overflow-x-auto md:flex'
      >
        {STRATEGY_TABS.map((tab) => {
          const isActive = activeTab === tab.id

          return (
            <button
              key={tab.id}
              role='tab'
              aria-selected={isActive}
              onClick={() => onTabChange(tab.id)}
              className={`relative shrink-0 whitespace-nowrap px-[18px] py-[13px] text-center text-[14px] leading-[20px] transition-colors ${
                isActive
                  ? 'font-medium text-white'
                  : 'font-normal text-white/45 hover:text-white/70'
              }`}
            >
              {tab.label}
              {isActive && (
                <span
                  className='pointer-events-none absolute inset-x-[18px] bottom-0 h-[2px] rounded-full'
                  style={{ background: 'var(--dawn-gradient-h)' }}
                />
              )}
            </button>
          )
        })}
      </div>
    </>
  )
}
