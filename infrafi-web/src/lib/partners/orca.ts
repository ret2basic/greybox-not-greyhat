import { address, createSolanaRpc, type Address } from '@solana/kit'
import {
  fetchAllMaybePosition,
  fetchAllWhirlpool,
  getPositionAddress,
} from '@orca-so/whirlpools-client'
import { deriveVaultShareMint } from 'glow-vaults-sdk'
import { GLOW_DEVNET_VAULT, USDC_MINT, USDTEL_MINT } from '@/lib/solana'
import { formatUsd, type PartnerFetchContext, type PartnerPosition } from './types'

// Whirlpool addresses for the two DAWN pools on Orca (verified via the public
// pools API). Keyed by the matching `id` in `@/components/boost/data.ts`.
export const ORCA_WHIRLPOOLS = {
  'orca-susdtel-usdtel': '34ri8LjXhtwViLTUNiYBJYUPMLpzKThwNgq7LZWZQz8o', // USD.tel / sUSD.tel
  'orca-usdtel-usdc': 'HDHQDJENWCrw6CisxwGTSRksoWAkuQUeFxKdJ4Knf7YL', // USD.tel / USDC
} as const

type OrcaStrategyId = keyof typeof ORCA_WHIRLPOOLS

// Same-origin proxy to Orca's per-pool endpoint (the browser can't call
// api.orca.so directly — no CORS). See `src/app/api/orca/pools/[address]`.
const ORCA_POOLS_API = '/api/orca/pools'

/**
 * Pool-derived stats (what Orca actually reports). The sUSD.tel base yield is
 * layered on by the section via `useEffectiveBaseApy` + `composeNetApy`, so
 * every strategy shares one base figure.
 */
export type OrcaPoolRaw = {
  tvl: string // "$202"
  tvlUsd: number // 201.74 — raw, for aggregating section TVL
  feeAprPct: number // 0
  // Spot pool price as Orca reports it: token B per token A (e.g. for the
  // USD.tel/sUSD.tel pool, sUSD.tel per USD.tel). Consumers invert as needed.
  // 0 when missing/unparseable.
  price: number
}

type OrcaPoolResponse = {
  data?: {
    tvlUsdc?: string
    yieldOverTvl?: string | null
    price?: string
    stats?: Partial<Record<'24h' | '7d' | '30d', { yieldOverTvl?: string | null }>>
  }
}

export function formatUsdCompact(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`
  return `$${value.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}

async function fetchPoolStats(address: string): Promise<OrcaPoolRaw | null> {
  const response = await fetch(`${ORCA_POOLS_API}/${address}`)
  if (!response.ok) return null
  const pool = ((await response.json()) as OrcaPoolResponse).data
  if (!pool) return null

  const tvlUsd = Number(pool.tvlUsdc ?? 0)
  const safeTvl = Number.isFinite(tvlUsd) ? tvlUsd : 0
  // `yieldOverTvl` is an annualized fraction (0.113 → 11.3%). Prefer the 30d
  // window, fall back to the lifetime value; both are ~0 while pools are empty.
  const feeFraction = Number(pool.stats?.['30d']?.yieldOverTvl ?? pool.yieldOverTvl ?? 0) || 0
  const price = Number(pool.price ?? 0) || 0

  return {
    tvl: formatUsdCompact(safeTvl),
    tvlUsd: safeTvl,
    feeAprPct: feeFraction * 100,
    price,
  }
}

/**
 * Fetches pool-derived stats for both Orca pools, keyed by strategy id. A
 * failed pool is simply omitted so its row falls back to the static figures.
 */
export const fetchOrcaPoolStats = async (): Promise<Record<string, OrcaPoolRaw>> => {
  const entries = Object.entries(ORCA_WHIRLPOOLS) as [OrcaStrategyId, string][]
  const results = await Promise.all(
    entries.map(
      async ([id, address]) =>
        [id, await fetchPoolStats(address).catch(() => null)] as const,
    ),
  )

  const map: Record<string, OrcaPoolRaw> = {}
  for (const [id, stats] of results) {
    if (stats) map[id] = stats
  }
  return map
}

// ── Wallet positions ───────────────────────────────────────────────────────
// Orca exposes NO REST endpoint for an owner's positions, so we read them on
// chain via the official `@orca-so/whirlpools-client` (pure-JS Codama codecs —
// the math-heavy `@orca-so/whirlpools-core` is WASM and intentionally avoided).
// web3.js v2 (`@solana/kit`) is used *only inside this module* so its types never
// leak into the v1 codebase.

// SPL token program ids — Orca position NFTs live under one or the other.
const TOKEN_PROGRAM_ADDRESS = 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'
const TOKEN_2022_PROGRAM_ADDRESS = 'TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb'
// Every leg of the two DAWN pools (USD.tel / sUSD.tel / USDC) uses 6 decimals.
const ORCA_TOKEN_DECIMALS = 6
const Q64 = 2 ** 64

// Underlying token amounts (base units) of a concentrated-liquidity position
// from its liquidity + tick range vs the pool's current sqrt price. Float math
// is enough for a display USD figure; mirrors Orca's tryGetAmountDeltaA/B.
function positionTokenAmounts(
  sqrtPriceX64: bigint,
  tickLowerIndex: number,
  tickUpperIndex: number,
  liquidity: bigint,
): { amountA: number; amountB: number } {
  const current = Number(sqrtPriceX64) / Q64
  const lower = Math.pow(1.0001, tickLowerIndex / 2)
  const upper = Math.pow(1.0001, tickUpperIndex / 2)
  const liq = Number(liquidity)
  let amountA = 0
  let amountB = 0
  if (current <= lower) {
    amountA = liq * (1 / lower - 1 / upper)
  } else if (current >= upper) {
    amountB = liq * (upper - lower)
  } else {
    amountA = liq * (1 / current - 1 / upper)
    amountB = liq * (current - lower)
  }
  return { amountA: Math.max(0, amountA), amountB: Math.max(0, amountB) }
}

type OrcaPositionAccount = { parsed?: { info?: { mint?: string; tokenAmount?: { amount?: string; decimals?: number } } } }

export const fetchOrcaPositions = async ({
  walletAddress,
  connection,
}: PartnerFetchContext): Promise<PartnerPosition[]> => {
  if (!connection) return []
  try {
    const rpc = createSolanaRpc(connection.rpcEndpoint)
    const owner = address(walletAddress)

    // 1. Candidate position-NFT mints from the owner's token accounts.
    const tokenResults = await Promise.all(
      [TOKEN_PROGRAM_ADDRESS, TOKEN_2022_PROGRAM_ADDRESS].map((programId) =>
        rpc
          .getTokenAccountsByOwner(owner, { programId: address(programId) }, { encoding: 'jsonParsed' })
          .send(),
      ),
    )
    const nftMints: Address[] = []
    for (const result of tokenResults) {
      for (const entry of result.value) {
        const info = (entry.account.data as OrcaPositionAccount).parsed?.info
        if (info?.mint && info.tokenAmount?.decimals === 0 && info.tokenAmount.amount === '1') {
          nftMints.push(address(info.mint))
        }
      }
    }
    if (nftMints.length === 0) return []

    // 2. Derive + fetch the position account for each NFT mint.
    const positionAddresses = await Promise.all(
      nftMints.map(async (mint) => (await getPositionAddress(mint))[0]),
    )
    const maybePositions = await fetchAllMaybePosition(rpc, positionAddresses)

    // 3. Keep only positions in our DAWN whirlpools.
    const whirlpoolToStrategy = new Map<string, OrcaStrategyId>(
      (Object.entries(ORCA_WHIRLPOOLS) as [OrcaStrategyId, string][]).map(([id, addr]) => [addr, id]),
    )
    const positions = maybePositions.filter(
      (p): p is Extract<typeof p, { exists: true }> =>
        p.exists && whirlpoolToStrategy.has(p.data.whirlpool),
    )
    if (positions.length === 0) return []

    // 4. Fetch each relevant whirlpool once for its sqrt price + token mints.
    const poolAddresses = [...new Set(positions.map((p) => p.data.whirlpool))].map((a) => address(a))
    const pools = await fetchAllWhirlpool(rpc, poolAddresses)
    const poolByAddress = new Map(pools.map((pool) => [pool.address as string, pool.data]))

    // 5. Aggregate token amounts + USD per strategy across the wallet's positions.
    const shareMint = deriveVaultShareMint(GLOW_DEVNET_VAULT).toBase58()
    const symbolFor = (mint: string): string =>
      mint === USDTEL_MINT.toBase58()
        ? 'USD.tel'
        : mint === USDC_MINT.toBase58()
          ? 'USDC'
          : mint === shareMint
            ? 'sUSD.tel'
            : 'tokens'

    type Agg = { symbolA: string; symbolB: string; amountA: number; amountB: number }
    const byStrategy = new Map<OrcaStrategyId, Agg>()
    for (const position of positions) {
      const strategyId = whirlpoolToStrategy.get(position.data.whirlpool)!
      const pool = poolByAddress.get(position.data.whirlpool)
      if (!pool) continue
      const { amountA, amountB } = positionTokenAmounts(
        pool.sqrtPrice,
        position.data.tickLowerIndex,
        position.data.tickUpperIndex,
        position.data.liquidity,
      )
      const agg = byStrategy.get(strategyId) ?? {
        symbolA: symbolFor(pool.tokenMintA),
        symbolB: symbolFor(pool.tokenMintB),
        amountA: 0,
        amountB: 0,
      }
      agg.amountA += amountA / 10 ** ORCA_TOKEN_DECIMALS
      agg.amountB += amountB / 10 ** ORCA_TOKEN_DECIMALS
      byStrategy.set(strategyId, agg)
    }

    return [...byStrategy.entries()].flatMap(([strategyId, agg]) => {
      // Every leg of the DAWN pools is a ~$1 stable, so summing the UI amounts is
      // a faithful USD estimate without a separate price oracle.
      const usd = agg.amountA + agg.amountB
      if (usd <= 0) return []
      const fmt = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 2 })
      return [
        {
          strategyId,
          balanceLabel: `${fmt(agg.amountA)} ${agg.symbolA} + ${fmt(agg.amountB)} ${agg.symbolB}`,
          usdLabel: formatUsd(usd),
        },
      ]
    })
  } catch (error) {
    console.warn('[partners/orca] Failed to fetch positions.', error)
    return []
  }
}
