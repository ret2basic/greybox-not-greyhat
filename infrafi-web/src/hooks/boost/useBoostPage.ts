'use client'

import { useMemo, useState } from 'react'
import { BoostTab } from '@/components/boost/types'

export type BoostSectionId = 'looping' | 'yield-trading' | 'lending' | 'liquidity'

export type BoostSectionDescriptor = {
  hasBottomSpacing?: boolean
  hasTopSpacing?: boolean
  id: BoostSectionId
}

const BOOST_TABS_TO_SECTIONS: Record<BoostTab, BoostSectionDescriptor[]> = {
  [BoostTab.All]: [
    { id: 'looping', hasTopSpacing: true, hasBottomSpacing: true },
    { id: 'yield-trading', hasBottomSpacing: true },
    { id: 'lending', hasBottomSpacing: true },
    { id: 'liquidity' },
  ],
  [BoostTab.Looping]: [{ id: 'looping', hasTopSpacing: true }],
  [BoostTab.YieldTrading]: [{ id: 'yield-trading', hasTopSpacing: true }],
  [BoostTab.Lending]: [{ id: 'lending', hasTopSpacing: true }],
  [BoostTab.Liquidity]: [{ id: 'liquidity', hasTopSpacing: true }],
}

export const useBoostPage = () => {
  const [activeTab, setActiveTab] = useState<BoostTab>(BoostTab.All)

  const contentSections = useMemo(
    () => BOOST_TABS_TO_SECTIONS[activeTab],
    [activeTab],
  )

  return {
    activeTab,
    contentSections,
    setActiveTab,
  }
}
