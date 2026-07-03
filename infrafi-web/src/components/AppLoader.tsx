'use client'

// AppLoader — boots InfraFi-Midnight with the EXACT Concept 06 visuals.
//
// Verbatim port of v6 src/AppLoader.jsx. The only deviations from v6
// are documented at each call site:
//
//   • MutationObserver replaces the rAF retry for h1 acquisition
//     (per Claude Design's SSR guidance — defends against any nested
//     Suspense delays even though our parent BuyStakeApp is CSR-only).
//   • firedOnceRef gates onDone so dev-mode StrictMode can't fire
//     sessionStorage.setItem twice (also per Claude Design).
//   • injectAppLoaderStyles adds one extra rule neutralizing our root
//     layout's `.z-1` Tailwind wrapper (which would otherwise cap the
//     h1 below the loader's backdrop).
//
// Architecture: type DIRECTLY INTO the real hero `<h1.h-display>`.
// No clones, no overlays, no DOM moves.
//
// Phases: TYPE 2000 / HOLD 1200 / GRID 700 / REVEAL 800.

import * as React from 'react'

const APPLOADER_TYPE   = 2000
const APPLOADER_HOLD   = 1200
const APPLOADER_GRID   = 700
const APPLOADER_REVEAL = 800
const APPLOADER_T_TYPE_END   = APPLOADER_TYPE
const APPLOADER_T_HOLD_END   = APPLOADER_T_TYPE_END + APPLOADER_HOLD
const APPLOADER_T_GRID_END   = APPLOADER_T_HOLD_END + APPLOADER_GRID
const APPLOADER_T_REVEAL_END = APPLOADER_T_GRID_END + APPLOADER_REVEAL
const APPLOADER_TOTAL        = APPLOADER_T_REVEAL_END

const STORAGE_KEY = 'infrafi_loader_played'

function injectAppLoaderStyles() {
  if (document.getElementById('app-loader-styles')) return
  const style = document.createElement('style')
  style.id = 'app-loader-styles'
  style.textContent = `
    @keyframes apploader-pulse { 0%,100%{opacity:1} 50%{opacity:0.45} }
    @keyframes apploader-blink { 0%,49%{opacity:1} 50%,100%{opacity:0} }

    /* Stacking-context neutralization for the hero h1 ancestors.
       Verbatim from v6 plus one Tailwind-specific rule for our
       root layout wrapper. These rules stay live after the loader
       unmounts so removing the body class doesn't trigger a
       compositing-layer change (which would cause a visible
       flicker). The neutralizations are harmless after boot — they
       just keep ancestors from creating stacking contexts they
       don't need. */
    .home.theme-midnight { isolation: auto !important; }
    /* Neutralize ONLY the app-shell wrapper's stacking context. This rule
       persists after the loader, so it must target the shell precisely —
       a broad child-div selector also matches React portals appended to
       the body (e.g. the mobile nav menu, modals), forcing their z-index
       to auto and dropping them below their own fixed backdrop. */
    .home.theme-midnight > .app-shell { z-index: auto !important; }
    /* Our Next.js root layout wraps the page in a div with
       Tailwind 'relative z-1' (z-index: 1). That creates a
       stacking context which CAPS the h1's z-index:10001 below
       the loader's backdrop at z:9999. Neutralize it so the h1's
       10001 takes effect at the root stacking context. */
    .home.theme-midnight .z-1 { z-index: auto !important; }
    .fade-up { transform: none !important; }
    /* h1 stacking-context lift is SCOPED to body.app-loader-active
       (deviation from v6's permanent rule). Reason: v6 keeps the
       rule live permanently to avoid a compositing-layer flicker
       on unmount, but in our app the TopNav is position:sticky
       with zIndex:50, so a permanent z-index:10001 on the h1 makes
       it paint OVER the TopNav whenever the user scrolls past it.
       Scoping to the body class means the lift only exists during
       the loader animation; once cleanup removes the body class,
       the h1 returns to default stacking and TopNav covers it
       normally on scroll. The flicker risk v6 was guarding against
       is masked by the REVEAL phase fade already in progress at
       cleanup. */
    body.app-loader-active h1.h-display {
      position: relative !important;
      z-index: 10001 !important;
    }
    /* The hero's wrapper uses an inline 'position:relative; z-index:1'
       which creates a stacking context that TRAPS the h1's z-index:10001
       below the loader backdrop at z:9999 (so the typed title paints
       behind the backdrop and never shows). Neutralize the wrapper's
       z-index while the loader is active so the h1 lift takes effect at
       the app-shell stacking context. Scoped to body.app-loader-active
       to match the h1 lift — once cleanup removes the body class, the
       wrapper returns to its normal z-index:1. */
    body.app-loader-active .app-container {
      z-index: auto !important;
    }
    /* The root layout wraps the page in '.app-shell' with an inline
       'isolation: isolate', which forces a root-level stacking context.
       That context sits at the z-auto layer, so its ENTIRE subtree —
       including this loader's z:9999 backdrop/chrome and the typed h1 —
       composites BELOW the pre-paint cover (html[data-loader] ::before
       at z:9998), leaving a flat black screen for the whole animation.
       Neutralize the isolation (and z-index) while the loader is active
       so the loader's 9999 competes at the root context and paints above
       the 9998 cover. !important overrides the inline isolation. Scoped
       to body.app-loader-active so .app-shell restores after cleanup. */
    body.app-loader-active .app-shell {
      isolation: auto !important;
      z-index: auto !important;
    }
    /* While the loader is mounted, suppress the .fade-up entry
       animation so the h1 (and its siblings inside the same
       wrapper) are visible at full opacity right away. */
    body.app-loader-active .fade-up {
      animation: none !important;
      opacity: 1 !important;
    }
  `
  document.head.appendChild(style)
}

// The hero headline the loader types. Kept at module scope so the
// typing logic and the deterministic "final markup" share one source
// of truth. Must stay 1:1 with BuyStakePageContent's <h1>:
//   "Broadband-backed <span class='gradient-text'>onchain&nbsp;yield.</span>"
const HERO_FULL = 'Broadband-backed onchain\u00A0yield.'
const HERO_ACCENT = 'onchain\u00A0yield.'

// Build the typed innerHTML for a given character count.
function buildTypedHTML(chars: number, withCursor: boolean): string {
  const FULL = HERO_FULL
  const ACCENT_TEXT = HERO_ACCENT
  const ACCENT_START = FULL.indexOf(ACCENT_TEXT)
  const ACCENT_END = ACCENT_START + ACCENT_TEXT.length

  let html = ''
  if (chars > 0) {
    const preEnd = Math.min(chars, ACCENT_START)
    const preText = FULL.slice(0, preEnd)
    html += escapeHTML(preText).replace(/\n/g, '<br>')
  }
  if (chars > ACCENT_START) {
    const accEnd = Math.min(chars, ACCENT_END)
    html += `<span class="gradient-text">${escapeHTML(FULL.slice(ACCENT_START, accEnd))}</span>`
  }
  if (withCursor) {
    html += `<span class="apploader-cursor" style="display:inline-block;width:4px;height:0.85em;background:var(--dawn-coral);margin-left:6px;vertical-align:-0.05em;animation:apploader-blink 0.6s steps(2) infinite;"></span>`
  }
  return html
}

function escapeHTML(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

// Deterministic final markup — the fully-typed headline with no cursor.
// Identical to BuyStakePageContent's <h1> contents, so the loader can
// restore the title without ever depending on a captured DOM snapshot
// (which could be empty if the h1 was acquired mid-render). The title
// is therefore guaranteed present after typing and stays pixel-aligned
// once the loader reveals the page.
function heroFinalHTML(): string {
  return buildTypedHTML(HERO_FULL.length, false)
}

// v6's gating pattern: lazy useState initializer reads sessionStorage
// once on first render. Works here because BuyStakeApp gates the
// entire tree behind a `mounted` flag — so this initializer only
// runs on the client where sessionStorage is defined. No SSR concern.
function shouldPlayInit(): boolean {
  try {
    return sessionStorage.getItem(STORAGE_KEY) !== '1'
  } catch {
    return false
  }
}

export function AppLoader({ onDone }: { onDone?: () => void } = {}) {
  // shouldPlay flips false ONCE — when the animation completes — and
  // never back to true. So `<AppLoader>` mounts at most one
  // animation per session. After done, it returns null; never
  // re-mounts (which would clobber refs and re-blank the h1).
  const [shouldPlay, setShouldPlay] = React.useState<boolean>(shouldPlayInit)

  // The skipped path: when shouldPlay is false (repeat visitor whose
  // sessionStorage flag is already set), the inline <script> in
  // layout.tsx <head> may still have set data-loader="active" on
  // <html> (because the URL matches and it doesn't know about
  // any per-component opt-outs). Remove it so the pre-paint CSS
  // cover lifts and the page becomes visible. The played path
  // handles its own cleanup inside AppLoaderInner.
  React.useEffect(() => {
    if (!shouldPlay && typeof document !== 'undefined') {
      document.documentElement.removeAttribute('data-loader')
    }
  }, [shouldPlay])

  if (!shouldPlay) return null

  return (
    <AppLoaderInner
      onDone={() => {
        try {
          sessionStorage.setItem(STORAGE_KEY, '1')
        } catch {
          /* noop */
        }
        setShouldPlay(false)
        onDone?.()
      }}
    />
  )
}

function AppLoaderInner({ onDone }: { onDone: () => void }) {
  const [now, setNow] = React.useState(0)
  const [done, setDone] = React.useState(false)
  const heroRef = React.useRef<HTMLElement | null>(null)
  const observerRef = React.useRef<MutationObserver | null>(null)
  const firedOnceRef = React.useRef(false) // StrictMode safety

  // Acquire real h1, save original markup, blank it for typing.
  React.useLayoutEffect(() => {
    injectAppLoaderStyles()
    document.body.classList.add('app-loader-active')

    const setupHero = (hero: HTMLElement) => {
      heroRef.current = hero
      // Blank the real h1 so typing starts from empty. We never capture
      // its current markup — restore uses heroFinalHTML() instead, which
      // is deterministic and can't be an empty snapshot.
      hero.innerHTML = ''
    }

    // Try synchronously first — if BuyStakePageContent has already
    // unwound from Suspense by the time we mount, the h1 is in DOM.
    const direct = document.querySelector<HTMLElement>('h1.h-display')
    if (direct) {
      setupHero(direct)
    } else {
      // Wait for the h1 via MutationObserver. Per Claude Design:
      // "If they're SSR'ing or have a suspense boundary delaying the
      // h1, you'd need a MutationObserver."
      const observer = new MutationObserver(() => {
        const found = document.querySelector<HTMLElement>('h1.h-display')
        if (found) {
          observer.disconnect()
          observerRef.current = null
          setupHero(found)
        }
      })
      observer.observe(document.body, { childList: true, subtree: true })
      observerRef.current = observer
    }

    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect()
        observerRef.current = null
      }
      const hero = heroRef.current
      if (hero) {
        hero.innerHTML = heroFinalHTML()
      }
      // Pin .fade-up to its final state via inline styles before
      // removing the body class — otherwise the browser may replay
      // the entry animation from frame 0.
      const fadeUps = document.querySelectorAll<HTMLElement>('.fade-up')
      fadeUps.forEach((el) => {
        el.style.animation = 'none'
        el.style.opacity = '1'
      })
      document.body.classList.remove('app-loader-active')
      // Lift the pre-paint CSS cover (set by the inline <script> in
      // layout.tsx <head>). At this point AppLoaderInner's REVEAL
      // phase has finished fading the React-rendered backdrop, so
      // removing the data-loader attribute drops the ::before cover
      // and the page becomes visible.
      document.documentElement.removeAttribute('data-loader')
    }
  }, [])

  // Animation timer — VERBATIM from v6: deps must be `[]`. setNow
  // re-renders this component every frame; if onDone were in deps,
  // each frame would clean up + re-run, resetting t0.
  React.useEffect(() => {
    let cancelled = false
    const t0 = performance.now()
    let rafId: number | null = null
    const tick = () => {
      if (cancelled) return
      const elapsed = performance.now() - t0
      setNow(elapsed)
      if (elapsed >= APPLOADER_TOTAL + 100) {
        setDone(true)
        // StrictMode safety: fire onDone at most once per instance.
        if (!firedOnceRef.current) {
          firedOnceRef.current = true
          onDone()
        }
        return
      }
      rafId = requestAnimationFrame(tick)
    }
    rafId = requestAnimationFrame(tick)
    return () => {
      cancelled = true
      if (rafId) cancelAnimationFrame(rafId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Drive the real h1's contents from `now`.
  React.useEffect(() => {
    const hero = heroRef.current
    if (!hero) return

    if (now < APPLOADER_T_TYPE_END) {
      // TYPE phase — type the headline character by character.
      const tType = Math.max(0, Math.min(1, now / APPLOADER_TYPE))
      const easedType = 1 - Math.pow(1 - tType, 2.0)
      const chars = Math.floor(easedType * HERO_FULL.length)
      const showCursor = chars < HERO_FULL.length
      hero.innerHTML = buildTypedHTML(chars, showCursor)
    } else {
      // Type complete — set the deterministic final markup so the
      // title is always present (never a blank snapshot).
      const finalHTML = heroFinalHTML()
      if (hero.innerHTML !== finalHTML) {
        hero.innerHTML = finalHTML
      }
    }
  }, [now])

  if (done) return null

  const tBar    = Math.max(0, Math.min(1, now / APPLOADER_TYPE))
  const tGrid   = Math.max(0, Math.min(1, (now - APPLOADER_T_HOLD_END) / APPLOADER_GRID))
  const tReveal = Math.max(0, Math.min(1, (now - APPLOADER_T_GRID_END) / APPLOADER_REVEAL))

  const phase =
    now < APPLOADER_T_TYPE_END   ? 'type' :
    now < APPLOADER_T_HOLD_END   ? 'hold' :
    now < APPLOADER_T_GRID_END   ? 'grid' :
                                   'reveal'

  const barProgress = 1 - Math.pow(1 - tBar, 1.4)
  const full = barProgress >= 0.999

  const step =
    full ? 'Vault open' :
    tBar < 0.30 ? 'Reading prospectus' :
    tBar < 0.60 ? 'Validating asset records' :
                  'Computing yield curves'

  const backdropOpacity =
    phase === 'reveal' ? Math.max(0, 1 - tReveal) : 1

  const gridOpacity =
    phase === 'type' || phase === 'hold' ? 0 :
    phase === 'grid' ? tGrid :
                       Math.max(0, 1 - tReveal)

  const loaderChromeOpacity =
    phase === 'type' || phase === 'hold' ? 1 :
    phase === 'grid' ? (() => {
      const x = 1 - tGrid
      return x < 0.5 ? 4*x*x*x : 1 - Math.pow(-2*x + 2, 3) / 2
    })() :
                       0

  const overlayOpacity = phase === 'reveal' ? Math.max(0, 1 - tReveal) : 1

  return (
    <div
      className='app-loader-root'
      aria-hidden='true'
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        pointerEvents: 'none',
        opacity: overlayOpacity,
      }}
    >
      <div style={{
        position: 'absolute', inset: 0,
        background: '#050608',
        opacity: backdropOpacity,
      }}/>

      <div style={{
        position: 'absolute', inset: 0,
        backgroundImage:
          'linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.045) 1px, transparent 1px)',
        backgroundSize: '56px 56px',
        WebkitMaskImage:
          'radial-gradient(ellipse 100% 90% at 50% 40%, #000 40%, rgba(0,0,0,0.6) 80%, transparent 100%)',
        maskImage:
          'radial-gradient(ellipse 100% 90% at 50% 40%, #000 40%, rgba(0,0,0,0.6) 80%, transparent 100%)',
        opacity: gridOpacity,
      }}/>

      {/* CENTERED LOADING BAR */}
      <div style={{
        position: 'absolute',
        left: '50%', top: '50%',
        transform: 'translate(-50%, -50%)',
        // Cap to 480 on desktop, but never exceed the viewport (minus side
        // gutters) so the bar + labels stay on-screen on mobile widths.
        width: 'min(480px, calc(100vw - 48px))',
        opacity: loaderChromeOpacity,
        transition: 'opacity 200ms ease',
      }}>
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
          marginBottom: 12,
          fontFamily: 'var(--font-mono)', fontSize: 10,
          color: 'var(--fg-3)', letterSpacing: '0.18em', textTransform: 'uppercase',
        }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <span style={{
              width: 5, height: 5, borderRadius: '50%',
              background: 'var(--dawn-coral)',
              boxShadow: '0 0 8px var(--dawn-coral)',
              animation: 'apploader-pulse 0.9s ease-in-out infinite',
            }}/>
            {step}
          </span>
          <span style={{ color: 'var(--fg-2)', fontVariantNumeric: 'tabular-nums' }}>
            {Math.floor(barProgress * 100)}%
          </span>
        </div>

        <div style={{
          width: '100%', height: 12,
          background: 'rgba(255,255,255,0.06)',
          border: '1px solid rgba(255,255,255,0.10)',
          borderRadius: 8, overflow: 'hidden',
          position: 'relative',
        }}>
          <div style={{
            position: 'absolute', left: 0, top: 0, bottom: 0,
            width: `${barProgress * 100}%`,
            background: 'var(--dawn-gradient-h)',
            boxShadow: '0 0 18px rgba(234,82,112,0.55), inset 0 1px 0 rgba(255,255,255,0.18)',
          }}/>
        </div>
      </div>
    </div>
  )
}

export default AppLoader
