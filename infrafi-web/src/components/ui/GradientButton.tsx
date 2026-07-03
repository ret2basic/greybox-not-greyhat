'use client'

import Link from 'next/link'
import type { CSSProperties, MouseEvent, ReactNode } from 'react'

type GradientButtonProps = {
  children: ReactNode
  size?: 'sm' | 'md'
  fullWidth?: boolean
  className?: string
  style?: CSSProperties
  href?: string
  target?: string
  rel?: string
  onClick?: (event: MouseEvent<HTMLElement>) => void
  type?: 'button' | 'submit' | 'reset'
  disabled?: boolean
  title?: string
  role?: string
  'aria-label'?: string
}

export function GradientButton({
  children,
  size = 'md',
  fullWidth = false,
  className,
  style,
  href,
  target,
  rel,
  onClick,
  type = 'button',
  disabled,
  title,
  role,
  'aria-label': ariaLabel,
}: GradientButtonProps) {
  const cls = ['gradient-btn', size === 'sm' && 'gradient-btn-sm', fullWidth && 'gradient-btn-block', className]
    .filter(Boolean)
    .join(' ')

  if (href !== undefined) {
    return (
      <Link
        href={href}
        className={cls}
        style={style}
        target={target}
        rel={rel}
        onClick={onClick}
        title={title}
        role={role}
        aria-label={ariaLabel}
      >
        {children}
      </Link>
    )
  }

  return (
    <button
      type={type}
      className={cls}
      style={style}
      onClick={onClick}
      disabled={disabled}
      title={title}
      role={role}
      aria-label={ariaLabel}
    >
      {children}
    </button>
  )
}
