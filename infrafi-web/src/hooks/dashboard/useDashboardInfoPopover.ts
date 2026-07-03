'use client'

import { type CSSProperties, useEffect, useId, useRef, useState } from 'react'

const MOBILE_BREAKPOINT_PX = 768
const SCREEN_EDGE_PADDING_PX = 12
const POPOVER_GAP_PX = 4
const ARROW_WIDTH_PX = 20
const ARROW_HALF_WIDTH_PX = ARROW_WIDTH_PX / 2
const ARROW_EDGE_PADDING_PX = 16

export const useDashboardInfoPopover = () => {
  const [isOpen, setIsOpen] = useState(false)
  const triggerRef = useRef<HTMLDivElement | null>(null)
  const popoverRef = useRef<HTMLDivElement | null>(null)
  const contentId = useId()
  const [popoverStyle, setPopoverStyle] = useState<CSSProperties | undefined>()
  const [arrowOffset, setArrowOffset] = useState<number>(ARROW_EDGE_PADDING_PX)
  const [isMobilePositioned, setIsMobilePositioned] = useState(false)

  useEffect(() => {
    if (!isOpen) {
      setPopoverStyle(undefined)
      setIsMobilePositioned(false)
      return
    }

    const handlePointerDown = (event: PointerEvent) => {
      if (!triggerRef.current?.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsOpen(false)
      }
    }

    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('keydown', handleEscape)

    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) {
      return
    }

    const updatePopoverPosition = () => {
      if (!triggerRef.current || !popoverRef.current) {
        return
      }

      if (window.innerWidth >= MOBILE_BREAKPOINT_PX) {
        setPopoverStyle(undefined)
        setArrowOffset(ARROW_EDGE_PADDING_PX)
        setIsMobilePositioned(false)
        return
      }

      const triggerRect = triggerRef.current.getBoundingClientRect()
      const popoverRect = popoverRef.current.getBoundingClientRect()

      const left = Math.max(
        SCREEN_EDGE_PADDING_PX,
        Math.min(
          triggerRect.left + triggerRect.width / 2 - popoverRect.width / 2,
          window.innerWidth - SCREEN_EDGE_PADDING_PX - popoverRect.width,
        ),
      )
      const top = Math.max(
        SCREEN_EDGE_PADDING_PX,
        triggerRect.top - popoverRect.height - POPOVER_GAP_PX,
      )
      const triggerCenterX = triggerRect.left + triggerRect.width / 2
      const pointerWithinPopover = triggerCenterX - left
      const arrowLeft = Math.max(
        ARROW_EDGE_PADDING_PX,
        Math.min(
          pointerWithinPopover - ARROW_HALF_WIDTH_PX,
          popoverRect.width - ARROW_EDGE_PADDING_PX - ARROW_WIDTH_PX,
        ),
      )

      setPopoverStyle({
        left: `${left}px`,
        top: `${top}px`,
      })
      setArrowOffset(arrowLeft)
      setIsMobilePositioned(true)
    }

    updatePopoverPosition()
    window.addEventListener('resize', updatePopoverPosition)
    window.addEventListener('scroll', updatePopoverPosition, true)

    return () => {
      window.removeEventListener('resize', updatePopoverPosition)
      window.removeEventListener('scroll', updatePopoverPosition, true)
    }
  }, [isOpen])

  const openPopover = () => setIsOpen(true)
  const closePopover = () => setIsOpen(false)
  const togglePopover = () => setIsOpen((currentValue) => !currentValue)

  return {
    arrowOffset,
    closePopover,
    contentId,
    isOpen,
    isMobilePositioned,
    openPopover,
    popoverRef,
    popoverStyle,
    togglePopover,
    triggerRef,
  }
}
