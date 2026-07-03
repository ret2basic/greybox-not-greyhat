'use client'

import type { ReactNode } from 'react'
import type { RangeKey } from '@/components/dashboard/utils'
import { SegmentedToggle } from '@/components/ui/SegmentedToggle'

export const RANGE_OPTIONS: readonly RangeKey[] = ['All', '7D', '30D', '90D', '1Y'] as const

export function RangeTabs({ value, onChange }: { value: RangeKey; onChange: (next: RangeKey) => void }) {
  return (
    <SegmentedToggle
      value={value}
      onChange={onChange}
      options={RANGE_OPTIONS.map((opt) => ({ value: opt, label: opt }))}
    />
  )
}

export function Hero() {
  return (
    <div className='dash-hero'>
      <h1>
        Vault <span className='accent'>stats</span>
      </h1>
      <p>Monitor telecom-backed yield, vault health, and deployment activity across the network.</p>
    </div>
  )
}

function Chevron() {
  return (
    <svg className='dash-section-chevron' viewBox='0 0 24 24' fill='none' aria-hidden>
      <path d='M6 9l6 6 6-6' stroke='currentColor' strokeWidth='2' strokeLinecap='round' strokeLinejoin='round' />
    </svg>
  )
}

export type SummaryMetric = { label: string; value: ReactNode }

export function DashboardSection({
  index,
  title,
  open,
  onToggle,
  accent = 'var(--d-amber)',
  summary,
  children,
}: {
  index: string
  title: string
  open: boolean
  onToggle: () => void
  accent?: string
  summary: SummaryMetric[]
  children: ReactNode
}) {
  if (!open) {
    return (
      <div
        className='dash-summary'
        style={{ ['--accent' as string]: accent }}
        onClick={onToggle}
        role='button'
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onToggle()
          }
        }}
      >
        <div className='dash-summary-head'>
          <div className={`dash-section-head collapsed`} style={{ cursor: 'pointer', gap: 12 }}>
            <Chevron />
            <div>
              <div className='dash-section-title'>
                <span className='idx'>{index}</span>
                {title}
              </div>
              <div className='dash-section-sub'>Click to expand</div>
            </div>
          </div>
        </div>
        <div className='dash-summary-metrics'>
          {summary.map((m, i) => (
            <span key={i} className='dash-summary-metric'>
              {m.label}
              <b>{m.value}</b>
            </span>
          ))}
        </div>
      </div>
    )
  }

  return (
    <section className='dash-section' style={{ ['--accent' as string]: accent }}>
      <div
        className='dash-section-head'
        onClick={onToggle}
        role='button'
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onToggle()
          }
        }}
      >
        <Chevron />
        <div>
          <div className='dash-section-title'>
            <span className='idx'>{index}</span>
            {title}
          </div>
          <div className='dash-section-sub'>Click to collapse</div>
        </div>
      </div>
      <div className='dash-collapse'>
        <div className='dash-collapse-inner'>
          <div className='dash-section-body'>{children}</div>
        </div>
      </div>
    </section>
  )
}
