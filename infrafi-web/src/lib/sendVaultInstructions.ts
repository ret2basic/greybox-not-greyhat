import type { Provider } from '@reown/appkit-utils/solana'
import {
  Transaction,
  type TransactionInstruction,
  type Connection,
  type PublicKey,
} from '@solana/web3.js'
import { confirmSolanaSignature } from '@/lib/confirmSolanaSignature'

export const VAULT_TX_COMMITMENT = 'confirmed' as const

export async function sendVaultInstructions(
  connection: Connection,
  walletProvider: Provider,
  owner: PublicKey,
  instructions: TransactionInstruction[],
): Promise<string> {
  const tx = new Transaction().add(...instructions)
  tx.feePayer = owner
  const { blockhash } = await connection.getLatestBlockhash(VAULT_TX_COMMITMENT)
  tx.recentBlockhash = blockhash
  const signature = await walletProvider.sendTransaction(tx, connection)
  await confirmSolanaSignature(connection, signature, VAULT_TX_COMMITMENT)
  return signature
}
