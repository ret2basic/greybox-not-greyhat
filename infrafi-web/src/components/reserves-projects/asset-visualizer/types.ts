// Renderer-facing schema for an asset's building plan. Mirrors
// infrafi-manager/src/types/building-plan.ts — keep them in sync.
//
// The web app reads this from `BuildingPlanRecord.plan` (the JSONB blob
// served by /project/:id/building) and consumes it directly in the asset
// visualizer (Tower3D + RightPanel). Coordinates are renderer design
// pixels with origin = polygon bbox centroid; +x = east, +z = south,
// 1 unit ≈ 1 foot.

export type Vec2 = [number, number]

export type AccessTech = 'gpon' | 'ethernet' | 'coax' | 'hallway-wifi'
export type MdfPlacement = 'basement' | 'roof'
export type PoeKind = 'fiber' | 'fwa'

export interface BuildingMetadata {
  apr: string
  tvl: string
  subscribers: number
}

export interface FillRect {
  cx: number
  cz: number
  w: number
  d: number
}

export interface BulkheadInstance {
  id: string
  x: number
  z: number
  w: number
  d: number
  h: number
  rotation: number
  label: string
}

export interface RiserSpec {
  x: number
  z: number
}

export interface MdfSpec {
  placement: MdfPlacement
  x: number
  z: number
  // When placement === 'roof', references the bulkhead that houses the MDF.
  bulkheadId?: string
}

export interface PoeStats {
  latency: string
  active: string
  capacity: string
}

export interface PoeSpec {
  kind: PoeKind
  provider: string
  x: number
  z: number
  stats: PoeStats
}

export interface BroadcastAntenna {
  id: string
  x: number
  z: number
  height: number
  label: string
}

export interface Wing {
  id: string
  label: string
  spineFrom: Vec2
  spineTo: Vec2
  apCount: number
}

export interface BuildingPlan {
  schemaVersion: 1
  building: {
    name: string
    city: string
    metadata: BuildingMetadata
    projectId?: string | null
    backhaul?: string | null
    uptime?: string | null
  }
  geometry: {
    floorCount: number
    floorHeight: number
    outline: Vec2[]
    fillRects: FillRect[]
  }
  infra: {
    riser: RiserSpec
    mdf: MdfSpec
    poe: PoeSpec
    bulkheads: BulkheadInstance[]
    broadcastAntennas: BroadcastAntenna[]
  }
  distribution: {
    accessTech: AccessTech
    idfFloors: number[]
    wings: Wing[]
  }
}

// ── RightPanel device catalog ─────────────────────────────────
// Mirrors v5's catalog shape (AVAccessConcepts.jsx 505–525). The
// RightPanel's logical-tree iterates this array, and the device
// list expansion uses each entry's `devices` for click-to-focus.

export interface CatalogDevice {
  id: string
  label: string
  // 3D scene coordinates. Used for the camera focusOn move on click.
  x: number
  y: number
  z: number
}

export type DeviceKey = 'poe' | 'mdf' | 'idf' | 'bcast' | 'access'

export interface DeviceCategory {
  key: DeviceKey
  label: string
  short?: string
  color: string
  hidden?: boolean
  devices: CatalogDevice[]
}

export type DeviceCatalog = DeviceCategory[]

// Shape consumed by the RightPanel's bottom (detail) pane.
export interface SelectedNodeDetail {
  id: string
  kind: string
  title: string
  subtitle?: string
  stats?: Array<{ label: string; value: string; color?: string }>
  status?: 'online' | 'degraded' | 'offline'
  uptime?: string
}
