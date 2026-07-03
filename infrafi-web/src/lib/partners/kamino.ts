import type { PartnerPosition } from './types'

// Kamino is marked **pending** in the PM plan, so its rows render as "Soon"
// and this fetcher stays inert. When it goes live, integrate
// `@kamino-finance/klend-sdk` (web3.js v1 compatible):
//   const market = await KaminoMarket.load(connection, MARKET_PUBKEY, ...)
//   const obligation = await market.getObligationByWallet(walletPubkey, ...)
// and map deposits/borrows to strategy ids 'kamino-loop-susdtel' /
// 'kamino-lend-susdtel'.
// Docs: https://kamino.com/docs/build · SDK: @kamino-finance/klend-sdk
//
// TODO(partner-config): set the lending market pubkey + sUSD.tel reserve.
export const KAMINO_MARKET = undefined as string | undefined

export const fetchKaminoPositions = async (): Promise<PartnerPosition[]> => {
  return []
}
