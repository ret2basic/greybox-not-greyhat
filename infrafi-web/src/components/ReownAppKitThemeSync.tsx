'use client'

import { useEffect, useRef } from 'react'
import { useAppKitTheme } from '@reown/appkit/react'
import { reownThemeVariables, reownTokenOverrides } from '@/config/reownTheme'

export function ReownAppKitThemeSync() {
  const { setThemeMode, setThemeVariables } = useAppKitTheme()
  const hasAppliedThemeRef = useRef(false)

  useEffect(() => {
    if (hasAppliedThemeRef.current) {
      return
    }

    hasAppliedThemeRef.current = true

    const applyTheme = () => {
      setThemeMode('dark')
      setThemeVariables(reownThemeVariables)

      for (const [property, value] of Object.entries(reownTokenOverrides)) {
        document.documentElement.style.setProperty(property, value, 'important')
      }
    }

    applyTheme()
    const animationFrameId = window.requestAnimationFrame(applyTheme)
    const timeoutId = window.setTimeout(applyTheme, 250)

    return () => {
      window.cancelAnimationFrame(animationFrameId)
      window.clearTimeout(timeoutId)
    }
  }, [setThemeMode, setThemeVariables])

  return null
}
