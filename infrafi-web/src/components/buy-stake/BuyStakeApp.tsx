'use client'

// Client-only wrapper that recreates v6's <App> tree exactly:
// AppLoader + screen content as siblings inside the same React render.
//
// Why this exists: v6 is a pure CSR SPA mounted into <div id="root">,
// which is the environment AppLoader was built for. Our Next.js App
// Router defaults to SSR, which puts the screen content behind a
// Suspense boundary (because BuyStakePageContent uses useSearchParams)
// and creates timing issues that AppLoader's design assumptions
// don't cover.
//
// The fix isn't to keep adapting AppLoader to fit SSR — it's to give
// AppLoader the environment it expects. We do that here by gating
// everything behind a `mounted` flag flipped in useEffect: on the
// server we render null, on the client we render the v6-shape tree
// once mount completes. There is no SSR HTML for the buy-stake page
// content; the loader and screen come up together at first client
// commit, exactly like v6.

import { Suspense, useEffect, useState } from 'react'
import { AppLoader } from '@/components/AppLoader'
import { BuyStakePageContent } from '@/components/buy-stake'

export default function BuyStakeApp() {
  const [mounted, setMounted] = useState(false)
  useEffect(() => {
    setMounted(true)
  }, [])
  if (!mounted) return null
  return (
    <>
      {/* AppLoader is rendered FIRST in source order so its
          position:fixed overlay sits above the page content. Both
          mount in the same React render — exactly like v6 App():
            return <><AppLoader/><BuyStakeScreen/></>
          AppLoader internally gates on sessionStorage and returns
          null when it shouldn't play (repeat visitors). */}
      <AppLoader />
      {/* The Suspense is only here because BuyStakePageContent uses
          useSearchParams, which is a Next.js requirement. Since the
          whole tree is client-only (mounted is false on server),
          this Suspense doesn't trigger SSR fallback semantics. */}
      <Suspense fallback={null}>
        <BuyStakePageContent />
      </Suspense>
    </>
  )
}
