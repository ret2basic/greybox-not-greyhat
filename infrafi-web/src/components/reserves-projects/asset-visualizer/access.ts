import type { AccessTech } from './types'

// Per-access-tech display tokens. Mirrors the design's ACCESS_TYPES table.
// Keys match the renderer schema's AccessTech values; we use 'hallway-wifi'
// where the design uses 'hallway' so that downstream lookups can use either.

export interface AccessSpec {
  id: AccessTech
  label: string
  color: string
  short: string
  // 'hallway' = APs along center spine, no per-unit drops
  // others    = drops + in-unit access node (AP/CPE/ONT)
  dropPattern: 'hallway-only' | 'drop-then-ap' | 'drop-then-cpe' | 'drop-then-ont'
  desc: string
  // Visual rendering hints for the access edges.
  thickness: number
  dashed: boolean
}

export const ACCESS_TYPES: Record<AccessTech, AccessSpec> = {
  'hallway-wifi': {
    id: 'hallway-wifi',
    label: 'Hallway AP',
    color: '#C7AFFF',
    short: 'AP',
    dropPattern: 'hallway-only',
    desc: 'WiFi-7 in shared common areas',
    thickness: 1.0,
    dashed: false,
  },
  ethernet: {
    id: 'ethernet',
    label: 'Ethernet + In-unit AP',
    color: '#9DEAFF',
    short: 'ETH',
    dropPattern: 'drop-then-ap',
    desc: 'Cat6a from IDF · in-unit AP',
    thickness: 0.9,
    dashed: true,
  },
  coax: {
    id: 'coax',
    label: 'Coax + CPE',
    color: '#FF8A65',
    short: 'COAX',
    dropPattern: 'drop-then-cpe',
    desc: 'MoCA / DOCSIS · CPE in unit',
    thickness: 1.4,
    dashed: false,
  },
  gpon: {
    id: 'gpon',
    label: 'GPON + ONT',
    color: '#7AE0B0',
    short: 'GPON',
    dropPattern: 'drop-then-ont',
    desc: 'Fiber to unit · ONT terminal',
    thickness: 0.7,
    dashed: false,
  },
}

export const ACCESS_LIST: AccessTech[] = ['hallway-wifi', 'ethernet', 'coax', 'gpon']

// Hierarchy color tokens — used by the visualizer's MDF/IDF/POE/bcast nodes.
export const POE_COLOR = '#7BD9FF'
export const MDF_COLOR = '#F3A24A'
export const IDF_COLOR = '#A8E063'
export const BCAST_COLOR = '#E48DD0'
export const TOWER_LINE = 'rgba(232, 224, 240, 0.55)'
export const TOWER_DIM = 'rgba(232, 224, 240, 0.22)'
export const TOWER_ACCENT = '#F3A24A'
