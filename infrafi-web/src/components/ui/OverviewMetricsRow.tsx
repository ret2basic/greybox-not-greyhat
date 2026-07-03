'use client'

import type { FC, ReactNode } from 'react'
import DashboardInfoPopover from '@/components/ui/DashboardInfoPopover'

export type OverviewMetricItem = {
  label: string
  value: string
  hasInfo?: boolean
  tooltip?: string
  tooltipWidthClassName?: string
  widthClassName?: string
}

type OverviewMetricsRowProps = {
  metrics: readonly OverviewMetricItem[]
  containerClassName?: string
  metricGroupClassName?: string
  dividerClassName?: string
  metricClassName?: string
  labelRowClassName?: string
  labelClassName?: string
  valueClassName?: string
  valueTopClassName?: string
  renderInfoIcon?: (metric: OverviewMetricItem) => ReactNode
}

function DefaultMetricInfoIcon() {
  return (
    <span className='inline-flex size-[10px] shrink-0 items-center justify-center rounded-full border border-[#A8958A] text-[8px] font-semibold leading-none text-[#A8958A]'>
      i
    </span>
  )
}

export const OverviewMetricsRow: FC<OverviewMetricsRowProps> = ({
  metrics,
  containerClassName = 'flex items-center justify-center gap-[15px]',
  metricGroupClassName = 'flex items-center gap-[15px]',
  dividerClassName = 'h-[38px] w-px bg-white/30',
  metricClassName = 'flex shrink-0 flex-col',
  labelRowClassName = 'flex items-center gap-0',
  labelClassName = 'text-[12px] font-normal leading-[15px] text-[#A8958A]',
  valueClassName = 'text-[12px] font-semibold leading-[15px] text-white',
  valueTopClassName = 'mt-[5px]',
  renderInfoIcon,
}) => {
  return (
    <div className={containerClassName}>
      {metrics.map((metric, index) => {
        const infoIcon = renderInfoIcon?.(metric) ?? <DefaultMetricInfoIcon />

        return (
          <div key={metric.label} className={metricGroupClassName}>
            {index > 0 ? <div className={dividerClassName} /> : null}
            <div className={`${metricClassName} ${metric.widthClassName ?? ''}`.trim()}>
              <div className={labelRowClassName}>
                <span className={labelClassName}>{metric.label}</span>
                {metric.hasInfo ? (
                  metric.tooltip ? (
                    <DashboardInfoPopover
                      ariaLabel={`${metric.label} explanation`}
                      content={metric.tooltip}
                      widthClassName={metric.tooltipWidthClassName ?? 'w-[198px]'}
                      trigger={infoIcon}
                    />
                  ) : (
                    infoIcon
                  )
                ) : null}
              </div>
              <span className={`${valueTopClassName} ${valueClassName}`.trim()}>{metric.value}</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
