'use client'

import { useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import type { SourceRect } from './ExpandableCard'

type Props = {
  open: boolean
  onClose: () => void
  title: string
  kicker: string
  children: ReactNode
  /**
   * Bounding rect of the source card at click time. Drives the FLIP morph
   * — modal appears at the card's position/size, then animates to its
   * natural centered shape.
   */
  originRect?: SourceRect | null
}

type Phase = 'closed' | 'opening' | 'open' | 'closing'

const OPEN_DURATION = 320
const CLOSE_DURATION = 280

// Full-screen overlay that mounts at its natural size, then runs a FLIP
// (First-Last-Invert-Play) animation so the modal card appears to grow
// from the source card and shrink back when closing.
export function ChartModal({
  open,
  onClose,
  title,
  kicker,
  children,
  originRect,
}: Props) {
  const [phase, setPhase] = useState<Phase>('closed')
  const [targetRect, setTargetRect] = useState<SourceRect | null>(null)
  const cardRef = useRef<HTMLDivElement | null>(null)
  // Snapshot of originRect taken at open time. The parent typically clears
  // its modal state when our `onClose` fires (CLOSE_DURATION - 40ms into
  // the close), which would null out the prop mid-animation and snap the
  // card to identity for the final ~40ms — a visible flash. Caching
  // locally keeps the FLIP-back stable through the whole close.
  const originRectRef = useRef<SourceRect | null>(null)

  // Drive the phase machine from the external `open` prop.
  useEffect(() => {
    if (!open) {
      setPhase((p) => (p === 'open' || p === 'opening' ? 'closing' : p))
      return
    }
    originRectRef.current = originRect ?? null
    setPhase('opening')
    setTargetRect(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  // Two-pass effect during 'opening':
  //   pass 1 — measure card's natural rect, store it (triggers re-render
  //            with FLIP transform applied to that rect).
  //   pass 2 — RAF×2, then flip phase to 'open' so transition animates
  //            the FLIP transform back to identity.
  useEffect(() => {
    if (phase !== 'opening') return
    if (!cardRef.current) return

    if (!targetRect) {
      const r = cardRef.current.getBoundingClientRect()
      setTargetRect({ left: r.left, top: r.top, width: r.width, height: r.height })
      return
    }

    let raf2 = 0
    const raf1 = requestAnimationFrame(() => {
      raf2 = requestAnimationFrame(() => setPhase('open'))
    })
    return () => {
      cancelAnimationFrame(raf1)
      if (raf2) cancelAnimationFrame(raf2)
    }
  }, [phase, targetRect])

  // Settle 'closing' → 'closed' after the close animation finishes.
  useEffect(() => {
    if (phase !== 'closing') return
    const t = setTimeout(() => {
      setPhase('closed')
      setTargetRect(null)
    }, CLOSE_DURATION)
    return () => clearTimeout(t)
  }, [phase])

  // Esc to close + body scroll lock. Width compensation isn't needed
  // because html has `scrollbar-gutter: stable` — the gutter persists
  // whether or not the scrollbar is currently visible, so toggling
  // body overflow:hidden doesn't change the viewport content width.
  useEffect(() => {
    if (phase === 'closed') return

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose()
    }
    window.addEventListener('keydown', onKey)

    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase])

  const handleClose = () => {
    if (phase === 'closing' || phase === 'closed') return
    setPhase('closing')
    // Tell the parent we're closed once the morph-back has (mostly)
    // completed so the parent can clear its modal state.
    setTimeout(onClose, CLOSE_DURATION - 40)
  }

  if (phase === 'closed') return null
  if (typeof window === 'undefined') return null

  // FLIP transform: invert the natural→source delta so the card appears
  // at the source rect, then we let the transition animate it home.
  // Read from the cached ref so the close animation is immune to the
  // parent clearing originRect mid-flight.
  const cachedOrigin = originRectRef.current
  const isMorphing = phase === 'opening' || phase === 'closing'
  let cardTransform = 'translate(0, 0) scale(1)'
  let cardOpacity = 1

  if (isMorphing && cachedOrigin && targetRect) {
    const dx =
      cachedOrigin.left + cachedOrigin.width / 2 -
      (targetRect.left + targetRect.width / 2)
    const dy =
      cachedOrigin.top + cachedOrigin.height / 2 -
      (targetRect.top + targetRect.height / 2)
    const sx = cachedOrigin.width / targetRect.width
    const sy = cachedOrigin.height / targetRect.height
    cardTransform = `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})`
    cardOpacity = 0.85
  }

  // Suppress transition during the FIRST FLIP-position paint so the
  // browser doesn't animate identity → FLIP. Enable transitions only
  // when we're going TO 'open' or BACK from 'open' (i.e. closing).
  const useTransition = phase === 'open' || phase === 'closing'
  const showChrome = phase === 'open'

  // FLIP first-paint flash guard: on the very first render of 'opening',
  // targetRect is null because the measurement effect hasn't run yet, so
  // the card would paint at its natural centered size for one frame
  // before snapping to the FLIP transform — visible to the user as a
  // "ghost modal" flash. visibility:hidden preserves layout (so the ref
  // can still be measured) but doesn't paint. We only need this guard
  // when there's an originRect to morph from; without one the modal
  // just opens with a fade and natural-size paint is correct.
  const hideForMeasure = phase === 'opening' && !!cachedOrigin && !targetRect

  return createPortal(
    <div
      className='theme-midnight'
      style={{ position: 'fixed', inset: 0, zIndex: 200 }}
    >
      {/* Backdrop — fades in/out independently of the morph */}
      <div
        onMouseDown={handleClose}
        style={{
          position: 'absolute',
          inset: 0,
          background: 'rgba(11,8,20,0.72)',
          backdropFilter: 'blur(8px)',
          WebkitBackdropFilter: 'blur(8px)',
          cursor: 'zoom-out',
          opacity: phase === 'open' ? 1 : 0,
          transition: 'opacity 280ms ease',
        }}
      />
      {/* Centering wrapper — pointer-events: none so dead space passes
          clicks through to the backdrop. Inner card re-enables them.
          Sized via CSS (.chart-modal-stage / .chart-modal-card) so media
          queries can collapse padding + widen the card on mobile, mirroring
          the dashboard's CardModal exactly. */}
      <div className='chart-modal-stage'>
        <div
          ref={cardRef}
          role='dialog'
          aria-modal='true'
          aria-labelledby='chart-modal-title'
          className='chart-modal-card'
          onMouseDown={(e) => e.stopPropagation()}
          style={{
            boxShadow:
              phase === 'open'
                ? '0 40px 120px -20px rgba(0,0,0,0.7)'
                : '0 22px 60px -20px rgba(0,0,0,0.45)',
            transform: cardTransform,
            transformOrigin: 'center center',
            opacity: cardOpacity,
            visibility: hideForMeasure ? 'hidden' : 'visible',
            transition: useTransition
              ? `transform ${OPEN_DURATION}ms cubic-bezier(.2,.7,.2,1), opacity 240ms ease, box-shadow 280ms ease`
              : 'none',
            willChange: 'transform, opacity',
          }}
        >
          {/* Inner content fades in once docked so the card-shaped frame
              doesn't show modal chrome while it's still tiny. Slight
              delay on the open direction lets the morph mostly settle
              before the chrome reveals. */}
          <div
            style={{
              opacity: showChrome ? 1 : 0,
              transition: showChrome
                ? 'opacity 220ms ease 100ms'
                : 'opacity 140ms ease',
            }}
          >
            <button
              type='button'
              onClick={handleClose}
              aria-label='Close'
              className='chart-modal-close'
            >
              ×
            </button>
            <div className='chart-modal-head'>
              <div
                className='kicker'
                style={{ marginBottom: 8, color: 'var(--dawn-amber)' }}
              >
                {kicker}
              </div>
              <h2 id='chart-modal-title' className='h-section chart-modal-title'>
                {title}
              </h2>
            </div>
            {children}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}
