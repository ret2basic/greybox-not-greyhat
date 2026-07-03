'use client'

import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent,
  type ReactNode,
} from 'react'

// Source rect captured from the card on click — used to drive ChartModal's
// FLIP morph animation so the modal appears to grow from this card.
export type SourceRect = {
  left: number
  top: number
  width: number
  height: number
}

type Props = {
  children: ReactNode
  onExpand?: (rect: SourceRect | null) => void
  padding?: number
  style?: CSSProperties
  description?: string
}

// Card that:
//  - shows a "What is this?" tooltip after a 350ms hover delay (when description provided)
//  - lifts + glows orange-amber on hover when onExpand is set
//  - clicks to expand, opening the modal owned by the parent
//  - suppresses the tooltip while the cursor sits over a child marked with
//    `data-suppress-tip="1"` (e.g. inner charts that have their own tooltip)
export function ExpandableCard({
  children,
  onExpand,
  padding = 24,
  style,
  description,
}: Props) {
  const [hover, setHover] = useState(false)
  const [showTip, setShowTip] = useState(false)
  const [insideSuppress, setInsideSuppress] = useState(false)
  const tipTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const cardRef = useRef<HTMLDivElement | null>(null)

  const handleClick = () => {
    if (!onExpand) return
    const r = cardRef.current?.getBoundingClientRect()
    onExpand(
      r
        ? { left: r.left, top: r.top, width: r.width, height: r.height }
        : null,
    )
  }

  useEffect(() => () => {
    if (tipTimer.current) clearTimeout(tipTimer.current)
  }, [])

  const onEnter = () => {
    setHover(true)
    if (description) {
      if (tipTimer.current) clearTimeout(tipTimer.current)
      tipTimer.current = setTimeout(() => setShowTip(true), 350)
    }
  }
  const onLeave = () => {
    setHover(false)
    setInsideSuppress(false)
    if (tipTimer.current) clearTimeout(tipTimer.current)
    setShowTip(false)
  }

  // Walk up from the actual hover target until we either find a suppress
  // marker inside this card or hit the card root itself.
  const checkSuppress = (e: MouseEvent<HTMLDivElement>) => {
    if (!description) return
    let n: Node | null = e.target as Node
    let found = false
    while (n && n !== e.currentTarget) {
      if (n instanceof HTMLElement && n.dataset.suppressTip === '1') {
        found = true
        break
      }
      n = n.parentNode
    }
    setInsideSuppress(found)
  }

  return (
    <div
      ref={cardRef}
      className='card'
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      onMouseOver={checkSuppress}
      onMouseOut={checkSuppress}
      onClick={handleClick}
      style={{
        padding,
        minWidth: 0,
        maxWidth: '100%',
        boxSizing: 'border-box',
        overflow: 'hidden',
        cursor: onExpand ? 'pointer' : 'default',
        transition:
          'border-color 220ms ease, transform 220ms ease, box-shadow 220ms ease, background-color 220ms ease',
        borderColor:
          hover && onExpand
            ? 'rgba(243,162,74,0.55)'
            : hover
              ? 'var(--line-strong)'
              : 'var(--line)',
        boxShadow:
          hover && onExpand
            ? '0 22px 60px -20px rgba(0,0,0,0.75), 0 0 0 1px rgba(243,162,74,0.32) inset, 0 0 36px -10px rgba(243,162,74,0.22)'
            : 'none',
        transform: hover && onExpand ? 'translateY(-3px)' : 'translateY(0)',
        ...style,
      }}
    >
      {children}
      {description && (
        <div
          aria-hidden
          style={{
            position: 'absolute',
            top: 14,
            right: 14,
            width: 280,
            padding: '12px 14px',
            borderRadius: 10,
            background: 'rgba(17,20,26,0.96)',
            backdropFilter: 'blur(8px)',
            WebkitBackdropFilter: 'blur(8px)',
            border: '1px solid rgba(243,162,74,0.28)',
            boxShadow: '0 14px 40px -12px rgba(0,0,0,0.7)',
            opacity: showTip && !insideSuppress ? 1 : 0,
            transform: showTip && !insideSuppress ? 'translateY(0)' : 'translateY(-4px)',
            transition: 'opacity 180ms ease, transform 220ms cubic-bezier(.2,.7,.2,1)',
            pointerEvents: 'none',
            zIndex: 5,
          }}
        >
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 9,
              letterSpacing: '0.16em',
              color: '#F3A24A',
              marginBottom: 6,
              textTransform: 'uppercase',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <svg width='11' height='11' viewBox='0 0 12 12' fill='none' aria-hidden>
              <circle cx='6' cy='6' r='5' stroke='currentColor' strokeWidth='1.2' />
              <path
                d='M6 5.5v2.5M6 3.8v0.4'
                stroke='currentColor'
                strokeWidth='1.2'
                strokeLinecap='round'
              />
            </svg>
            <span>What is this?</span>
          </div>
          <div
            style={{
              fontSize: 12.5,
              lineHeight: 1.5,
              color: 'var(--fg-2)',
              letterSpacing: '0.005em',
            }}
          >
            {description}
          </div>
        </div>
      )}
    </div>
  )
}
