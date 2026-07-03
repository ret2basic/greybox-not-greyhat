// Wallet adapters (Phantom, etc.) and @solana/web3.js retry sendTransaction
// when confirmation polling lags. If the first attempt actually landed, the
// retry's simulation fails with "this transaction has already been processed"
// and bubbles up as a SendTransactionError — even though the deposit /
// withdrawal succeeded on chain.
//
// This helper detects that benign case so callers can treat it as success
// rather than surfacing a confusing error to the user.
export function isAlreadyProcessedError(err: unknown): boolean {
  const message =
    err instanceof Error ? err.message : typeof err === 'string' ? err : ''
  return /already\s+(been\s+)?processed/i.test(message)
}

// Friendly mapping for Glow Vault Anchor program errors. The on-chain logs
// include "Error Code: <CamelCase>. Error Number: <n>. Error Message: <…>".
// We surface the human message and (where possible) tighten it for retail
// users; full logs still go to the console for diagnostics.
const VAULT_ERROR_FRIENDLY: Record<string, string> = {
  StaleVaultPrices:
    'Vault prices need refreshing before this deposit can land. The protocol operator runs this on a schedule — please try again in a few minutes.',
}

const ANCHOR_ERROR_RE =
  /AnchorError[\s\S]*?Error Code:\s*(\w+)[\s\S]*?Error Message:\s*([^.\n]+)/
const SIMULATION_FAILURE_RE =
  /(treasury submit simulation failed|transaction simulation failed|simulate(?:d)? transaction failed)/i

// Extract a single user-friendly line from a Solana program error.
// Falls back to the raw message if no Anchor pattern is found.
export function friendlySolanaError(err: unknown): string {
  const raw =
    err instanceof Error ? err.message : typeof err === 'string' ? err : ''
  const match = raw.match(ANCHOR_ERROR_RE)
  if (match) {
    const [, code, message] = match
    const friendly = VAULT_ERROR_FRIENDLY[code]
    return friendly ?? `${message.trim()} (${code})`
  }
  // Strip the "Catch the SendTransactionError…" boilerplate web3 appends.
  const trimmed = raw.replace(/\s*Catch the `SendTransactionError`[\s\S]*$/i, '').trim()
  // For the multi-line "Logs: [ … ]" envelope, just take the first sentence.
  const firstLine = trimmed.split('\n')[0]
  if (SIMULATION_FAILURE_RE.test(firstLine)) {
    return 'Transaction could not be submitted. Please try again.'
  }
  return firstLine || 'Transaction failed.'
}
