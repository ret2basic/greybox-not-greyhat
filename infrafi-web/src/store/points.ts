'use client'

import { useApp } from './app'
import { createStore } from './util'

type PointsSummary = {
  id: string
  user_wallet: string
  season_id: string
  total_points: number
  estimated_tokens: number
  updated_at: string
}

type WalletPointsResponse = {
  summary: PointsSummary
  estimated_tokens: number
  season: {
    id: string
    number: number
    start_date: string
    end_date: string
    total_tokens: number
    created_at: string
  }
}

type LeaderboardResponse = {
  entries: PointsSummary[]
  season_total_points: number
}

interface PointsStore {
  seasonNumber: number | null
  seasonStartDate: string | null
  seasonEndDate: string | null
  leaderboardEntries: PointsSummary[]
  seasonTotalPoints: number
  walletAddress: string | null
  walletPoints: number
  walletRank: number | null
  loading: boolean
  fetchPortfolioPoints: (wallet: string) => Promise<void>
  clear: () => void
}

const LEADERBOARD_LIMIT = 500

export const usePoints = createStore<PointsStore>(
  'points',
  (set) => ({
    seasonNumber: null,
    seasonStartDate: null,
    seasonEndDate: null,
    leaderboardEntries: [],
    seasonTotalPoints: 0,
    walletAddress: null,
    walletPoints: 0,
    walletRank: null,
    loading: false,

    fetchPortfolioPoints: async (wallet) => {
      const { http } = useApp.getState()
      set({ loading: true })

      try {
        const [{ data: walletData }, { data: leaderboardData }] = await Promise.all([
          http.get<WalletPointsResponse>(`/points/${wallet}`),
          http.get<LeaderboardResponse>('/points/leaderboard', {
            params: { limit: LEADERBOARD_LIMIT },
          }),
        ])

        const walletRankIndex = leaderboardData.entries.findIndex((entry) => entry.user_wallet === wallet)

        set({
          seasonNumber: walletData.season.number,
          seasonStartDate: walletData.season.start_date,
          seasonEndDate: walletData.season.end_date,
          leaderboardEntries: leaderboardData.entries,
          seasonTotalPoints: leaderboardData.season_total_points,
          walletAddress: walletData.summary.user_wallet,
          walletPoints: walletData.summary.total_points,
          walletRank: walletRankIndex >= 0 ? walletRankIndex + 1 : null,
        })
      } finally {
        set({ loading: false })
      }
    },

    clear: () => {
      set({
        seasonNumber: null,
        seasonStartDate: null,
        seasonEndDate: null,
        leaderboardEntries: [],
        seasonTotalPoints: 0,
        walletAddress: null,
        walletPoints: 0,
        walletRank: null,
        loading: false,
      })
    },
  }),
  false,
)
