import { NextRequest, NextResponse } from 'next/server'
import { PublicKey } from '@solana/web3.js'
import { getM0OrchestrationApiKey } from '@/lib/serverEnv'

const M0_QUOTE_API = 'https://gateway.m0.xyz/v1/orchestration/quote'
const SOLANA_CHAIN = 'Solana'
const USDC_MINT = 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v'
const USDTEL_MINT = 'dawn7ZUF7h7anFuEsDdAU1Y3HYwikwqNMAENZsQJdNL'
const ALLOWED_MINTS = new Set([USDC_MINT, USDTEL_MINT])
const MAX_AMOUNT_IN_DIGITS = 30
const QUOTE_TOP_LEVEL_KEYS = new Set(['route', 'amountIn', 'sender', 'recipient', 'maxNumQuotes'])
const ROUTE_KEYS = new Set(['source', 'destination'])
const ROUTE_ENDPOINT_KEYS = new Set(['chain', 'address'])

interface QuoteRequestBody {
  route: {
    source: { chain: string; address: string }
    destination: { chain: string; address: string }
  }
  amountIn: string
  sender: string
  recipient: string
  maxNumQuotes: 1
}

type JsonRecord = Record<string, unknown>

type ValidationResult = { ok: true; body: QuoteRequestBody } | { ok: false; issues: string[] }

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function unexpectedKeys(record: JsonRecord, allowed: Set<string>): string[] {
  return Object.keys(record).filter((key) => !allowed.has(key))
}

function parsePublicKey(value: string): string | null {
  try {
    return new PublicKey(value).toBase58()
  } catch {
    return null
  }
}

function validateRouteEndpoint(
  value: unknown,
  label: 'source' | 'destination',
  issues: string[],
): { chain: string; address: string } | null {
  if (!isRecord(value)) {
    issues.push(`route.${label} must be an object`)
    return null
  }

  const extraKeys = unexpectedKeys(value, ROUTE_ENDPOINT_KEYS)
  if (extraKeys.length > 0) {
    issues.push(`route.${label} contains unsupported field(s): ${extraKeys.join(', ')}`)
  }

  const chain = value['chain']
  const address = value['address']
  if (chain !== SOLANA_CHAIN) {
    issues.push(`route.${label}.chain must be ${SOLANA_CHAIN}`)
  }
  if (typeof address !== 'string') {
    issues.push(`route.${label}.address must be a string`)
    return null
  }

  const normalizedAddress = parsePublicKey(address)
  if (!normalizedAddress) {
    issues.push(`route.${label}.address must be a valid Solana public key`)
    return null
  }
  if (!ALLOWED_MINTS.has(normalizedAddress)) {
    issues.push(`route.${label}.address is not an allowed mint`)
    return null
  }

  return { chain: SOLANA_CHAIN, address: normalizedAddress }
}

function validateQuoteRequestBody(value: unknown): ValidationResult {
  const issues: string[] = []

  if (!isRecord(value)) {
    return { ok: false, issues: ['request body must be a JSON object'] }
  }

  const extraKeys = unexpectedKeys(value, QUOTE_TOP_LEVEL_KEYS)
  if (extraKeys.length > 0) {
    issues.push(`request body contains unsupported field(s): ${extraKeys.join(', ')}`)
  }

  const route = value['route']
  if (!isRecord(route)) {
    issues.push('route must be an object')
  }

  const routeExtraKeys = isRecord(route) ? unexpectedKeys(route, ROUTE_KEYS) : []
  if (routeExtraKeys.length > 0) {
    issues.push(`route contains unsupported field(s): ${routeExtraKeys.join(', ')}`)
  }

  const source = validateRouteEndpoint(
    isRecord(route) ? route['source'] : undefined,
    'source',
    issues,
  )
  const destination = validateRouteEndpoint(
    isRecord(route) ? route['destination'] : undefined,
    'destination',
    issues,
  )

  if (source && destination) {
    if (source.address === destination.address) {
      issues.push('route source and destination mints must be different')
    }
    if (
      !(
        (source.address === USDC_MINT && destination.address === USDTEL_MINT) ||
        (source.address === USDTEL_MINT && destination.address === USDC_MINT)
      )
    ) {
      issues.push('route must swap between USDC and USD.tel')
    }
  }

  const amountIn = value['amountIn']
  if (typeof amountIn !== 'string') {
    issues.push('amountIn must be a string')
  } else if (!/^[1-9]\d*$/.test(amountIn)) {
    issues.push('amountIn must be a positive integer string')
  } else if (amountIn.length > MAX_AMOUNT_IN_DIGITS) {
    issues.push(`amountIn must be at most ${MAX_AMOUNT_IN_DIGITS} digits`)
  }

  const sender = value['sender']
  let normalizedSender: string | null = null
  if (typeof sender !== 'string') {
    issues.push('sender must be a string')
  } else {
    normalizedSender = parsePublicKey(sender)
    if (!normalizedSender) {
      issues.push('sender must be a valid Solana public key')
    }
  }

  const recipient = value['recipient']
  let normalizedRecipient: string | null = null
  if (typeof recipient !== 'string') {
    issues.push('recipient must be a string')
  } else {
    normalizedRecipient = parsePublicKey(recipient)
    if (!normalizedRecipient) {
      issues.push('recipient must be a valid Solana public key')
    }
  }

  if (normalizedSender && normalizedRecipient && normalizedSender !== normalizedRecipient) {
    issues.push('recipient must match sender')
  }

  const maxNumQuotes = value['maxNumQuotes']
  const normalizedMaxNumQuotes = maxNumQuotes === 1 ? 1 : null
  if (normalizedMaxNumQuotes !== 1) {
    issues.push('maxNumQuotes must be 1')
  }

  if (
    issues.length > 0 ||
    !source ||
    !destination ||
    typeof amountIn !== 'string' ||
    !normalizedSender ||
    !normalizedRecipient ||
    normalizedMaxNumQuotes !== 1
  ) {
    return { ok: false, issues }
  }

  return {
    ok: true,
    body: {
      route: { source, destination },
      amountIn,
      sender: normalizedSender,
      recipient: normalizedRecipient,
      maxNumQuotes: normalizedMaxNumQuotes,
    },
  }
}

export async function POST(req: NextRequest) {
  const contentType = req.headers.get('content-type')?.toLowerCase() ?? ''
  if (!contentType.includes('application/json')) {
    return NextResponse.json({ error: 'Unsupported content type' }, { status: 415 })
  }

  let rawBody: unknown
  try {
    rawBody = await req.json()
  } catch {
    return NextResponse.json({ error: 'Malformed JSON request body' }, { status: 400 })
  }

  const validation = validateQuoteRequestBody(rawBody)
  if (!validation.ok) {
    return NextResponse.json(
      { error: 'Invalid quote request body', issues: validation.issues },
      { status: 400 },
    )
  }

  const m0ApiKey = getM0OrchestrationApiKey()
  if (!m0ApiKey) {
    return NextResponse.json({ error: 'Quote service is not configured' }, { status: 500 })
  }

  try {
    const res = await fetch(M0_QUOTE_API, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': m0ApiKey,
      },
      body: JSON.stringify(validation.body),
    })

    if (!res.ok) {
      return NextResponse.json({ error: 'M0 orchestration quote failed' }, { status: res.status })
    }

    const data = await res.json()
    if (!Array.isArray(data)) {
      return NextResponse.json(
        { error: 'Invalid response shape from M0 orchestration quote API' },
        { status: 502 },
      )
    }

    return NextResponse.json(data, { status: 200 })
  } catch (err) {
    console.error('[api/quote] orchestration proxy error', err)
    return NextResponse.json({ error: 'Quote request failed' }, { status: 500 })
  }
}
