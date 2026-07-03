import {
  formatAmount,
  formatUsd,
  type PartnerFetchContext,
  type PartnerPosition,
} from './types'

// Loopscale exposes a public REST data API — no SDK or mint addresses needed,
// the connected wallet alone is enough to read its loops and loans.
// Docs: https://docs.loopscale.com/api-reference/data/positions/get-loan-info
const LOOPSCALE_LOANS_INFO_URL = 'https://tars.loopscale.com/v1/markets/loans/info'

// Strategy ids these positions map onto (see boost/data.ts).
const LOOP_STRATEGY_ID = 'loopscale-loop-susdtel'
const LEND_STRATEGY_ID = 'loopscale-lend-susdtel'

// Most stablecoin principals on Loopscale (USDC / sUSD.tel) use 6 decimals.
const PRINCIPAL_DECIMALS = 6

type LoopscaleLoan = {
  orderFundingType?: string // "Loop" | "Term"
  principalMint?: string
  // Loopscale records lamport amounts as strings; field naming may vary, so we
  // read a few likely keys defensively.
  principalRepaid?: string
  principalOutstanding?: string
  currentPrincipal?: string
  apy?: number // active interest rate, recorded in cBPS
}

type LoopscaleLoansResponse = {
  loans?: LoopscaleLoan[]
  data?: LoopscaleLoan[]
}

function toUiAmount(lamports: string | undefined): number {
  if (!lamports) return 0
  const value = Number(lamports)
  if (!Number.isFinite(value)) return 0
  return value / 10 ** PRINCIPAL_DECIMALS
}

function loanNotional(loan: LoopscaleLoan): number {
  return toUiAmount(loan.principalOutstanding ?? loan.currentPrincipal ?? loan.principalRepaid)
}

async function queryLoans(body: Record<string, unknown>): Promise<LoopscaleLoan[]> {
  const response = await fetch(LOOPSCALE_LOANS_INFO_URL, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ filterType: 'Active', pageSize: 1000, ...body }),
  })
  if (!response.ok) return []
  const json = (await response.json()) as LoopscaleLoansResponse
  return json.loans ?? json.data ?? []
}

function aggregate(loans: LoopscaleLoan[], strategyId: string): PartnerPosition | null {
  if (loans.length === 0) return null
  const total = loans.reduce((sum, loan) => sum + loanNotional(loan), 0)
  if (total <= 0) return null
  return {
    strategyId,
    // Loopscale stablecoin principals track ~$1, so notional ≈ USD value.
    balanceLabel: formatAmount(total, 'sUSD.tel'),
    usdLabel: formatUsd(total),
  }
}

export const fetchLoopscalePositions = async ({
  walletAddress,
}: PartnerFetchContext): Promise<PartnerPosition[]> => {
  try {
    // Looping = leveraged "Loop" orders the wallet borrows against.
    // Lending = "Term" orders the wallet supplies as a lender.
    const [loopLoans, lendLoans] = await Promise.all([
      queryLoans({ borrowers: [walletAddress], orderFundingType: 'Loop' }),
      queryLoans({ lenders: [walletAddress], orderFundingType: 'Term' }),
    ])

    return [
      aggregate(loopLoans, LOOP_STRATEGY_ID),
      aggregate(lendLoans, LEND_STRATEGY_ID),
    ].filter((position): position is PartnerPosition => position !== null)
  } catch {
    // Network/parse failure: degrade to no live position (row stays static).
    return []
  }
}
