'use client'

import { SegmentedToggle } from '@/components/ui/SegmentedToggle'
import type { RangeKey } from './utils'

type Props = {
  value: RangeKey
  onChange: (next: RangeKey) => void
  options?: readonly RangeKey[]
}

const DEFAULT_OPTIONS: readonly RangeKey[] = ['7D', '30D', '90D', '1Y', 'All'] as const

export function RangeTabs({ value, onChange, options = DEFAULT_OPTIONS }: Props) {
  return (
    <SegmentedToggle<RangeKey>
      value={value}
      onChange={onChange}
      options={options.map((opt) => ({ value: opt, label: opt }))}
    />
  )
}
