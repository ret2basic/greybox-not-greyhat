'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'

const linkStyle: React.CSSProperties = {
  fontSize: 10,
  color: 'var(--fg-3)',
  letterSpacing: '0.14em',
  textTransform: 'uppercase',
}

const Dot = () => (
  <span style={{ width: 4, height: 4, background: 'var(--fg-4)', borderRadius: 2 }} />
)

export const FooterTicker = () => {
  const [isSmallScreen, setIsSmallScreen] = useState(false)

  useEffect(() => {
    const media = window.matchMedia('(max-width: 1024px)')
    const sync = () => setIsSmallScreen(media.matches)
    sync()
    media.addEventListener('change', sync)
    return () => media.removeEventListener('change', sync)
  }, [])

  return (
    <footer
      style={{
        marginTop: 'auto',
        borderTop: '1px solid var(--line)',
        background: '#0E0F14',
        padding: isSmallScreen ? '14px 16px' : '0 32px',
      }}
    >
      <div
        className='app-container'
        style={{
          display: 'flex',
          gap: 18,
          alignItems: 'center',
          flexWrap: 'wrap',
          minHeight: isSmallScreen ? 'auto' : 50,
          padding: 0,
        }}
      >
        <span
          className='mono'
          style={{
            fontSize: 10,
            letterSpacing: '0.16em',
            color: 'var(--fg-3)',
            textTransform: 'uppercase',
          }}
        >
          {'// PROTOCOL_STATUS'}
        </span>
        <span
          className='mono'
          style={{ fontSize: 10, color: 'var(--pos)', letterSpacing: '0.14em' }}
        >
          ● HEALTHY
        </span>
        <div style={{ flex: 1 }} />
        <Link className='mono' href='/terms' style={linkStyle}>
          Terms &amp; Conditions
        </Link>
        <Dot />
        <Link className='mono' href='/privacy' style={linkStyle}>
          Privacy Policy
        </Link>
        <Dot />
        <span
          className='mono'
          style={{ fontSize: 10, color: 'var(--fg-4)', letterSpacing: '0.14em' }}
        >
          © 2026 DAWN OPS
        </span>
      </div>
    </footer>
  )
}
