import { NextRequest, NextResponse } from 'next/server'

const RPC_ENDPOINTS = {
  mainnet: 'SOLANA_RPC_URL',
  devnet: 'SOLANA_DEVNET_RPC_URL',
} as const

const DEFAULT_DEVNET_RPC_URL = 'https://api.devnet.solana.com'
const DEFAULT_ALLOWED_METHODS = new Set([
  'getAccountInfo',
  'getBalance',
  'getEpochInfo',
  'getFeeForMessage',
  'getHealth',
  'getLatestBlockhash',
  'getMinimumBalanceForRentExemption',
  'getMultipleAccounts',
  'getParsedAccountInfo',
  'getParsedTokenAccountsByOwner',
  'getRecentPrioritizationFees',
  'getSignatureStatuses',
  'getSlot',
  'getTokenAccountBalance',
  'getTokenAccountsByOwner',
  'getTokenSupply',
  'getTransaction',
  'getVersion',
  'isBlockhashValid',
])
const TRANSACTION_METHODS = new Set([
  'sendTransaction',
  'simulateTransaction',
])
const BLOCKED_METHODS = new Set(['getProgramAccounts', 'getSignaturesForAddress'])
const MAX_BODY_BYTES = parsePositiveInteger(process.env.SOLANA_RPC_PROXY_MAX_BODY_BYTES, 512 * 1024)
const MAX_BATCH_SIZE = parsePositiveInteger(process.env.SOLANA_RPC_PROXY_MAX_BATCH_SIZE, 10)
const UPSTREAM_TIMEOUT_MS = parsePositiveInteger(process.env.SOLANA_RPC_PROXY_TIMEOUT_MS, 30_000)
const BURST_LIMIT = parsePositiveInteger(process.env.SOLANA_RPC_PROXY_BURST_LIMIT, 30)
const BURST_WINDOW_SECONDS = parsePositiveInteger(
  process.env.SOLANA_RPC_PROXY_BURST_WINDOW_SECONDS,
  10,
)
const SUSTAINED_LIMIT = parsePositiveInteger(process.env.SOLANA_RPC_PROXY_SUSTAINED_LIMIT, 600)
const SUSTAINED_WINDOW_SECONDS = parsePositiveInteger(
  process.env.SOLANA_RPC_PROXY_SUSTAINED_WINDOW_SECONDS,
  60,
)
const ALLOW_MISSING_ORIGIN = process.env.SOLANA_RPC_PROXY_ALLOW_MISSING_ORIGIN === 'true'
const ALLOW_TRANSACTION_METHODS = process.env.SOLANA_RPC_PROXY_ALLOW_TRANSACTION_METHODS === 'true'
const IS_PRODUCTION = process.env.NODE_ENV === 'production'

type Cluster = keyof typeof RPC_ENDPOINTS
type RpcRequest = {
  jsonrpc?: unknown
  method?: unknown
  params?: unknown
  id?: unknown
}
type RateLimitResult = {
  allowed: boolean
  retryAfterSeconds?: number
}
type RateLimitCounter = {
  count: number
  ttl: number
}
type RateLimitWindowName = 'burst' | 'sustained'
type RateLimitWindow = {
  name: RateLimitWindowName
  limit: number
  windowSeconds: number
}

const memoryRateLimits = new Map<string, { count: number; resetAt: number }>()
const RATE_LIMIT_FALLBACK_LOG_INTERVAL_MS = 30_000
const RATE_LIMIT_WINDOWS = [
  { name: 'burst', limit: BURST_LIMIT, windowSeconds: BURST_WINDOW_SECONDS },
  { name: 'sustained', limit: SUSTAINED_LIMIT, windowSeconds: SUSTAINED_WINDOW_SECONDS },
] satisfies RateLimitWindow[]
let lastRateLimitFallbackLogAt = 0

function parsePositiveInteger(value: string | undefined, fallback: number) {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : fallback
}

function json(status: number, body: unknown, headers: Record<string, string> = {}) {
  return NextResponse.json(body, {
    status,
    headers: {
      'cache-control': 'no-store',
      ...headers,
    },
  })
}

function getAllowedOrigins(req: NextRequest) {
  const origins = new Set<string>([req.nextUrl.origin])
  const configuredOrigins = process.env.SOLANA_RPC_PROXY_ALLOWED_ORIGINS
  const host = req.headers.get('host')
  const forwardedProto =
    req.headers.get('x-forwarded-proto') ?? req.nextUrl.protocol.replace(':', '')
  const addOrigin = (origin: string) => {
    try {
      origins.add(new URL(origin).origin)
    } catch {
      origins.add(origin)
    }
  }

  if (host) {
    addOrigin(`${forwardedProto}://${host}`)
  }

  if (process.env.NEXT_PUBLIC_APP_URL) {
    addOrigin(process.env.NEXT_PUBLIC_APP_URL)
  }
  if (process.env.VERCEL_URL) {
    addOrigin(`https://${process.env.VERCEL_URL}`)
  }
  if (configuredOrigins) {
    configuredOrigins
      .split(',')
      .map((origin) => origin.trim())
      .filter(Boolean)
      .forEach(addOrigin)
  }

  return origins
}

function getCorsHeaders(req: NextRequest): Record<string, string> {
  const origin = req.headers.get('origin')
  const allowedOrigins = getAllowedOrigins(req)

  if (origin && allowedOrigins.has(origin)) {
    return {
      'access-control-allow-origin': origin,
      vary: 'Origin',
    }
  }

  return {}
}

function isAllowedRequestSource(req: NextRequest) {
  const origin = req.headers.get('origin')
  const referer = req.headers.get('referer')
  const allowedOrigins = getAllowedOrigins(req)

  if (!origin && !referer) {
    return !IS_PRODUCTION || ALLOW_MISSING_ORIGIN
  }
  if (origin) {
    return allowedOrigins.has(origin)
  }
  if (referer) {
    try {
      return allowedOrigins.has(new URL(referer).origin)
    } catch {
      return false
    }
  }

  return false
}

function getClientIp(req: NextRequest) {
  const forwardedFor = req.headers.get('x-forwarded-for')
  if (forwardedFor) {
    return forwardedFor.split(',')[0]?.trim() || 'unknown'
  }

  return req.headers.get('cf-connecting-ip') ?? req.headers.get('x-real-ip') ?? 'unknown'
}

function getUpstashConfig() {
  const url = process.env.UPSTASH_REDIS_REST_URL ?? process.env.KV_REST_API_URL
  const token = process.env.UPSTASH_REDIS_REST_TOKEN ?? process.env.KV_REST_API_TOKEN

  if (!url || !token) {
    return null
  }

  return { url: url.replace(/\/$/, ''), token }
}

async function incrementWithUpstash(
  key: string,
  windowSeconds: number,
): Promise<RateLimitCounter | null> {
  const config = getUpstashConfig()
  if (!config) {
    return null
  }

  const response = await fetch(`${config.url}/pipeline`, {
    method: 'POST',
    headers: {
      authorization: `Bearer ${config.token}`,
      'content-type': 'application/json',
    },
    body: JSON.stringify([
      ['INCR', key],
      ['EXPIRE', key, String(windowSeconds)],
      ['TTL', key],
    ]),
    cache: 'no-store',
  })

  if (!response.ok) {
    throw new Error(`Rate limit store failed with ${response.status}`)
  }

  const data = (await response.json()) as Array<{ result?: number }>
  return {
    count: Number(data[0]?.result ?? 0),
    ttl: Number(data[2]?.result ?? windowSeconds),
  }
}

function incrementWithMemory(key: string, windowSeconds: number): RateLimitCounter {
  const now = Date.now()
  const existing = memoryRateLimits.get(key)

  if (!existing || existing.resetAt <= now) {
    const resetAt = now + windowSeconds * 1000
    memoryRateLimits.set(key, { count: 1, resetAt })
    return { count: 1, ttl: windowSeconds }
  }

  existing.count += 1
  return { count: existing.count, ttl: Math.max(1, Math.ceil((existing.resetAt - now) / 1000)) }
}

function getRateLimitKey(cluster: Cluster, windowName: RateLimitWindowName, ip: string) {
  return `solana-rpc:${cluster}:${windowName}:${ip}`
}

function evaluateRateLimitCounter(
  counter: RateLimitCounter,
  limit: number,
): RateLimitResult | null {
  if (counter.count <= limit) {
    return null
  }

  return { allowed: false, retryAfterSeconds: counter.ttl }
}

function logRateLimitStoreFallback(error: unknown) {
  const now = Date.now()
  if (now - lastRateLimitFallbackLogAt < RATE_LIMIT_FALLBACK_LOG_INTERVAL_MS) {
    return
  }

  lastRateLimitFallbackLogAt = now
  console.warn('[api/rpc] rate limit store failed, falling back to memory', error)
}

async function incrementRateLimitCounter(
  key: string,
  windowSeconds: number,
): Promise<RateLimitCounter> {
  try {
    return (
      (await incrementWithUpstash(key, windowSeconds)) ?? incrementWithMemory(key, windowSeconds)
    )
  } catch (error) {
    logRateLimitStoreFallback(error)
    return incrementWithMemory(key, windowSeconds)
  }
}

async function checkRateLimitWindow(
  cluster: Cluster,
  ip: string,
  window: RateLimitWindow,
): Promise<RateLimitResult | null> {
  const key = getRateLimitKey(cluster, window.name, ip)
  const counter = await incrementRateLimitCounter(key, window.windowSeconds)
  return evaluateRateLimitCounter(counter, window.limit)
}

async function checkRateLimit(req: NextRequest, cluster: Cluster): Promise<RateLimitResult> {
  // In local development every request comes from the dev's own machine without
  // x-forwarded-for / cf-connecting-ip / x-real-ip headers, so every browser
  // tab shares the same "unknown" IP bucket and blows through the burst limit
  // during normal page loads (AppKit + hooks easily exceed 30 req / 10s).
  if (!IS_PRODUCTION) {
    return { allowed: true }
  }

  const ip = getClientIp(req)

  for (const rateLimitWindow of RATE_LIMIT_WINDOWS) {
    const result = await checkRateLimitWindow(cluster, ip, rateLimitWindow)
    if (result) {
      return result
    }
  }

  return { allowed: true }
}

function getAllowedMethods() {
  const configuredMethods = process.env.SOLANA_RPC_PROXY_ALLOWED_METHODS
  if (!configuredMethods) {
    const methods = new Set(DEFAULT_ALLOWED_METHODS)
    if (ALLOW_TRANSACTION_METHODS) {
      TRANSACTION_METHODS.forEach((method) => methods.add(method))
    }
    return methods
  }

  return new Set(
    configuredMethods
      .split(',')
      .map((method) => method.trim())
      .filter(Boolean),
  )
}

function findDuplicateJsonKey(jsonText: string): string | null {
  let index = 0
  let duplicateKey: string | null = null

  const skipWhitespace = () => {
    while (index < jsonText.length && /\s/.test(jsonText[index] ?? '')) {
      index += 1
    }
  }

  const parseStringLiteral = (): string | null => {
    if (jsonText[index] !== '"') {
      return null
    }

    const start = index
    index += 1

    while (index < jsonText.length) {
      const char = jsonText[index]
      if (char === '\\') {
        index += 2
        continue
      }
      if (char === '"') {
        index += 1
        try {
          return JSON.parse(jsonText.slice(start, index)) as string
        } catch {
          return null
        }
      }
      if (char && char < ' ') {
        return null
      }
      index += 1
    }

    return null
  }

  const parseNumber = () => {
    const match = /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/.exec(jsonText.slice(index))
    if (!match) {
      return false
    }
    index += match[0].length
    return true
  }

  const parseLiteral = (literal: string) => {
    if (!jsonText.startsWith(literal, index)) {
      return false
    }
    index += literal.length
    return true
  }

  const parseValue = (): boolean => {
    skipWhitespace()
    const char = jsonText[index]

    if (char === '{') {
      return parseObject()
    }
    if (char === '[') {
      return parseArray()
    }
    if (char === '"') {
      return parseStringLiteral() !== null
    }
    if (char === '-' || (char !== undefined && char >= '0' && char <= '9')) {
      return parseNumber()
    }

    return parseLiteral('true') || parseLiteral('false') || parseLiteral('null')
  }

  const parseObject = (): boolean => {
    const keys = new Set<string>()
    index += 1
    skipWhitespace()

    if (jsonText[index] === '}') {
      index += 1
      return true
    }

    while (index < jsonText.length) {
      skipWhitespace()
      const key = parseStringLiteral()
      if (key === null) {
        return false
      }
      if (keys.has(key)) {
        duplicateKey = key
        return false
      }
      keys.add(key)

      skipWhitespace()
      if (jsonText[index] !== ':') {
        return false
      }
      index += 1

      if (!parseValue()) {
        return false
      }

      skipWhitespace()
      if (jsonText[index] === ',') {
        index += 1
        continue
      }
      if (jsonText[index] === '}') {
        index += 1
        return true
      }
      return false
    }

    return false
  }

  const parseArray = (): boolean => {
    index += 1
    skipWhitespace()

    if (jsonText[index] === ']') {
      index += 1
      return true
    }

    while (index < jsonText.length) {
      if (!parseValue()) {
        return false
      }

      skipWhitespace()
      if (jsonText[index] === ',') {
        index += 1
        continue
      }
      if (jsonText[index] === ']') {
        index += 1
        return true
      }
      return false
    }

    return false
  }

  parseValue()
  return duplicateKey
}

function validateRpcPayload(payload: unknown): RpcRequest[] {
  const requests = Array.isArray(payload) ? payload : [payload]

  if (requests.length === 0) {
    throw new ResponseError(400, 'JSON-RPC batch cannot be empty.')
  }
  if (requests.length > MAX_BATCH_SIZE) {
    throw new ResponseError(413, `JSON-RPC batch size exceeds ${MAX_BATCH_SIZE}.`)
  }

  const allowedMethods = getAllowedMethods()

  requests.forEach((request) => {
    if (!request || typeof request !== 'object') {
      throw new ResponseError(400, 'Invalid JSON-RPC request.')
    }

    const method = (request as RpcRequest).method
    if (typeof method !== 'string') {
      throw new ResponseError(400, 'JSON-RPC method must be a string.')
    }
    if (BLOCKED_METHODS.has(method) || !allowedMethods.has(method)) {
      throw new ResponseError(403, `JSON-RPC method is not allowed: ${method}`)
    }
  })

  return requests as RpcRequest[]
}

function getRpcUrl(cluster: Cluster) {
  const envName = RPC_ENDPOINTS[cluster]
  const url = process.env[envName] ?? (cluster === 'devnet' ? DEFAULT_DEVNET_RPC_URL : undefined)

  if (!url) {
    throw new ResponseError(500, `Missing ${envName} on server.`)
  }

  try {
    const parsed = new URL(url)
    if (!['https:', 'http:'].includes(parsed.protocol)) {
      throw new Error(`${envName} must use http: or https:.`)
    }
    if (IS_PRODUCTION && parsed.protocol !== 'https:') {
      throw new Error(`${envName} must use https: in production.`)
    }
    return parsed.toString()
  } catch (error) {
    throw new ResponseError(500, error instanceof Error ? error.message : `Invalid ${envName}.`)
  }
}

class ResponseError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
  }
}

export async function handleSolanaRpc(req: NextRequest, cluster: string) {
  const corsHeaders = getCorsHeaders(req)

  if (cluster !== 'mainnet' && cluster !== 'devnet') {
    return json(404, { error: 'Unknown Solana RPC cluster.' }, corsHeaders)
  }

  if (req.method === 'OPTIONS') {
    if (!isAllowedRequestSource(req)) {
      return json(403, { error: 'Request origin is not allowed.' })
    }

    return new NextResponse(null, {
      status: 204,
      headers: {
        allow: 'POST, OPTIONS',
        'access-control-allow-methods': 'POST, OPTIONS',
        'access-control-allow-headers':
          req.headers.get('access-control-request-headers') ?? 'content-type',
        'access-control-max-age': '86400',
        'cache-control': 'no-store',
        ...corsHeaders,
      },
    })
  }

  if (req.method !== 'POST') {
    return json(
      405,
      { error: 'Use POST JSON-RPC requests for the Solana RPC proxy.' },
      {
        allow: 'POST, OPTIONS',
        ...corsHeaders,
      },
    )
  }
  if (!isAllowedRequestSource(req)) {
    return json(403, { error: 'Request origin is not allowed.' }, corsHeaders)
  }

  const contentType = req.headers.get('content-type')?.toLowerCase() ?? ''
  if (!contentType.includes('application/json')) {
    return json(415, { error: 'Unsupported content type.' }, corsHeaders)
  }

  const contentLength = Number(req.headers.get('content-length') ?? 0)
  if (Number.isFinite(contentLength) && contentLength > MAX_BODY_BYTES) {
    return json(413, { error: 'Solana RPC request body is too large.' }, corsHeaders)
  }

  const rateLimit = await checkRateLimit(req, cluster)
  if (!rateLimit.allowed) {
    return json(
      429,
      { error: 'Too many Solana RPC requests.' },
      {
        'retry-after': String(rateLimit.retryAfterSeconds ?? 30),
        ...corsHeaders,
      },
    )
  }

  try {
    const rawBody = await req.text()
    if (new TextEncoder().encode(rawBody).byteLength > MAX_BODY_BYTES) {
      return json(413, { error: 'Solana RPC request body is too large.' }, corsHeaders)
    }

    const duplicateJsonKey = findDuplicateJsonKey(rawBody)
    if (duplicateJsonKey) {
      return json(
        400,
        { error: `Duplicate JSON key is not allowed: ${duplicateJsonKey}` },
        corsHeaders,
      )
    }

    const payload = JSON.parse(rawBody) as unknown
    validateRpcPayload(payload)

    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), UPSTREAM_TIMEOUT_MS)

    try {
      const upstreamResponse = await fetch(getRpcUrl(cluster), {
        method: 'POST',
        headers: {
          accept: 'application/json',
          'content-type': 'application/json',
        },
        body: rawBody,
        cache: 'no-store',
        signal: controller.signal,
      })
      const body = await upstreamResponse.text()

      return new NextResponse(body, {
        status: upstreamResponse.status,
        headers: {
          'content-type': upstreamResponse.headers.get('content-type') ?? 'application/json',
          'cache-control': 'no-store',
          ...corsHeaders,
        },
      })
    } finally {
      clearTimeout(timeout)
    }
  } catch (error) {
    if (error instanceof SyntaxError) {
      return json(400, { error: 'Invalid JSON body.' }, corsHeaders)
    }
    if (error instanceof ResponseError) {
      return json(error.status, { error: error.message }, corsHeaders)
    }

    console.error('[api/rpc] Solana RPC proxy error', error)
    return json(502, { error: 'Failed to proxy Solana RPC request.' }, corsHeaders)
  }
}
