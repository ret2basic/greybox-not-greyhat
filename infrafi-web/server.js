import fs from 'node:fs'
import http from 'node:http'
import net from 'node:net'
import path from 'node:path'
import nextEnv from '@next/env'
import next from 'next'
import { parse } from 'node:url'
import { WebSocket, WebSocketServer } from 'ws'

const { loadEnvConfig } = nextEnv
const dev = process.env.NODE_ENV !== 'production'

loadEnvConfig(process.cwd(), dev)
loadStandaloneConfig()

const listenHostname = process.env.HOSTNAME || '0.0.0.0'
const nextHostname = dev && listenHostname === '0.0.0.0' ? 'localhost' : listenHostname
const preferredPort = parsePositiveInteger(process.env.PORT, 3000)
const port = dev ? await resolveAvailablePort(preferredPort, listenHostname) : preferredPort

process.env.PORT = String(port)

const app = next({ dev, hostname: nextHostname, port, webpack: dev })
const handle = app.getRequestHandler()
const wss = new WebSocketServer({ noServer: true, perMessageDeflate: false })

const SOLANA_RPC_PATH_PREFIX = '/api/rpc/solana/'
const SOLANA_CLUSTERS = new Set(['mainnet', 'devnet'])
const DEFAULT_SOLANA_DEVNET_RPC_URL = 'https://api.devnet.solana.com'
const WS_ALLOWED_METHODS = new Set([
  'accountSubscribe',
  'accountUnsubscribe',
  'rootSubscribe',
  'rootUnsubscribe',
  'signatureSubscribe',
  'signatureUnsubscribe',
  'slotSubscribe',
  'slotUnsubscribe',
])
const HOP_BY_HOP_HEADERS = new Set([
  'connection',
  'host',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'sec-websocket-accept',
  'sec-websocket-extensions',
  'sec-websocket-key',
  'sec-websocket-protocol',
  'sec-websocket-version',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
])
const MAX_WS_MESSAGE_BYTES = parsePositiveInteger(
  process.env.SOLANA_RPC_PROXY_MAX_WS_MESSAGE_BYTES,
  64 * 1024,
)
const MAX_WS_BATCH_SIZE = parsePositiveInteger(process.env.SOLANA_RPC_PROXY_MAX_WS_BATCH_SIZE, 10)
const MAX_PENDING_WS_MESSAGES = parsePositiveInteger(
  process.env.SOLANA_RPC_PROXY_MAX_PENDING_WS_MESSAGES,
  20,
)
const MAX_WS_CONNECTIONS_PER_IP = parsePositiveInteger(
  process.env.SOLANA_RPC_PROXY_MAX_WS_CONNECTIONS_PER_IP,
  10,
)
const UPSTREAM_TIMEOUT_MS = parsePositiveInteger(process.env.SOLANA_RPC_PROXY_TIMEOUT_MS, 30_000)
const wsConnectionsByIp = new Map()

function parsePositiveInteger(value, fallback) {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : fallback
}

async function resolveAvailablePort(startPort, hostname) {
  let currentPort = startPort

  while (!(await isPortAvailable(currentPort, hostname))) {
    console.warn(`> Port ${currentPort} is already in use, trying ${currentPort + 1}`)
    currentPort += 1
  }

  return currentPort
}

function isPortAvailable(portToCheck, hostname) {
  return new Promise((resolve, reject) => {
    const server = net.createServer()

    server.once('error', (error) => {
      if (error.code === 'EADDRINUSE') {
        resolve(false)
        return
      }

      reject(error)
    })
    server.once('listening', () => {
      server.close(() => resolve(true))
    })
    server.listen(portToCheck, hostname)
  })
}

function loadStandaloneConfig() {
  if (dev || process.env.__NEXT_PRIVATE_STANDALONE_CONFIG) {
    return
  }

  try {
    const manifestPath = path.join(process.cwd(), '.next', 'required-server-files.json')
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'))

    if (manifest?.config) {
      process.env.__NEXT_PRIVATE_STANDALONE_CONFIG = JSON.stringify(manifest.config)
    }
  } catch {
    // The file only exists after `next build`; dev and prebuild scripts can safely continue.
  }
}

function getRequestPathname(req) {
  try {
    return new URL(req.url || '/', 'http://localhost').pathname
  } catch {
    return '/'
  }
}

function getSolanaClusterFromPathname(pathname) {
  if (!pathname.startsWith(SOLANA_RPC_PATH_PREFIX)) {
    return null
  }

  const rest = pathname.slice(SOLANA_RPC_PATH_PREFIX.length)
  const [cluster, extraPath] = rest.split('/')

  if (!SOLANA_CLUSTERS.has(cluster) || extraPath) {
    return null
  }

  return cluster
}

function getAllowedOrigins(req) {
  const host = req.headers.host
  const forwardedProto = req.headers['x-forwarded-proto']
  const socketProtocol = req.socket.encrypted ? 'https' : 'http'
  const protocol = Array.isArray(forwardedProto)
    ? forwardedProto[0]
    : forwardedProto || socketProtocol
  const origins = new Set(host ? [`${protocol}://${host}`] : [])
  const configuredOrigins = process.env.SOLANA_RPC_PROXY_ALLOWED_ORIGINS
  const addOrigin = (origin) => {
    try {
      origins.add(new URL(origin).origin)
    } catch {
      origins.add(origin)
    }
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

function isAllowedOrigin(req) {
  const origin = req.headers.origin

  if (!origin) {
    return dev || process.env.SOLANA_RPC_PROXY_ALLOW_MISSING_ORIGIN === 'true'
  }

  return getAllowedOrigins(req).has(origin)
}

function getClientIp(req) {
  const forwardedFor = req.headers['x-forwarded-for']
  if (typeof forwardedFor === 'string') {
    return forwardedFor.split(',')[0]?.trim() || 'unknown'
  }
  if (Array.isArray(forwardedFor)) {
    return forwardedFor[0]?.split(',')[0]?.trim() || 'unknown'
  }

  return (
    req.headers['cf-connecting-ip'] ||
    req.headers['x-real-ip'] ||
    req.socket.remoteAddress ||
    'unknown'
  )
}

function validateUpstreamUrl(url, label) {
  const parsed = new URL(url)
  if (!['ws:', 'wss:'].includes(parsed.protocol)) {
    throw new Error(`${label} must use ws: or wss:.`)
  }
  if (!dev && parsed.protocol !== 'wss:') {
    throw new Error(`${label} must use wss: in production.`)
  }
  return parsed.toString()
}

function toWsUrl(httpRpcUrl) {
  const parsed = new URL(httpRpcUrl)
  parsed.protocol = parsed.protocol === 'https:' ? 'wss:' : 'ws:'
  return parsed.toString()
}

function getSolanaWsRpcUrl(cluster) {
  const url =
    cluster === 'mainnet'
      ? process.env.SOLANA_WS_RPC_URL ||
        (process.env.SOLANA_RPC_URL ? toWsUrl(process.env.SOLANA_RPC_URL) : undefined)
      : process.env.SOLANA_DEVNET_WS_RPC_URL ||
        toWsUrl(process.env.SOLANA_DEVNET_RPC_URL || DEFAULT_SOLANA_DEVNET_RPC_URL)

  if (!url) {
    throw new Error('Missing SOLANA_RPC_URL or SOLANA_WS_RPC_URL on server.')
  }

  return validateUpstreamUrl(url, `${cluster} Solana WS RPC URL`)
}

function getWsForwardHeaders(req) {
  const headers = {}

  Object.entries(req.headers).forEach(([key, value]) => {
    if (value === undefined || HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
      return
    }
    if (key.toLowerCase() === 'origin') {
      return
    }

    headers[key] = value
  })

  return headers
}

function findDuplicateJsonKey(jsonText) {
  let index = 0
  let duplicateKey = null

  const skipWhitespace = () => {
    while (index < jsonText.length && /\s/.test(jsonText[index] || '')) {
      index += 1
    }
  }

  const parseStringLiteral = () => {
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
          return JSON.parse(jsonText.slice(start, index))
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

  const parseLiteral = (literal) => {
    if (!jsonText.startsWith(literal, index)) {
      return false
    }
    index += literal.length
    return true
  }

  const parseValue = () => {
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

  const parseObject = () => {
    const keys = new Set()
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

  const parseArray = () => {
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

function isAllowedWsRpcMessage(data) {
  if (Buffer.byteLength(data) > MAX_WS_MESSAGE_BYTES) {
    return false
  }

  try {
    const message = data.toString()
    if (findDuplicateJsonKey(message)) {
      return false
    }

    const payload = JSON.parse(message)
    const requests = Array.isArray(payload) ? payload : [payload]
    if (requests.length === 0 || requests.length > MAX_WS_BATCH_SIZE) {
      return false
    }

    return requests.every((request) => {
      return request && typeof request.method === 'string' && WS_ALLOWED_METHODS.has(request.method)
    })
  } catch {
    return false
  }
}

function closeSocket(socket, code, reason) {
  if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
    socket.close(code, reason)
  }
}

function releaseWsConnection(ip) {
  const current = wsConnectionsByIp.get(ip) || 0
  if (current <= 1) {
    wsConnectionsByIp.delete(ip)
    return
  }

  wsConnectionsByIp.set(ip, current - 1)
}

function handleSolanaWsProxy(cluster, req, socket, head) {
  if (!isAllowedOrigin(req)) {
    socket.write('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n')
    socket.destroy()
    return
  }

  const ip = getClientIp(req)
  const activeConnections = wsConnectionsByIp.get(ip) || 0
  if (activeConnections >= MAX_WS_CONNECTIONS_PER_IP) {
    socket.write('HTTP/1.1 429 Too Many Requests\r\nConnection: close\r\n\r\n')
    socket.destroy()
    return
  }

  wsConnectionsByIp.set(ip, activeConnections + 1)

  wss.handleUpgrade(req, socket, head, (clientSocket) => {
    const pendingMessages = []
    let upstreamOpen = false
    let upstreamSocket
    let upstreamCloseExpected = false
    let connectionReleased = false

    const releaseConnectionOnce = () => {
      if (connectionReleased) {
        return
      }

      connectionReleased = true
      releaseWsConnection(ip)
    }
    const closeUpstreamSocket = (code, reason) => {
      upstreamCloseExpected = true
      closeSocket(upstreamSocket, code, reason)
    }

    clientSocket.once('close', releaseConnectionOnce)
    clientSocket.once('error', releaseConnectionOnce)

    try {
      upstreamSocket = new WebSocket(getSolanaWsRpcUrl(cluster), undefined, {
        headers: getWsForwardHeaders(req),
        handshakeTimeout: UPSTREAM_TIMEOUT_MS,
        perMessageDeflate: false,
      })
    } catch (error) {
      console.error('[solana-rpc-ws-proxy] invalid upstream', error)
      closeSocket(clientSocket, 1011, 'Invalid Solana RPC upstream socket')
      return
    }

    clientSocket.on('message', (data, isBinary) => {
      if (isBinary || !isAllowedWsRpcMessage(data)) {
        closeSocket(clientSocket, 1008, 'Solana WS RPC method is not allowed')
        closeUpstreamSocket(1000, 'Client message rejected')
        return
      }

      if (!upstreamOpen) {
        if (pendingMessages.length >= MAX_PENDING_WS_MESSAGES) {
          closeSocket(clientSocket, 1013, 'Solana RPC upstream socket is not ready')
          return
        }

        pendingMessages.push(data)
        return
      }

      upstreamSocket.send(data)
    })

    clientSocket.on('close', () => {
      closeUpstreamSocket(1000, 'Client socket closed')
    })
    clientSocket.on('error', () => {
      closeUpstreamSocket(1011, 'Client socket error')
    })

    upstreamSocket.on('open', () => {
      upstreamOpen = true
      pendingMessages.splice(0).forEach((data) => {
        if (upstreamSocket.readyState === WebSocket.OPEN) {
          upstreamSocket.send(data)
        }
      })
    })
    upstreamSocket.on('message', (data, isBinary) => {
      if (clientSocket.readyState === WebSocket.OPEN) {
        clientSocket.send(data, { binary: isBinary })
      }
    })
    upstreamSocket.on('close', (code, reason) => {
      if (!upstreamCloseExpected && code !== 1000) {
        console.warn('[solana-rpc-ws-proxy] upstream socket closed unexpectedly', {
          code,
          reason: reason.toString(),
        })
      }
      closeSocket(clientSocket, 1000, 'Upstream Solana RPC socket closed')
    })
    upstreamSocket.on('error', (error) => {
      if (!upstreamCloseExpected) {
        console.error('[solana-rpc-ws-proxy] upstream socket error', error)
      }
      closeSocket(clientSocket, 1011, 'Upstream Solana RPC socket error')
    })
  })
}

app.prepare().then(() => {
  const handleUpgrade = app.getUpgradeHandler()
  const server = http.createServer(async (req, res) => {
    const parsedUrl = parse(req.url || '', true)
    await handle(req, res, parsedUrl)
  })

  server.on('upgrade', (req, socket, head) => {
    const cluster = getSolanaClusterFromPathname(getRequestPathname(req))

    if (cluster) {
      handleSolanaWsProxy(cluster, req, socket, head)
      return
    }

    handleUpgrade(req, socket, head).catch((error) => {
      console.error('[next-upgrade] failed to handle websocket upgrade', error)
      socket.destroy()
    })
  })

  server.listen(port, listenHostname, () => {
    console.log(`> Ready on http://${nextHostname}:${port}`)
    if (listenHostname !== nextHostname) {
      console.log(`> Listening on http://${listenHostname}:${port}`)
    }
  })
})
