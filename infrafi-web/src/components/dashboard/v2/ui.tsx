'use client'

import type { CSSProperties, ReactNode } from 'react'
import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { DeltaArrow } from './charts'

type Rect = { left: number; top: number; width: number; height: number }

// True only for the copy of a card's content rendered inside the expand modal.
// Charts read it to draw their axis/scale/gridline-rich variant when focused.
const ExpandedContext = createContext(false)
export const useExpanded = () => useContext(ExpandedContext)

export function InfoBadge({ title }: { title?: string }) {
  const ref = useRef<HTMLSpanElement>(null)
  const [tip, setTip] = useState<{ left: number; top: number } | null>(null)

  const show = () => {
    const el = ref.current
    if (!el) return
    const r = el.getBoundingClientRect()
    setTip({ left: r.left + r.width / 2, top: r.top })
  }
  const hide = () => setTip(null)

  return (
    <span
      ref={ref}
      className='dash-info'
      aria-label={title}
      tabIndex={title ? 0 : undefined}
      onMouseEnter={title ? show : undefined}
      onMouseLeave={title ? hide : undefined}
      onFocus={title ? show : undefined}
      onBlur={title ? hide : undefined}
    >
      i
      {title &&
        tip &&
        createPortal(
          <span className='dash-info-tip' style={{ left: tip.left, top: tip.top }}>
            {title}
          </span>,
          document.body,
        )}
    </span>
  )
}

export function DeltaPill({ value, positive }: { value: string; positive: boolean }) {
  return (
    <span className={`dash-delta ${positive ? 'pos' : 'neg'}`}>
      <DeltaArrow up={positive} />
      {value}
    </span>
  )
}

// Expand glyph (top-right of cards) — affordance for the click-to-expand
// interaction handled by Card.
export function ExpandGlyph() {
  return (
    <svg className='dash-expand' viewBox='0 0 10.9375 10.9375' fill='none' aria-hidden>
      <path
        d='M0.46875 2.96875V0.46875H2.96875M0.46875 0.46875L3.59375 3.59375M10.4688 2.96875V0.46875H7.96875M10.4688 0.46875L7.34375 3.59375M0.46875 7.96875V10.4688H2.96875M0.46875 10.4688L3.59375 7.34375M10.4688 7.96875V10.4688H7.96875M10.4688 10.4688L7.34375 7.34375'
        stroke='currentColor'
        strokeWidth='0.9375'
        strokeLinecap='round'
        strokeLinejoin='round'
      />
    </svg>
  )
}

export function Card({
  children,
  className = '',
  style,
  expandable = true,
  detail,
}: {
  children: ReactNode
  className?: string
  style?: CSSProperties
  expandable?: boolean
  // Optional bespoke content for the expand modal. When provided it replaces
  // the collapsed card content inside the focused panel (the design's "detail"
  // view); otherwise the modal simply re-renders the card.
  detail?: ReactNode
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [origin, setOrigin] = useState<Rect | null>(null)

  const open = () => {
    const el = ref.current
    if (!el) return
    const r = el.getBoundingClientRect()
    setOrigin({ left: r.left, top: r.top, width: r.width, height: r.height })
  }

  // Clicks on inner controls (toggles, buttons, links) must not expand.
  // The card itself is role="button", so it's excluded from this selector.
  const isInteractive = (target: EventTarget | null) =>
    target instanceof Element && !!target.closest('button, a, input, select, textarea, [role="tab"]')

  return (
    <>
      <div
        ref={ref}
        className={`dash-card ${expandable ? 'is-expandable' : ''} ${className}`.trim()}
        style={style}
        onClick={expandable ? (e) => !isInteractive(e.target) && open() : undefined}
        role={expandable ? 'button' : undefined}
        tabIndex={expandable ? 0 : undefined}
        onKeyDown={
          expandable
            ? (e) => {
                if ((e.key === 'Enter' || e.key === ' ') && e.target === e.currentTarget) {
                  e.preventDefault()
                  open()
                }
              }
            : undefined
        }
      >
        {children}
      </div>
      {origin && (
        <CardModal origin={origin} onClose={() => setOrigin(null)}>
          {detail ?? children}
        </CardModal>
      )}
    </>
  )
}

// Focused expand modal. Morphs from the card's on-screen rect to a centered
// panel using a FLIP transform, then back again on close.
function CardModal({ origin, onClose, children }: { origin: Rect; onClose: () => void; children: ReactNode }) {
  const cardRef = useRef<HTMLDivElement>(null)
  const [phase, setPhase] = useState<'opening' | 'open' | 'closing'>('opening')
  const [target, setTarget] = useState<Rect | null>(null)

  // Mount in 'opening' so the panel lays out at its natural centered position;
  // measure that rect, apply the FLIP transform onto the origin card, then on
  // the next frames release it so it animates to the docked position.
  useEffect(() => {
    if (phase !== 'opening' || !cardRef.current) return
    if (!target) {
      const r = cardRef.current.getBoundingClientRect()
      setTarget({ left: r.left, top: r.top, width: r.width, height: r.height })
      return
    }
    let r2 = 0
    const r1 = requestAnimationFrame(() => {
      r2 = requestAnimationFrame(() => setPhase('open'))
    })
    return () => {
      cancelAnimationFrame(r1)
      if (r2) cancelAnimationFrame(r2)
    }
  }, [phase, target])

  const close = () => {
    setPhase('closing')
    setTimeout(onClose, 180)
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close()
    }
    window.addEventListener('keydown', onKey)
    // Lock scroll without compensating for the scrollbar: the global stylesheet
    // sets `html { scrollbar-gutter: stable }` so the gutter is permanently
    // reserved. Adding padding-right here would double-reserve and shift the
    // page left while the modal is open.
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Close skips the morph entirely — the card just fades away in place.
  const opening = phase === 'opening'
  const closing = phase === 'closing'
  const useTransition = phase === 'open' || closing
  let transform = 'translate(0px, 0px) scale(1, 1)'
  let opacity = 1
  if (opening && target) {
    const dx = origin.left + origin.width / 2 - (target.left + target.width / 2)
    const dy = origin.top + origin.height / 2 - (target.top + target.height / 2)
    transform = `translate(${dx}px, ${dy}px) scale(${origin.width / target.width}, ${origin.height / target.height})`
    opacity = 0.85
  }
  if (closing) {
    opacity = 0
  }

  return createPortal(
    <div
      className={`dash dash-modal-root ${phase === 'open' ? 'is-open' : ''} ${closing ? 'is-closing' : ''}`.trim()}
    >
      <div className='dash-modal-backdrop' onMouseDown={close} />
      <div className='dash-modal-stage'>
        <div
          ref={cardRef}
          className='dash-modal-card'
          onMouseDown={(e) => e.stopPropagation()}
          style={{
            transform,
            opacity,
            transition: closing
              ? 'opacity 180ms ease'
              : useTransition
                ? 'transform 280ms cubic-bezier(0.2, 0.7, 0.2, 1), opacity 200ms ease, box-shadow 280ms ease'
                : 'none',
          }}
        >
          <button type='button' className='dash-modal-close' onClick={close} aria-label='Close'>
            <svg viewBox='0 0 24 24' width='14' height='14' fill='none' aria-hidden>
              <path d='M6 6l12 12M18 6L6 18' stroke='currentColor' strokeWidth='2' strokeLinecap='round' />
            </svg>
          </button>
          <ExpandedContext.Provider value={true}>{children}</ExpandedContext.Provider>
        </div>
      </div>
    </div>,
    document.body,
  )
}
