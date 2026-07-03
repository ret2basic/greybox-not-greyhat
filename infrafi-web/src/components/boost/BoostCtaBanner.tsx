'use client'

import { type FC } from 'react'

import { GradientButton } from '@/components/ui/GradientButton'

export const BoostCtaBanner: FC = () => {
  return (
    <div className='mt-[24px] flex w-full items-center justify-between rounded-[20px] border border-[#26272B] bg-[#13151A] px-[20px] py-[14px] md:mt-[16px] md:h-[72px] md:rounded-[10px] md:border-white/[0.07] md:px-[26px] md:py-0'>
      <div className='flex flex-col gap-[3px] pr-[8px]'>
        <p className='text-[11px] font-normal leading-[15px] text-white/45 md:text-[12px]'>Need sUSD.tel?</p>
        <p className='text-[14px] font-semibold leading-[20px] text-white md:text-[16px]'>
          Stake USD.tel first to start composing.
        </p>
      </div>

      <GradientButton href='/buy-stake' size='sm' className='shrink-0' style={{ padding: '8px 16px' }}>
        Buy &amp; Stake
        <span className='font-normal'>↗</span>
      </GradientButton>
    </div>
  )
}
