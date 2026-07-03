import { NextResponse } from 'next/server'
import { getM0OrchestrationApiKey } from '@/lib/serverEnv'

export async function GET() {
  const m0KeyPresent = Boolean(getM0OrchestrationApiKey())
  return NextResponse.json(
    {
      status: 'ok',
      timestamp: new Date().toISOString(),
      service: 'infrafi-web',
      m0KeyPresent,
    },
    { status: 200 },
  )
}
