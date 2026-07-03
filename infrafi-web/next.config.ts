import type { NextConfig } from 'next'

// In local dev we can't call the deployed infrafi-api directly from the browser
// because its CORS layer (infrafi-api/src/router.rs) only allows the configured
// APP_URL/MANAGER_URL origins. Route the calls through Next.js server-side so the
// browser only ever talks to its own origin.
const INFRAFI_API_PROXY_TARGET = process.env.INFRAFI_API_PROXY_TARGET ?? 'https://api.usd.tel'

const nextConfig: NextConfig = {
  output: 'standalone',
  outputFileTracingRoot: process.cwd(),
  transpilePackages: ['glow-vaults-sdk'],
  images: {
    formats: ['image/avif', 'image/webp'],
  },
  async rewrites() {
    return [
      {
        source: '/api/infrafi/:path*',
        destination: `${INFRAFI_API_PROXY_TARGET}/:path*`,
      },
    ]
  },
  // Used by production builds (next build)
  webpack: (config) => {
    config.externals.push('pino-pretty', 'lokijs', 'encoding')
    return config
  },
  // Turbopack is the default dev server in Next.js 16+
  turbopack: {},
}

export default nextConfig
