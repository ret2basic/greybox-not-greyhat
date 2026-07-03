import { VersionedTransaction } from '@solana/web3.js'
import { USDC_MINT, USDTEL_MINT } from '@/lib/solana'

export function deserializeTransaction(base64: string): VersionedTransaction {
  const txBytes = Buffer.from(base64, 'base64')
  return VersionedTransaction.deserialize(txBytes)
}

export type SwapDirection = 'buy' | 'sell'

export interface M0Quote {
  amountIn: string
  amountOut: string
  /** Raw base64-encoded transactions from orchestration payloads, executed in order */
  transactionBase64s: string[]
}

const M0_API = '/api/quote'

const DECIMALS: Record<SwapDirection, number> = {
  buy: 6,   // USDC has 6 decimals
  sell: 6,  // USDtel has 6 decimals
}

export function toRawAmount(humanAmount: string, direction: SwapDirection): string {
  const parsed = parseFloat(humanAmount)
  if (isNaN(parsed) || parsed <= 0) return '0'
  return Math.floor(parsed * 10 ** DECIMALS[direction]).toString()
}

export function fromRawAmount(rawAmount: string, direction: SwapDirection): string {
  const n = Number(rawAmount) / 10 ** DECIMALS[direction]
  return n.toFixed(6)
}

export async function fetchQuote(
  amountIn: string,
  direction: SwapDirection,
  walletAddress: string,
): Promise<M0Quote> {
  const source = direction === 'buy' ? USDC_MINT.toBase58() : USDTEL_MINT.toBase58()
  const destination = direction === 'buy' ? USDTEL_MINT.toBase58() : USDC_MINT.toBase58()

  const body = {
    route: {
      source: { chain: 'Solana', address: source },
      destination: { chain: 'Solana', address: destination },
    },
    amountIn,
    sender: walletAddress,
    recipient: walletAddress,
    maxNumQuotes: 1,
  }

  const res = await fetch(M0_API, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '(could not read body)')
    throw new Error(`M0 quote API error: ${res.status} ${res.statusText} — ${text}`)
  }

  const quotes = await res.json()

  if (!Array.isArray(quotes) || quotes.length === 0) {
    throw new Error('No quotes returned from M0 API')
  }

  const quote = quotes[0]

  const payloads = quote.payloads
  if (!Array.isArray(payloads) || payloads.length === 0) {
    throw new Error('Quote has no payloads')
  }

  const transactionBase64s = payloads.map((payload: { data?: { type?: string; transaction?: string } }, index: number) => {
    if (payload.data?.type !== 'svm') {
      throw new Error(`Unsupported payload type from M0 API at index ${index}: ${String(payload.data?.type)}`)
    }
    if (!payload.data.transaction) {
      throw new Error(`Quote payload at index ${index} has no transaction`)
    }
    return payload.data.transaction
  })

  return {
    amountIn: quote.amountIn,
    amountOut: quote.amountOut,
    transactionBase64s,
  }
}
