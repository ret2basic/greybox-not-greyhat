'use client'

import { useApp } from './app'
import { createStore } from './util'

export interface Project {
  id: string
  spv_id: string
  name: string
  description: string
  types: string[]
  status: string
  city: string | null
  state: string | null
  country: string | null
  launch_date: string
  notes: string | null
  created_at: string
}

export interface GeoCoords {
  lng: number
  lat: number
}

// Geocode cache key. Lowercased + trimmed so trivial spelling/case differences
// share a cache slot. Keep the format stable — it's also written to localStorage.
export function geocodeKey(city: string, country: string): string {
  return `${city.trim().toLowerCase()}|${country.trim().toLowerCase()}`
}

const GEOCODE_LS_KEY = 'infrafi:geocode-cache:v1'

function loadGeocodeCache(): Record<string, GeoCoords | null> {
  if (typeof window === 'undefined') return {}
  try {
    const raw = window.localStorage.getItem(GEOCODE_LS_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function saveGeocodeCache(cache: Record<string, GeoCoords | null>): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(GEOCODE_LS_KEY, JSON.stringify(cache))
  } catch {
    // Quota exceeded or storage disabled — best-effort cache, ignore.
  }
}

// Nominatim's usage policy caps at ~1 req/s per IP and requires a non-default
// User-Agent (browsers send their own UA, which satisfies that). We chain all
// geocode requests through one tail-promise + spacing delay, and dedupe
// concurrent calls per-key so we never fire the same lookup twice.
const NOMINATIM_RATE_MS = 1100
let geocodeChain: Promise<unknown> = Promise.resolve()
const inflightGeocode = new Map<string, Promise<GeoCoords | null>>()

async function nominatimGeocode(city: string, country: string): Promise<GeoCoords | null> {
  const url = new URL('https://nominatim.openstreetmap.org/search')
  url.searchParams.set('city', city)
  url.searchParams.set('country', country)
  url.searchParams.set('format', 'json')
  url.searchParams.set('limit', '1')
  const res = await fetch(url.toString(), { headers: { Accept: 'application/json' } })
  if (!res.ok) return null
  const arr = (await res.json()) as Array<{ lat?: string; lon?: string }>
  if (!arr.length) return null
  const lat = Number(arr[0].lat)
  const lng = Number(arr[0].lon)
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null
  return { lat, lng }
}

export interface CapitalByType {
  project_type: string
  total_deployed: number
  project_count: number
}

export interface ProjectMetrics {
  project_id: string
  deployed_value: number
  yield_rate: number
}

// Server-side building_plan record. The `plan` blob holds the full editor
// state (renderer schema lives in src/types/building-plan.ts on the manager
// repo; will be mirrored here when we port the asset visualizer).
export interface BuildingPlanRecord {
  id: string
  project_id: string
  name: string
  backhaul: string | null
  uptime: string | null
  // Untyped on the wire — the visualizer module narrows it once ported.
  plan: unknown
  created_at: string
  updated_at: string
}

interface ProjectsStore {
  projects: Project[]
  capitalByType: CapitalByType[]
  projectMetrics: ProjectMetrics[]
  // Per-project buildings cache. Filled lazily as the user selects a project.
  buildingsByProject: Record<string, BuildingPlanRecord[]>
  // Geocode cache keyed by `${city}|${country}` (lowercased). `null` =
  // lookup attempted but Nominatim returned nothing — don't retry.
  coordsByLocation: Record<string, GeoCoords | null>
  loading: boolean

  fetchProjects: () => Promise<void>
  fetchCapitalByType: () => Promise<void>
  fetchProjectMetrics: () => Promise<void>
  fetchProjectBuildings: (projectId: string) => Promise<BuildingPlanRecord[]>
  fetchProjectCoords: (city: string, country: string) => Promise<GeoCoords | null>
}

export const useProjects = createStore<ProjectsStore>(
  'projects',
  (set, get) => ({
    projects: [],
    capitalByType: [],
    projectMetrics: [],
    buildingsByProject: {},
    coordsByLocation: loadGeocodeCache(),
    loading: false,

    fetchProjects: async () => {
      const { http } = useApp.getState()
      set({ loading: true })
      try {
        const { data } = await http.get<Project[]>('/project')
        set({ projects: data })
      } finally {
        set({ loading: false })
      }
    },

    fetchCapitalByType: async () => {
      const { http } = useApp.getState()
      const { data } = await http.get<CapitalByType[]>('/project/capital-by-type')
      set({ capitalByType: data })
    },

    fetchProjectMetrics: async () => {
      const { http } = useApp.getState()
      const { data } = await http.get<ProjectMetrics[]>('/project/metrics')
      set({ projectMetrics: data })
    },

    fetchProjectBuildings: async (projectId) => {
      // Cached after first fetch — Reserves & Projects calls this each time
      // a project pin is selected; we don't want to refetch on every click.
      const cached = get().buildingsByProject[projectId]
      if (cached) return cached
      const { http } = useApp.getState()
      try {
        const { data } = await http.get<BuildingPlanRecord[]>(
          `/project/${projectId}/building`,
        )
        set((state) => ({
          buildingsByProject: { ...state.buildingsByProject, [projectId]: data },
        }))
        return data
      } catch (err) {
        console.error('[useProjects.fetchProjectBuildings] failed', err)
        return []
      }
    },

    fetchProjectCoords: (city, country) => {
      if (!city || !country) return Promise.resolve(null)
      const key = geocodeKey(city, country)
      const cached = get().coordsByLocation[key]
      // `undefined` = never looked up; anything else (incl. null) is final.
      if (cached !== undefined) return Promise.resolve(cached)
      const inflight = inflightGeocode.get(key)
      if (inflight) return inflight
      const promise = geocodeChain
        .catch(() => null)
        .then(async () => {
          const coords = await nominatimGeocode(city, country).catch(() => null)
          // Space the next request out to honor Nominatim's rate cap.
          await new Promise((r) => setTimeout(r, NOMINATIM_RATE_MS))
          set((state) => {
            const next = { ...state.coordsByLocation, [key]: coords }
            saveGeocodeCache(next)
            return { coordsByLocation: next }
          })
          inflightGeocode.delete(key)
          return coords
        })
      inflightGeocode.set(key, promise)
      geocodeChain = promise
      return promise
    },
  }),
  false,
)
