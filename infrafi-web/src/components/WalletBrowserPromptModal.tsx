'use client'

import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useCompliance } from '@/store'

const copyLinkWithExecCommand = (link: string) => {
  const textArea = document.createElement('textarea')
  textArea.value = link
  textArea.setAttribute('readonly', '')
  textArea.style.position = 'fixed'
  textArea.style.opacity = '0'
  textArea.style.pointerEvents = 'none'
  textArea.style.left = '-9999px'
  document.body.appendChild(textArea)
  textArea.focus()
  textArea.select()
  textArea.setSelectionRange(0, textArea.value.length)

  const isCopied = document.execCommand('copy')
  document.body.removeChild(textArea)
  return isCopied
}

const WalletBrowserPromptModal = () => {
  const [isMounted, setIsMounted] = useState(false)
  const [isLinkCopied, setIsLinkCopied] = useState(false)
  const [mobileDragOffset, setMobileDragOffset] = useState(0)
  const [isMobileDragging, setIsMobileDragging] = useState(false)
  const dragStartYRef = useRef<number | null>(null)
  const isOpen = useCompliance((state) => state.isWalletBrowserPromptOpen)
  const closeModal = useCompliance((state) => state.closeWalletBrowserPrompt)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  useEffect(() => {
    if (!isOpen) {
      return
    }

    const previousOverflow = document.body.style.overflow
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        closeModal()
      }
    }

    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', handleKeyDown)

    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [closeModal, isOpen])

  useEffect(() => {
    if (!isOpen) {
      return
    }
    setIsLinkCopied(false)
  }, [isOpen])

  if (!isMounted || !isOpen) {
    return null
  }

  const handleDragStart = (clientY: number) => {
    if (window.innerWidth >= 768) {
      return
    }
    dragStartYRef.current = clientY
  }

  const handleDragMove = (clientY: number) => {
    const startY = dragStartYRef.current
    if (startY === null) {
      return
    }
    const delta = clientY - startY
    if (delta > 0) {
      setIsMobileDragging(true)
      setMobileDragOffset(delta)
      return
    }
    setMobileDragOffset(0)
  }

  const handleDragEnd = () => {
    const shouldClose = mobileDragOffset > 100
    dragStartYRef.current = null
    setIsMobileDragging(false)
    setMobileDragOffset(0)
    if (shouldClose) {
      closeModal()
    }
  }

  const handleCopyLink = async () => {
    const appUrl = `${window.location.origin}/`
    let isCopied = false

    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(appUrl)
        isCopied = true
      } catch {
        isCopied = copyLinkWithExecCommand(appUrl)
      }
    } else {
      isCopied = copyLinkWithExecCommand(appUrl)
    }

    setIsLinkCopied(isCopied)
  }

  return createPortal(
    <div
      className='fixed inset-0 flex items-end bg-black/65 md:hidden'
      style={{ zIndex: 10000 }}
      onClick={closeModal}
    >
      <div
        role='dialog'
        aria-modal='true'
        aria-label='Open in wallet browser'
        className='w-full rounded-t-[26px] border border-white/12 bg-[#050505]'
        style={{
          transform: mobileDragOffset > 0 ? `translateY(${mobileDragOffset}px)` : undefined,
          transition: isMobileDragging ? 'none' : 'transform 180ms ease-out',
        }}
        onClick={(event) => event.stopPropagation()}
      >
        <div className='max-h-[calc(100vh-14px)] overflow-y-auto px-[20px] pb-[28px] pt-[8px]'>
          <div
            className='mb-[10px] flex justify-center'
            onTouchStart={(event) => handleDragStart(event.touches[0].clientY)}
            onTouchMove={(event) => {
              event.preventDefault()
              handleDragMove(event.touches[0].clientY)
            }}
            onTouchEnd={handleDragEnd}
            onTouchCancel={handleDragEnd}
            onMouseDown={(event) => handleDragStart(event.clientY)}
            onMouseMove={(event) => {
              if (dragStartYRef.current !== null) {
                handleDragMove(event.clientY)
              }
            }}
            onMouseUp={handleDragEnd}
            onMouseLeave={handleDragEnd}
          >
            <span className='h-[5px] w-[50px] rounded-full bg-[#2B2B2B]' />
          </div>

          <div className='flex items-start justify-between gap-4'>
            <h2 className='text-[18px] font-semibold leading-[26px] text-white'>
              Open in your wallet&apos;s browser
            </h2>
            <button
              type='button'
              aria-label='Close wallet browser prompt'
              onClick={closeModal}
              onTouchEnd={(event) => {
                event.preventDefault()
                event.stopPropagation()
                closeModal()
              }}
              className='mt-[4px] inline-flex size-[36px] shrink-0 items-center justify-center rounded-[11px] border border-white/10 bg-white/[0.07] text-white/70 transition-opacity hover:opacity-80'
            >
              <svg width='12' height='12' viewBox='0 0 12 12' fill='none' xmlns='http://www.w3.org/2000/svg'>
                <path d='M2 2L10 10' stroke='currentColor' strokeWidth='1.4' strokeLinecap='round' />
                <path d='M10 2L2 10' stroke='currentColor' strokeWidth='1.4' strokeLinecap='round' />
              </svg>
            </button>
          </div>

          <div className='mt-[16px] h-px w-full bg-white/10' />

          <p className='mt-[16px] text-[14px] leading-[165%] text-[#8B8B8B]'>
            To connect on mobile, copy the DAWN link and open it in your wallet app&apos;s browser.
          </p>

          <button
            type='button'
            onClick={() => void handleCopyLink()}
            onTouchEnd={(event) => {
              event.preventDefault()
              event.stopPropagation()
              void handleCopyLink()
            }}
            className='mt-[24px] inline-flex h-[52px] w-full items-center justify-center gap-[10px] rounded-[10px] border border-white/10 bg-[#0D0E10] text-[17px] font-semibold leading-[22px] text-white transition-opacity hover:opacity-90'
          >
            {isLinkCopied ? (
              <svg
                width='24'
                height='24'
                viewBox='0 0 24 24'
                fill='none'
                xmlns='http://www.w3.org/2000/svg'
                aria-hidden='true'
              >
                <circle cx='12' cy='12' r='10' stroke='#2ECC71' strokeWidth='1.8' />
                <path
                  d='M8 12.5L10.7 15.2L16.4 9.5'
                  stroke='#2ECC71'
                  strokeWidth='2'
                  strokeLinecap='round'
                  strokeLinejoin='round'
                />
              </svg>
            ) : (
              <svg
                width='24'
                height='24'
                viewBox='0 0 24 24'
                fill='none'
                xmlns='http://www.w3.org/2000/svg'
                aria-hidden='true'
              >
                <rect x='9' y='8' width='10' height='12' rx='2' stroke='currentColor' strokeWidth='1.6' />
                <path
                  d='M15 8V6C15 4.89543 14.1046 4 13 4H7C5.89543 4 5 4.89543 5 6V14C5 15.1046 5.89543 16 7 16H9'
                  stroke='currentColor'
                  strokeWidth='1.6'
                />
              </svg>
            )}
            {isLinkCopied ? 'Link copied' : 'Copy link'}
          </button>

          <button
            type='button'
            onClick={closeModal}
            onTouchEnd={(event) => {
              event.preventDefault()
              event.stopPropagation()
              closeModal()
            }}
            className='mt-[20px] block w-full text-center text-[17px] font-semibold leading-[22px] text-white transition-opacity hover:opacity-80'
          >
            Got it
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}

export default WalletBrowserPromptModal
