import { NextRequest } from 'next/server'
import { handleSolanaRpc } from '@/app/api/rpc/_shared'

type RouteContext = {
  params: Promise<{ cluster: string }>
}

export async function OPTIONS(req: NextRequest, context: RouteContext) {
  const { cluster } = await context.params
  return handleSolanaRpc(req, cluster)
}

export async function POST(req: NextRequest, context: RouteContext) {
  const { cluster } = await context.params
  return handleSolanaRpc(req, cluster)
}
