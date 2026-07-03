'use client'

import Image from 'next/image'
import { createPortal } from 'react-dom'
import { useEffect, useState } from 'react'
import restrictedMapSvg from '@/assets/restricted-ip/restricted-map.svg'
import { useCompliance } from '@/store'

function RestrictedAccessMessage() {
  return (
    <div className='flex w-full max-w-[760px] flex-col'>
      <Image
        src={restrictedMapSvg}
        alt=''
        width={1006}
        height={587}
        priority
        className='h-auto w-full'
      />
      <div className='flex flex-col items-center gap-3 px-6 pb-10 pt-8 text-center'>
        <h2 className='text-[26px] font-semibold leading-tight text-white'>Access Restricted</h2>
        <p className='text-[15px] leading-normal text-white/60'>
          This service is not available in your region.
        </p>
      </div>
    </div>
  )
}

export function RestrictedAccessFullPage() {
  const [isMounted, setIsMounted] = useState(false)
  const status = useCompliance((state) => state.status)
  const show = status === 'blocked' || status === 'error'

  useEffect(() => {
    setIsMounted(true)
  }, [])

  useEffect(() => {
    if (!show) {
      return
    }

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    return () => {
      document.body.style.overflow = previousOverflow
    }
  }, [show])

  if (!isMounted || !show) {
    return null
  }

  return createPortal(
    <div
      className='fixed inset-0 z-100 flex items-center justify-center bg-black px-4'
      role='alert'
      aria-live='polite'
      aria-label='Restricted location notice'
    >
      <RestrictedAccessMessage />
    </div>,
    document.body,
  )
}

const RestrictedAccessModal = () => {
  const [isMounted, setIsMounted] = useState(false)
  const isOpen = useCompliance((state) => state.isRestrictionModalOpen)
  const closeModal = useCompliance((state) => state.closeRestrictionModal)

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

  if (!isMounted || !isOpen) {
    return null
  }

  return createPortal(
    <div
      className='fixed inset-0 z-90 flex items-center justify-center bg-black/80 px-4 py-6'
      onClick={closeModal}
    >
      <div
        role='dialog'
        aria-modal='true'
        aria-label='Restricted location notice'
        className='relative w-full max-w-[760px] overflow-hidden rounded-[12px] border border-white/20 bg-black'
        onClick={(event) => event.stopPropagation()}
      >
        <button
          type='button'
          aria-label='Close restricted location notice'
          onClick={closeModal}
          className='absolute right-[14px] top-[14px] z-1 inline-flex size-8 items-center justify-center text-white/60 transition-opacity hover:opacity-80'
        >
          <svg
            width='14'
            height='14'
            viewBox='0 0 14 14'
            fill='none'
            xmlns='http://www.w3.org/2000/svg'
            aria-hidden='true'
            className='block'
          >
            <path d='M2 2L12 12' stroke='currentColor' strokeWidth='1.8' strokeLinecap='round' />
            <path d='M12 2L2 12' stroke='currentColor' strokeWidth='1.8' strokeLinecap='round' />
          </svg>
        </button>

        <RestrictedAccessMessage />
      </div>
    </div>,
    document.body,
  )
}

export default RestrictedAccessModal
