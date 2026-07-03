import { NextRequest } from 'next/server'
import { handleSolanaRpc } from '@/app/api/rpc/_shared'

export async function OPTIONS(req: NextRequest) {
  return handleSolanaRpc(req, 'mainnet')
}

export async function POST(req: NextRequest) {
  return handleSolanaRpc(req, 'mainnet')
}
