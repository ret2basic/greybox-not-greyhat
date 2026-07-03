import type { Metadata, Viewport } from 'next'
import { Inter, Inter_Tight, JetBrains_Mono, Instrument_Serif } from 'next/font/google'
import './globals.css'
import { TopNav } from '@/components/TopNav'
import { FooterTicker } from '@/components/FooterTicker'
import Providers from '@/components/Providers'

const inter = Inter({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  display: 'swap',
  variable: '--font-sans',
})

const interTight = Inter_Tight({
  subsets: ['latin'],
  weight: ['500', '600', '700'],
  display: 'swap',
  variable: '--font-display',
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  display: 'swap',
  variable: '--font-mono',
})

const instrumentSerif = Instrument_Serif({
  subsets: ['latin'],
  weight: ['400'],
  style: ['normal', 'italic'],
  display: 'swap',
  variable: '--font-serif',
})

export const metadata: Metadata = {
  title: "DAWN InfraFi - Funding Tomorrow's Internet",
  description:
    'Invest crypto into billbound and deployment through the DAWN network. Secure, transparent, and accessible retail investment platform.',
  icons: {
    icon: '/favicon.ico',
  },
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
}

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    // suppressHydrationWarning silences React's hydration mismatch
    // warning on the <html> element. Two attributes legitimately
    // differ between server-rendered HTML and the post-hydration
    // DOM, neither of which is a code bug:
    //   1. `data-loader="active"` — set by the inline <script> in
    //      <head> below, BEFORE React hydrates, to render the
    //      pre-paint cover. By design.
    //   2. Browser-extension attributes (data-peer-injected,
    //      cz-shortcut-listen, etc.) injected before React loads.
    //      Outside our control.
    // The warning only applies to <html>'s direct attributes; React
    // still warns on real mismatches deeper in the tree.
    <html lang='en' className='dark' suppressHydrationWarning>
      <head>
        {/* Pre-paint cover (per Claude Design's SSR recipe).
            Runs synchronously during HTML parse, BEFORE the body
            renders. If the user is on a loader-eligible route AND
            sessionStorage says the loader hasn't played this session,
            sets `data-loader="active"` on <html>. The CSS rule in
            globals.css then paints a dark ::before backdrop over the
            ENTIRE viewport — covering the layout shell (TopNav,
            FooterTicker, ambient gradient) that gets SSR'd.
            This eliminates the brief flash of the layout shell that
            otherwise shows between HTML paint and React hydration.
            AppLoaderInner removes the attribute on completion (the
            played path); AppLoader's outer gate removes it via
            useEffect for repeat visitors (the skipped path). */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              "try{var p=location.pathname;if((p==='/'||p==='/buy-stake')&&sessionStorage.getItem('infrafi_loader_played')!=='1'){document.documentElement.setAttribute('data-loader','active')}}catch(e){}",
          }}
        />
      </head>
      <body
        className={`${inter.variable} ${interTight.variable} ${jetbrainsMono.variable} ${instrumentSerif.variable} home theme-midnight antialiased min-h-screen`}
      >
        <Providers>
          <div className='app-shell relative min-h-screen' style={{ isolation: 'isolate' }}>
            {/* Page background — 1:1 with Figma: grid + ellipse glows behind all content. */}
            <div aria-hidden className='app-bg'>
              <svg className='app-bg-grid' shapeRendering='crispEdges'>
                <defs>
                  <pattern
                    id='app-bg-grid-pattern'
                    width={56}
                    height={56}
                    patternUnits='userSpaceOnUse'
                  >
                    <rect x={0} y={0} width={56} height={1} fill='rgba(255,255,255,0.04)' />
                    <rect x={0} y={0} width={1} height={56} fill='rgba(255,255,255,0.04)' />
                  </pattern>
                </defs>
                <rect width='100%' height='100%' fill='url(#app-bg-grid-pattern)' />
              </svg>
              <div className='app-bg-glows' />
            </div>
            <TopNav />
            {children}
            <FooterTicker />
          </div>
        </Providers>
      </body>
    </html>
  )
}
