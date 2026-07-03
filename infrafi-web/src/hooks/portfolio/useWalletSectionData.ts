'use client'

import { useMemo } from 'react'
import { getWalletPointsAndApyByAsset } from '@/components/portfolio/constants'
import {
  formatClaimableDate,
  formatDisplayAmount,
  getDaysUntil,
} from '@/components/portfolio/formatters'
import type { PendingDepositActionStyle } from '@/components/portfolio/wallet-section/types'
import type { PositionRow } from '@/components/portfolio/wallet-section/WalletTable'
import type { PortfolioAsset, WalletRow } from '@/components/portfolio/types'
import type { PortfolioBalances } from '@/hooks/portfolio/usePortfolioBalances'
import { usePortfolioPoints } from '@/hooks/portfolio/usePortfolioPoints'
import { useSolanaSwap } from '@/hooks/useSolanaSwap'
import { useVaultStake } from '@/hooks/useVaultStake'
import { useNav } from '@/store'
import { formatTokenBalance } from '@/utils/formatAmount'

export type PendingDepositPanelRow = {
  index: number
  amount: string
  asset: PortfolioAsset
  actionKind: 'claim' | 'cancel'
  actionLabel: string
  actionStyle: PendingDepositActionStyle
  isDisabled: boolean
  // Unix seconds the deposit becomes claimable — lets consumers recompute
  // readiness/countdown live at render rather than at fetch time.
  claimableAtTimestamp: number
}

export type PositionActivityKind = 'settling' | 'locked' | 'claimable'

export type PositionActivityItem = {
  index: number
  asset: PortfolioAsset
  amountLabel: string
  kind: PositionActivityKind
  startedAgoLabel: string
  completesInLabel: string
  daysRemainingLabel: string
  claimableDateLabel: string
  canCancel: boolean
}

export type PositionDetails = {
  totalLabel: string
  liquidLabel: string
  lockedLabel: string
  nextClaimableLabel: string
  activity: PositionActivityItem[]
}

const LOCKED_THRESHOLD_SECONDS = 86_400

const humanizeDuration = (seconds: number) => {
  const safeSeconds = Math.max(0, seconds)
  if (safeSeconds < 60) {
    return 'less than a minute'
  }
  if (safeSeconds < 3_600) {
    return `${Math.round(safeSeconds / 60)}m`
  }
  if (safeSeconds < LOCKED_THRESHOLD_SECONDS) {
    return `${Math.round(safeSeconds / 3_600)}h`
  }
  return `${Math.round(safeSeconds / LOCKED_THRESHOLD_SECONDS)}d`
}

const formatFullDate = (timestampSeconds: number | null) => {
  if (timestampSeconds === null) {
    return '-'
  }
  return new Date(timestampSeconds * 1000).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export const useWalletSectionData = (balances: PortfolioBalances) => {
  const { isConnected, isLoading, mainnetUsdtelBalance, susdtelBalance, usdtelBalance } = balances
  const { executeSwap, isSwapping, swapError } = useSolanaSwap(
    isConnected ? mainnetUsdtelBalance : '0',
    'sell',
  )
  const stakeFlow = useVaultStake('')
  const nav = useNav((state) => state.nav)
  const { walletPoints } = usePortfolioPoints()
  const pointsAndApyByAsset = useMemo(
    () => getWalletPointsAndApyByAsset({ points: walletPoints, apy: nav?.apy }),
    [nav?.apy, walletPoints],
  )

  const lockedUsdtelAmountLabel = useMemo(() => {
    const totalLocked = stakeFlow.pendingDeposits.reduce((accumulator, deposit) => {
      return accumulator + Number(deposit.pendingSharesUi)
    }, 0)
    return `${formatDisplayAmount(String(totalLocked))} USD.tel`
  }, [stakeFlow.pendingDeposits])

  const walletRows = useMemo<WalletRow[]>(() => {
    const dynamicRows: Array<{ asset: PortfolioAsset; balance: string }> = [
      { asset: 'USD.tel', balance: isConnected ? usdtelBalance : '0' },
      { asset: 'sUSD.tel', balance: isConnected ? susdtelBalance : '0' },
    ]

    return dynamicRows.map((row) => ({
      asset: row.asset,
      balance: formatTokenBalance(row.balance),
      usd: `$${formatTokenBalance(row.balance)}`,
      lockedBalance: row.asset === 'USD.tel' ? lockedUsdtelAmountLabel : '-',
      points: pointsAndApyByAsset[row.asset].points,
      apy: pointsAndApyByAsset[row.asset].apy,
      action: row.asset === 'USD.tel' ? 'withdraw' : 'none',
      isBalanceLoading: isConnected && isLoading,
    }))
  }, [
    isConnected,
    isLoading,
    lockedUsdtelAmountLabel,
    pointsAndApyByAsset,
    susdtelBalance,
    usdtelBalance,
  ])

  // Real positions for the "Portfolio detail" table. infrafi-api exposes no
  // per-venue / per-position feed (venue, chain, per-position status/APY), so we
  // surface the two on-chain holdings the user actually has: idle USD.tel and
  // staked sUSD.tel. Zero balances are filtered out.
  const positionRows = useMemo<PositionRow[]>(() => {
    if (!isConnected) {
      return []
    }

    const rows: PositionRow[] = []

    if (Number(usdtelBalance) > 0) {
      const balance = formatTokenBalance(usdtelBalance)
      rows.push({
        id: 'usdtel',
        token: 'USD.tel',
        asset: 'USD.tel',
        status: 'idle',
        balance,
        balanceSub: 'Liquid',
        usd: `$${balance}`,
        apy: '-',
        action: 'manage',
      })
    }

    if (Number(susdtelBalance) > 0) {
      const balance = formatTokenBalance(susdtelBalance)
      rows.push({
        id: 'susdtel',
        token: 'sUSD.tel',
        asset: 'sUSD.tel',
        status: 'available',
        balance,
        balanceSub: 'Staked',
        usd: `$${balance}`,
        apy: pointsAndApyByAsset['sUSD.tel'].apy,
        apyAccent: true,
        action: 'manage',
      })
    }

    return rows
  }, [isConnected, pointsAndApyByAsset, susdtelBalance, usdtelBalance])

  const pendingPanelData = useMemo(() => {
    const nowSeconds = Math.floor(Date.now() / 1000)
    const rows: PendingDepositPanelRow[] = stakeFlow.pendingDeposits.map((deposit) => {
      const daysUntilClaim = getDaysUntil(deposit.claimableAtTimestamp, nowSeconds)
      const asset: PortfolioAsset = deposit.isClaimable ? 'sUSD.tel' : 'USD.tel'
      const actionLabel = deposit.isClaimable ? 'Claim sUSD.tel' : `Cancel deposit (${daysUntilClaim}d left)`
      const actionStyle: PendingDepositActionStyle = 'accent'

      return {
        index: deposit.index,
        amount: formatDisplayAmount(deposit.pendingSharesUi),
        asset,
        actionKind: deposit.isClaimable ? 'claim' : 'cancel',
        actionLabel,
        actionStyle,
        isDisabled: stakeFlow.isSubmitting,
        claimableAtTimestamp: deposit.claimableAtTimestamp,
      }
    })

    const totalEscrow = stakeFlow.pendingDeposits.reduce((accumulator, deposit) => {
      return accumulator + Number(deposit.pendingSharesUi)
    }, 0)
    const nextClaimableTimestamp = stakeFlow.pendingDeposits.reduce<number | null>((current, deposit) => {
      if (current === null) {
        return deposit.claimableAtTimestamp
      }
      return Math.min(current, deposit.claimableAtTimestamp)
    }, null)

    return {
      pendingCount: rows.length,
      rows,
      totalEscrowLabel: `${formatDisplayAmount(String(totalEscrow))} sUSD.tel`,
      nextClaimableLabel: formatClaimableDate(nextClaimableTimestamp),
    }
  }, [stakeFlow.isSubmitting, stakeFlow.pendingDeposits])

  const positionDetails = useMemo<PositionDetails>(() => {
    const nowSeconds = Math.floor(Date.now() / 1000)
    const lockedAmount = stakeFlow.pendingDeposits.reduce((accumulator, deposit) => {
      return accumulator + Number(deposit.pendingSharesUi)
    }, 0)
    const liquidAmount = Number(susdtelBalance)
    const nextClaimableTimestamp = stakeFlow.pendingDeposits.reduce<number | null>((current, deposit) => {
      if (current === null) {
        return deposit.claimableAtTimestamp
      }
      return Math.min(current, deposit.claimableAtTimestamp)
    }, null)

    const activity = stakeFlow.pendingDeposits.map<PositionActivityItem>((deposit) => {
      const remainingSeconds = deposit.claimableAtTimestamp - nowSeconds
      const elapsedSeconds = nowSeconds - deposit.depositTimestamp
      const kind: PositionActivityKind = deposit.isClaimable
        ? 'claimable'
        : remainingSeconds > LOCKED_THRESHOLD_SECONDS
          ? 'locked'
          : 'settling'
      const asset: PortfolioAsset = kind === 'settling' ? 'USD.tel' : 'sUSD.tel'

      return {
        index: deposit.index,
        asset,
        amountLabel: `${formatDisplayAmount(deposit.pendingSharesUi)} ${asset}`,
        kind,
        startedAgoLabel: `Started ${humanizeDuration(elapsedSeconds)} ago`,
        completesInLabel: `Usually completes in ${humanizeDuration(remainingSeconds)}`,
        daysRemainingLabel: `${getDaysUntil(deposit.claimableAtTimestamp, nowSeconds)} days remaining`,
        claimableDateLabel: formatFullDate(deposit.claimableAtTimestamp),
        canCancel: !deposit.isClaimable && !stakeFlow.isSubmitting,
      }
    })

    return {
      totalLabel: formatDisplayAmount(String(liquidAmount + lockedAmount)),
      liquidLabel: formatDisplayAmount(String(liquidAmount)),
      lockedLabel: formatDisplayAmount(String(lockedAmount)),
      nextClaimableLabel: formatFullDate(nextClaimableTimestamp),
      activity,
    }
  }, [stakeFlow.isSubmitting, stakeFlow.pendingDeposits, susdtelBalance])

  const canWithdraw = isConnected && Number(mainnetUsdtelBalance) > 0 && !isSwapping

  const handleWithdraw = async (amount?: string) => {
    const requestedAmount = amount && Number(amount) > 0 ? amount : mainnetUsdtelBalance
    if (!canWithdraw || Number(requestedAmount) <= 0) {
      return undefined
    }

    return executeSwap(requestedAmount)
  }

  return {
    isConnected,
    isLoading,
    pendingPanelData,
    positionDetails,
    positionRows,
    walletRows,
    canWithdraw,
    withdrawMaxAmount: mainnetUsdtelBalance,
    isWithdrawing: isSwapping,
    withdrawError: swapError,
    onWithdraw: handleWithdraw,
    onClaim: (depositIndex: number) => void stakeFlow.claimDepositedShares(depositIndex),
    onCancel: (depositIndex: number) => void stakeFlow.cancelPendingDeposit(depositIndex),
  }
}
