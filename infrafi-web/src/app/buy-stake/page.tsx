import BuyStakeApp from '@/components/buy-stake/BuyStakeApp'

// The buy-stake route is rendered client-only via BuyStakeApp's
// `mounted` gate. This gives AppLoader the CSR environment v6 was
// designed for, eliminating the SSR/Suspense timing problems that
// were breaking the typing animation and hairline anchor.
export default function BuyStakePage() {
  return <BuyStakeApp />
}
