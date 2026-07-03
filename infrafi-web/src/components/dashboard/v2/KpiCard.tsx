'use client'

import { useState } from 'react'
import { changeFromStart, type RangeKey } from '@/components/dashboard/utils'
import {
  AreaSpark,
  DetailFooter,
  DetailHeader,
  DetailRangeTabs,
  DetailStat,
  pickAxisDates,
  sliceByRange,
} from './charts'
import { Card, DeltaPill, ExpandGlyph, InfoBadge } from './ui'

// Expand-modal detail panel — mirrors the reference KPI modal: kicker + title,
// CURRENT / CHANGE / {range} HIGH / {range} LOW stats, range tabs, the big axis
// chart, and an About footer. Range tabs slice the already-loaded series.
function KpiDetail({
  label,
  color,
  data,
  dates,
  formatValue,
  about,
  refLine,
  refLabel,
}: {
  label: string
  color: string
  data: number[]
  dates: string[]
  formatValue: (n: number) => string
  about?: string
  refLine?: number
  refLabel?: string
}) {
  const [range, setRange] = useState<RangeKey>('30D')
  const sliced = sliceByRange(data, dates, range)
  const series = sliced.data.length >= 2 ? sliced.data : data
  const xLabels = pickAxisDates(sliced.dates.length >= 2 ? sliced.dates : dates)
  const current = series[series.length - 1]
  const first = series[0]
  const change = changeFromStart(current, first, formatValue)
  const high = Math.max(...series)
  const low = Math.min(...series)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <DetailHeader kicker={label} title={label} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap' }}>
          <DetailStat label='Current' value={formatValue(current)} />
          <DetailStat label='Change' value={change.label} tone={change.positive ? 'pos' : 'neg'} />
          <DetailStat label={`${range} High`} value={formatValue(high)} />
          <DetailStat label={`${range} Low`} value={formatValue(low)} />
        </div>
        <DetailRangeTabs value={range} onChange={setRange} />
      </div>
      <AreaSpark
        data={series}
        color={color}
        formatValue={formatValue}
        xLabels={xLabels}
        pointDates={sliced.dates.length >= 2 ? sliced.dates : dates}
        refLine={refLine}
        refLabel={refLabel}
      />
      {about && <DetailFooter label='About'>{about}</DetailFooter>}
    </div>
  )
}

export function KpiCard({
  label,
  value,
  sub,
  delta,
  deltaPositive,
  color,
  data,
  info,
  formatValue,
  dates = [],
  about,
  refLine,
  refLabel,
}: {
  label: string
  value: string
  sub: string
  delta: string
  deltaPositive: boolean
  color: string
  data: number[]
  info?: string
  formatValue?: (n: number) => string
  dates?: string[]
  about?: string
  refLine?: number
  refLabel?: string
}) {
  const fmt = formatValue ?? ((n: number) => n.toFixed(2))
  return (
    <Card
      style={{ minHeight: 192 }}
      detail={
        <KpiDetail
          label={label}
          color={color}
          data={data}
          dates={dates}
          formatValue={fmt}
          about={about}
          refLine={refLine}
          refLabel={refLabel}
        />
      }
    >
      <ExpandGlyph />
      <div className='dash-card-label' style={{ marginBottom: 12 }}>
        {label}
        <InfoBadge title={info} />
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
        <span className='dash-card-value tabular'>{value}</span>
        <DeltaPill value={delta} positive={deltaPositive} />
      </div>
      <div className='dash-card-sub' style={{ marginBottom: 14 }}>
        {sub}
      </div>
      <div style={{ paddingTop: 10, paddingBottom: 10 }}>
        <AreaSpark data={data} color={color} width={400} height={53} pad={8} />
      </div>
    </Card>
  )
}
