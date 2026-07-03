'use client'

import { useEffect, useState, type CSSProperties, type ReactNode } from 'react'

export type SegmentedToggleOption<T extends string> = {
  value: T
  label: ReactNode
  disabled?: boolean
  badge?: ReactNode
}

const MOBILE_BREAKPOINT = '(max-width: 640px)'

function getOptionText(label: ReactNode, value: string): string {
  if (typeof label === 'string' || typeof label === 'number') return String(label)
  return value
}

export function SegmentedToggle<T extends string>({
  options,
  value,
  onChange,
  className,
  style,
  equalWidth = false,
}: {
  options: SegmentedToggleOption<T>[]
  value: T
  onChange: (value: T) => void
  className?: string
  style?: CSSProperties
  // Lay segments out as equal-width columns (every segment matches the widest)
  // so labels of different lengths don't produce uneven pill sizes.
  equalWidth?: boolean
}) {
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
    const media = window.matchMedia(MOBILE_BREAKPOINT)
    const sync = () => setIsMobile(media.matches)
    sync()
    media.addEventListener('change', sync)
    return () => media.removeEventListener('change', sync)
  }, [])

  if (isMobile) {
    const activeOption = options.find((opt) => opt.value === value)
    return (
      <div
        className={className}
        style={{
          position: 'relative',
          display: 'inline-flex',
          alignItems: 'center',
          ...style,
        }}
      >
        <select
          value={value}
          onChange={(event) => onChange(event.target.value as T)}
          aria-label='Select range'
          style={{
            appearance: 'none',
            WebkitAppearance: 'none',
            MozAppearance: 'none',
            padding: '10px 36px 10px 16px',
            borderRadius: 999,
            background: 'var(--bg-2)',
            border: '1px solid var(--line)',
            color: 'var(--fg-1, var(--d-text))',
            fontFamily: 'inherit',
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer',
            outline: 'none',
            minWidth: 120,
          }}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value} disabled={opt.disabled}>
              {getOptionText(opt.label, opt.value)}
            </option>
          ))}
        </select>
        <span
          aria-hidden='true'
          style={{
            position: 'absolute',
            right: 14,
            top: '50%',
            transform: 'translateY(-50%)',
            pointerEvents: 'none',
            color: 'var(--fg-3)',
            fontSize: 10,
            lineHeight: 1,
          }}
        >
          {activeOption?.badge}
          <span style={{ marginLeft: activeOption?.badge ? 6 : 0 }}>▾</span>
        </span>
      </div>
    )
  }

  return (
    <div
      className={className}
      role='tablist'
      style={{
        display: equalWidth ? 'inline-grid' : 'inline-flex',
        ...(equalWidth
          ? { gridAutoFlow: 'column', gridAutoColumns: '1fr' }
          : null),
        alignItems: 'center',
        padding: 4,
        gap: 4,
        borderRadius: 999,
        background: 'var(--bg-2)',
        border: '1px solid var(--line)',
        ...style,
      }}
    >
      {options.map((opt) => {
        const active = opt.value === value
        return (
          <button
            key={opt.value}
            type='button'
            role='tab'
            aria-selected={active}
            disabled={opt.disabled}
            onClick={() => !opt.disabled && onChange(opt.value)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
              width: equalWidth ? '100%' : undefined,
              padding: '8px 20px',
              borderRadius: 999,
              border: 'none',
              cursor: opt.disabled ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit',
              fontSize: 13,
              fontWeight: active ? 600 : 500,
              color: active ? '#0B0814' : 'var(--fg-3)',
              background: active
                ? 'linear-gradient(90deg, var(--dawn-amber), var(--dawn-coral))'
                : 'transparent',
              opacity: opt.disabled ? 0.7 : 1,
              whiteSpace: 'nowrap',
              transition: 'color 160ms ease',
            }}
          >
            {opt.label}
            {opt.badge}
          </button>
        )
      })}
    </div>
  )
}
