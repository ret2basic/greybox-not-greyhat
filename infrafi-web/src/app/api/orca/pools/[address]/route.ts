import { NextResponse, type NextRequest } from 'next/server'

type RouteContext = {
  params: Promise<{ address: string }>
}

// Same-origin proxy for Orca's public pool endpoint. The browser can't call
// api.orca.so directly (no CORS headers), so the client hits this route and we
// fetch server-side. Docs: https://docs.orca.so/api-reference/whirlpools
export async function GET(_req: NextRequest, context: RouteContext) {
  const { address } = await context.params

  // Guard against open-proxy abuse: only base58 Solana-style addresses.
  if (!/^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(address)) {
    return NextResponse.json({ error: 'invalid address' }, { status: 400 })
  }

  try {
    const upstream = await fetch(`https://api.orca.so/v2/solana/pools/${address}`, {
      headers: { accept: 'application/json' },
      next: { revalidate: 60 },
    })
    if (!upstream.ok) {
      return NextResponse.json({ error: 'upstream error' }, { status: upstream.status })
    }
    return NextResponse.json(await upstream.json())
  } catch {
    return NextResponse.json({ error: 'fetch failed' }, { status: 502 })
  }
}
