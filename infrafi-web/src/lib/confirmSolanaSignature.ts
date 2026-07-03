import type { Commitment, Connection, TransactionConfirmationStatus } from '@solana/web3.js'

const POLL_INTERVAL_MS = 750
const MAX_WAIT_MS = 120_000

function meetsCommitment(
  status: TransactionConfirmationStatus | null | undefined,
  commitment: Commitment,
): boolean {
  if (!status) {
    return false
  }
  if (commitment === 'finalized') {
    return status === 'finalized'
  }
  if (commitment === 'confirmed') {
    return status === 'confirmed' || status === 'finalized'
  }
  return status === 'processed' || status === 'confirmed' || status === 'finalized'
}

/**
 * Waits until the signature reaches the requested commitment using HTTP polling.
 * Avoids confirmTransaction({ blockhash, lastValidBlockHeight }), which can throw
 * "block height exceeded" after slow signing or flaky RPC WebSockets even when the tx landed.
 */
export async function confirmSolanaSignature(
  connection: Connection,
  signature: string,
  commitment: Commitment,
): Promise<void> {
  const deadline = Date.now() + MAX_WAIT_MS

  while (Date.now() < deadline) {
    const { value } = await connection.getSignatureStatuses([signature], {
      searchTransactionHistory: true,
    })
    const st = value[0]
    if (st?.err) {
      throw new Error(JSON.stringify(st.err))
    }
    if (meetsCommitment(st?.confirmationStatus ?? null, commitment)) {
      return
    }
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS))
  }

  throw new Error(
    'Transaction confirmation timed out. If you approved the transaction, check its status in a Solana explorer.',
  )
}
