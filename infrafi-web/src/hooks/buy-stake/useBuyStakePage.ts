'use client'

import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { SUSDTEL_TOOLTIP_TEXT, TVL_TOOLTIP_TEXT } from '@/constants/metric-tooltips'
import { useTopMetricsValues } from '@/hooks/ui/useTopMetricsValues'
import { BuyMode, StakeMode } from './types'

export enum BuyStakeTab {
  Buy = 'buy',
  Stake = 'stake',
  Bridge = 'bridge',
}

type PageMetricItem = {
  label: string
  value: string
  hasInfo?: boolean
  tooltip?: string
  tooltipWidthClassName: string
  widthClassName: string
}

const BUY_STAKE_TABS = [
  { id: BuyStakeTab.Buy, label: 'Buy' },
  { id: BuyStakeTab.Stake, label: 'Stake' },
  { id: BuyStakeTab.Bridge, label: 'Bridge', isDisabled: true },
] as const

export const useBuyStakePage = () => {
  const { apy, susdtel, tvl } = useTopMetricsValues()
  const searchParams = useSearchParams()
  const resolvedTab = searchParams.get('tab') === BuyStakeTab.Stake ? BuyStakeTab.Stake : BuyStakeTab.Buy
  const resolvedStakeMode = searchParams.get('mode') === StakeMode.Unstake ? StakeMode.Unstake : StakeMode.Stake
  const resolvedBuyMode = searchParams.get('mode') === BuyMode.Withdraw ? BuyMode.Withdraw : BuyMode.Buy
  const [activeTab, setActiveTab] = useState<BuyStakeTab>(resolvedTab)
  const [stakeMode, setStakeMode] = useState<StakeMode>(resolvedStakeMode)
  const [buyMode] = useState<BuyMode>(resolvedBuyMode)

  useEffect(() => {
    setActiveTab(resolvedTab)
    setStakeMode(resolvedStakeMode)
  }, [resolvedTab, resolvedStakeMode])

  const tabPanelRadiusClassName =
    activeTab === BuyStakeTab.Buy ? 'rounded-[5px] rounded-tl-none' : 'rounded-[5px]'
  const pageMetrics = useMemo<readonly PageMetricItem[]>(
    () => [
      {
        label: 'TVL',
        value: tvl,
        hasInfo: true,
        tooltip: TVL_TOOLTIP_TEXT,
        tooltipWidthClassName: 'w-[198px]',
        widthClassName: 'sm:w-[60px]',
      },
      {
        label: 'APY',
        value: apy,
        tooltipWidthClassName: 'w-[198px]',
        widthClassName: 'sm:w-[45px]',
      },
      {
        label: 'sUSD.tel',
        value: susdtel,
        hasInfo: true,
        tooltip: SUSDTEL_TOOLTIP_TEXT,
        tooltipWidthClassName: 'w-[230px]',
        widthClassName: 'sm:w-[60px]',
      },
    ],
    [apy, susdtel, tvl],
  )

  return {
    activeTab,
    buyStakeTabs: BUY_STAKE_TABS,
    buyMode,
    pageMetrics,
    setActiveTab,
    setStakeMode,
    stakeMode,
    tabPanelRadiusClassName,
  }
}
