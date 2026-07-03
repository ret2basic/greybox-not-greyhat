'use client'

// import RestrictedAccessModal, { RestrictedAccessFullPage } from '@/components/RestrictedAccessModal'
import { ReownAppKitThemeSync } from '@/components/ReownAppKitThemeSync'
import WalletBrowserPromptModal from '@/components/WalletBrowserPromptModal'
import { useProviders } from '@/hooks/providers/useProviders'
// import { useCompliance } from '@/store'
import { QueryClientProvider } from '@tanstack/react-query'
import { HeroUIProvider } from '@heroui/react'
import { type FC, type ReactNode } from 'react'

type ProvidersProps = {
  children: ReactNode
}

const Providers: FC<ProvidersProps> = ({ children }) => {
  const { queryClient } = useProviders()
  // const initializeCompliance = useCompliance((state) => state.initializeCompliance)

  // useEffect(() => {
  //   void initializeCompliance()
  // }, [initializeCompliance])

  return (
    <QueryClientProvider client={queryClient}>
      <HeroUIProvider>
        <ReownAppKitThemeSync />
        {children}
        <WalletBrowserPromptModal />
        {/* <RestrictedAccessFullPage /> */}
        {/* <RestrictedAccessModal /> */}
      </HeroUIProvider>
    </QueryClientProvider>
  )
}

export default Providers
