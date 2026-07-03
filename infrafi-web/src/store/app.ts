'use client'

import axios, { type Axios } from 'axios'
import { createStore } from './util'

const API_URL = process.env.NEXT_PUBLIC_API_URL
if (!API_URL) throw new Error('NEXT_PUBLIC_API_URL is not set')

interface AppStore {
  http: Axios
  mode: 'light' | 'dark'

  initMode: () => void
  setMode: (mode: 'light' | 'dark') => void
}

export const useApp = createStore<AppStore>(
  'app',
  (set) => {
    const http = axios.create({ baseURL: API_URL })

    return {
      http,
      mode: 'dark',

      initMode: () => {
        const attr = document.documentElement.getAttribute('data-color-scheme')

        const current =
          attr === 'dark' || attr === 'light'
            ? attr
            : document.documentElement.classList.contains('dark')
              ? 'dark'
              : 'light'
        set({ mode: current })
      },

      setMode: (mode) => {
        document.documentElement.setAttribute('data-color-scheme', mode)

        if (mode === 'dark') {
          document.documentElement.classList.add('dark')
        } else {
          document.documentElement.classList.remove('dark')
        }

        document.cookie = `theme=${mode}; Max-Age=31536000; Path=/; SameSite=Lax`

        set({ mode })
      },
    }
  },
  false,
)
