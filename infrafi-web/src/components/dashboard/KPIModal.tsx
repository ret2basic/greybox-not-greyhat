'use client'

import { BigAreaChart } from './BigAreaChart'
import { RangeTabs } from './RangeTabs'
import { changeFromStart, fmtVal, type RangeKey, type ValueKind } from './utils'

type Props = {
  // Real series for the selected range, oldest → newest.
  data: number[]
  dates?: string[]
  range: RangeKey
  onRangeChange: (next: RangeKey) => void
  color: string
  kind: ValueKind | string
  about?: string
  refLine?: number | null
  refLabel?: string
  // Live snapshot value for the "Current" stat — overrides data[last] so the
  // modal always shows the same number as the header chip regardless of which
  // API field backs the history series.
  currentValue?: number
}

// The big version of a KPI — range tabs, a large chart, change/high/low
// summary stats, and an "About" copy block. Presentational: the caller owns
// the range state and supplies the real data series for it.
export function KPIModal({
  data,
  dates,
  range,
  onRangeChange,
  color,
  kind,
  about,
  refLine = null,
  refLabel = '',
  currentValue,
}: Props) {
  const hasData = data.length >= 2
  const start = hasData ? data[0] : 0
  const end = hasData ? data[data.length - 1] : 0
  // Use the live snapshot value when available so "Current" matches the header
  // chip exactly — history's last data point may differ due to field naming
  // (net_asset_value_raw vs net_asset_value) or APY calculation method.
  const displayCurrent = currentValue !== undefined ? currentValue : end
  const change = hasData
    ? changeFromStart(displayCurrent, start, (n) => fmtVal(n, kind))
    : null
  const high = hasData ? Math.max(...data, displayCurrent) : displayCurrent
  const low = hasData ? Math.min(...data, displayCurrent) : displayCurrent
  const stat = (v: number) => (hasData ? fmtVal(v, kind) : '—')

  return (
    <div className='kpi-modal-body'>
      {/* flexWrap mirrors dashboard's KpiDetail — RangeTabs drop below the
          stat row when the card narrows, stats themselves wrap onto two
          lines instead of overflowing horizontally. */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 16,
          flexWrap: 'wrap',
        }}
      >
        <div
          className='kpi-modal-stats'
          style={{ display: 'flex', gap: 28, flexWrap: 'wrap', alignItems: 'baseline' }}
        >
          <div>
            <div className='kicker' style={{ marginBottom: 4 }}>Current</div>
            <div
              className='tabular kpi-modal-current'
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: 32,
                letterSpacing: '-0.025em',
              }}
            >
              {hasData ? stat(displayCurrent) : '—'}
            </div>
          </div>
          <div>
            <div className='kicker' style={{ marginBottom: 4 }}>Change</div>
            <div
              className='tabular kpi-modal-stat'
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: 18,
                color: change && !change.positive ? 'var(--neg)' : 'var(--pos)',
              }}
            >
              {change ? change.label : '—'}
            </div>
          </div>
          <div>
            <div className='kicker' style={{ marginBottom: 4 }}>{range} High</div>
            <div
              className='tabular kpi-modal-stat'
              style={{ fontFamily: 'var(--font-display)', fontSize: 18 }}
            >
              {stat(high)}
            </div>
          </div>
          <div>
            <div className='kicker' style={{ marginBottom: 4 }}>{range} Low</div>
            <div
              className='tabular kpi-modal-stat'
              style={{ fontFamily: 'var(--font-display)', fontSize: 18 }}
            >
              {stat(low)}
            </div>
          </div>
        </div>
        <RangeTabs value={range} onChange={onRangeChange} />
      </div>
      <div className='kpi-modal-chart'>
        <BigAreaChart
          data={data}
          dates={dates}
          color={color}
          kind={kind}
          height={360}
          refLine={refLine}
          refLabel={refLabel}
        />
      </div>
      {about && (
        <div className='card-flat kpi-modal-footer'>
          <div className='kicker kpi-modal-footer-label'>About</div>
          <div style={{ fontSize: 13, color: 'var(--fg-2)', lineHeight: 1.6 }}>
            {about}
          </div>
        </div>
      )}
    </div>
  )
}
