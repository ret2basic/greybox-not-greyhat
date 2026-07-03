'use client'

import { type FC, type ReactNode, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Image from 'next/image'
import darkPopoverArrowIcon from '@/assets/icons/dark-popover-arrow.svg'
import infoCircleGrayIcon from '@/assets/icons/info-circle-gray.svg'
import { useDashboardInfoPopover } from '@/hooks/dashboard/useDashboardInfoPopover'

type DashboardInfoPopoverProps = {
  ariaLabel: string
  content: string
  widthClassName: string
  trigger?: ReactNode
}

const DashboardInfoPopover: FC<DashboardInfoPopoverProps> = ({
  ariaLabel,
  content,
  widthClassName,
  trigger,
}) => {
  const {
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
  } = useDashboardInfoPopover()
  const [isClient, setIsClient] = useState(false)
  const touchHandledRef = useRef(false)

  const supportsHoverPointer = () =>
    typeof window !== 'undefined' && window.matchMedia('(hover: hover) and (pointer: fine)').matches

  useEffect(() => {
    setIsClient(true)
  }, [])

  const popoverContent = (
    <div
      ref={popoverRef}
      style={isMobilePositioned ? popoverStyle : undefined}
      className={`${isMobilePositioned ? 'fixed z-10010' : 'absolute bottom-full left-[-16px] z-10010 mb-[4px]'} max-w-[calc(100vw-24px)] ${widthClassName} transition-opacity duration-200 ${
        isOpen ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0'
      }`}
    >
      <div
        id={contentId}
        role='tooltip'
        className='rounded-[8px] border border-[#E97B40] bg-black px-[16px] py-[12px] shadow-[0_2px_4px_rgba(0,0,0,0.15)]'
      >
        <p className='text-[14px] font-normal leading-[18px] text-white'>{content}</p>
      </div>

      <div
        className='flex h-[12px] items-start pl-[16px]'
        style={isMobilePositioned ? { paddingLeft: `${arrowOffset}px` } : undefined}
      >
        <Image
          src={darkPopoverArrowIcon}
          alt=''
          width={20}
          height={12}
          className='pointer-events-none block h-[12px] w-[20px]'
        />
      </div>
    </div>
  )

  return (
    <div
      ref={triggerRef}
      className='relative shrink-0'
      onMouseEnter={() => {
        if (supportsHoverPointer()) {
          openPopover()
        }
      }}
      onMouseLeave={() => {
        if (supportsHoverPointer()) {
          closePopover()
        }
      }}
    >
      <button
        type='button'
        aria-label={ariaLabel}
        aria-describedby={isOpen ? contentId : undefined}
        aria-expanded={isOpen}
        onPointerDown={(event) => {
          if (event.pointerType !== 'touch') {
            return
          }

          touchHandledRef.current = true
          event.preventDefault()
          event.stopPropagation()
          togglePopover()
        }}
        onClick={(event) => {
          if (touchHandledRef.current) {
            touchHandledRef.current = false
            return
          }

          event.stopPropagation()
          togglePopover()
        }}
        onFocus={openPopover}
        onBlur={(event) => {
          if (!triggerRef.current?.contains(event.relatedTarget as Node | null)) {
            closePopover()
          }
        }}
        className='flex size-[19px] items-center justify-center rounded-full transition-opacity md:hover:opacity-80 focus-visible:opacity-80'
      >
        {trigger ?? <Image src={infoCircleGrayIcon} alt='' width={19} height={19} className='shrink-0' />}
      </button>

      {isMobilePositioned && isClient ? createPortal(popoverContent, document.body) : popoverContent}
    </div>
  )
}

export default DashboardInfoPopover
