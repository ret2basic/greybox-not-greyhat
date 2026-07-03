'use client';

import { Fragment, useState, useMemo, useRef, useEffect, useLayoutEffect, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import {
  DeploymentGlobe,
  STATUS_COLORS,
  locationLabel,
  formatDeployedValue,
} from './DeploymentGlobe';
import { AssetVisualizerPanel } from './asset-visualizer/AssetVisualizerPanel';
import { SegmentedToggle } from '@/components/ui/SegmentedToggle';
import { GradientButton } from '@/components/ui/GradientButton';
import DashboardInfoPopover from '@/components/ui/DashboardInfoPopover';
import { useProjects, useVault, geocodeKey, type BuildingPlanRecord, type GeoCoords, type Project, type ProjectMetrics } from '@/store';
import { ACCESS_TYPES as VIZ_ACCESS_TYPES } from './asset-visualizer/access';

// v5 templates read `window.ACCESS_TYPES[b.accessType]` to look up chip
// color/short label. Our visualizer module exports the same data under
// keys 'hallway-wifi' / 'gpon' / 'ethernet' / 'coax'; the v5-shape
// building objects we feed to the templates use 'hallway' for the
// hallway-WiFi tech (see toV5Building). Aliasing here keeps the lookup
// shape compatible with both keys.
function lookupAccessSpec(key: string): { color: string; short: string; label: string } | undefined {
  const norm = key === 'hallway' ? 'hallway-wifi' : key;
  const spec = (VIZ_ACCESS_TYPES as any)[norm];
  return spec ? { color: spec.color, short: spec.short, label: spec.label } : undefined;
}

// Compact money formatting (matches v5's "$37.5K", "$1.2M" style).
function formatMoneyCompact(amount: number): string {
  if (amount >= 1_000_000) return `$${(amount / 1_000_000).toFixed(1)}M`;
  if (amount >= 1_000) return `$${(amount / 1_000).toFixed(1)}K`;
  return `$${amount.toFixed(0)}`;
}

// Hook for the vault's idle reserves (dry powder).
function useDryPowder(): number | null {
  const dryPowder = useVault((s) => s.dryPowder);
  const fetchDryPowder = useVault((s) => s.fetchDryPowder);
  useEffect(() => { fetchDryPowder(); }, [fetchDryPowder]);
  return dryPowder;
}

// ── API → v5-shape adapters ──────────────────────────────────────
// The v5 reserves page is built around a hardcoded `DEPLOYMENTS` array
// whose entries carry every field the page needs (name, lng/lat, status,
// label, value, optional buildings). Our API exposes Projects, Metrics,
// and BuildingPlanRecords in different shapes — the adapters below project
// our real data INTO that v5 shape so the v5 view code can keep working
// byte-identical.

// 3-letter ISO country codes used by v5 STATUS_COLORS / CITY_LOCATIONS keys.
// Map from the human-readable country names we store in `project.country`.
const COUNTRY_TO_REGION: Record<string, string> = {
  'United States': 'USA', 'USA': 'USA', 'US': 'USA',
  'Mexico': 'MEX',
  'Brazil': 'BRA',
  'United Kingdom': 'GBR', 'UK': 'GBR',
  'Germany': 'DEU',
  'Nigeria': 'NGA',
  'India': 'IND',
  'Philippines': 'PHL',
  'Japan': 'JPN',
  'Singapore': 'SGP',
  'Latvia': 'LVA',
};

// Fallback 3-letter region code for countries not in the map above. We pick
// the first three letters of the country name (uppercased) — close enough to
// an ISO alpha-3 to read as a region badge without needing a full ISO table.
function regionCodeFor(country: string | null | undefined): string {
  if (!country) return '—';
  const known = COUNTRY_TO_REGION[country];
  if (known) return known;
  const letters = country.replace(/[^A-Za-z]/g, '');
  return (letters.slice(0, 3) || '—').toUpperCase();
}

// project.status (DB enum) → v5 deployment status bucket.
function bucketFromApiStatus(s: string): 'active' | 'upcoming' | 'diligence' | null {
  if (s === 'ACTIVE') return 'active';
  if (s === 'CONTRACT_SIGNED' || s === 'EQUIPMENT_PROCUREMENT' || s === 'NETWORK_ACTIVATION') {
    return 'upcoming';
  }
  if (s === 'DUE_DILIGENCE') return 'diligence';
  return null; // DRAFT etc — skip
}

// project.types[0] → human-readable strategy label used in v5 deployment.label.
const PROJECT_TYPE_LABEL: Record<string, string> = {
  ISP_ACQUISITION: 'Acquisition',
  INTERNET_BUILD_OUT: 'Deployment',
  CARRIER_OFFLOAD: 'Cellular',
  FIBER_DEPLOYMENT: 'Fiber',
  TOWER_BUILD: 'Backbone',
  EDGE_INFRASTRUCTURE: 'Edge',
};

// project.types[0] → v5 STRATEGY_CHIP category name. v5 only ships chip
// styles for three categories; map ours into them so the chips + filter
// bar at the top of the tables render correctly.
const PROJECT_TYPE_TO_STRATEGY: Record<string, string> = {
  ISP_ACQUISITION: 'Acquisitions',
  INTERNET_BUILD_OUT: 'Apartment Buildings',
  CARRIER_OFFLOAD: 'Carrier Offload',
  FIBER_DEPLOYMENT: 'Apartment Buildings',
  TOWER_BUILD: 'Carrier Offload',
  EDGE_INFRASTRUCTURE: 'Apartment Buildings',
};

// Deterministic gradient mark for the active-table row "monogram" cell.
// v5 hand-picked these per project; we derive from strategy so different
// projects of the same strategy still pop visually.
const STRATEGY_MARK: Record<string, { grad: string; fg: string }> = {
  'Apartment Buildings': { grad: 'linear-gradient(135deg, #5BA8E6, #1F6FBE)', fg: '#031224' },
  'Carrier Offload':     { grad: 'linear-gradient(135deg, #B26FFF, #6B2EAB)', fg: '#180935' },
  'Acquisitions':        { grad: 'linear-gradient(135deg, #F3A24A, #EA5270)', fg: '#1A0A0A' },
};

// project.status (DB enum) → v5 upcoming-table phase label + step (1..4).
const STATUS_PROGRESS_V5: Record<string, { step: number; label: string }> = {
  CONTRACT_SIGNED:       { step: 1, label: 'Contract signed' },
  DUE_DILIGENCE:         { step: 2, label: 'Due diligence' },
  EQUIPMENT_PROCUREMENT: { step: 3, label: 'Equipment procurement' },
  NETWORK_ACTIVATION:    { step: 4, label: 'Network activated' },
};

// Render a date string like "Q4 2029" from an ISO launch_date.
function formatQuarter(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return '';
  const q = Math.ceil((d.getMonth() + 1) / 3);
  return `Q${q} ${d.getFullYear()}`;
}

// Tokenize a string into lowercase search terms (used by v5's matchesQuery).
function tokensFor(p: Project): string[] {
  const parts = [p.name, p.city, p.state, p.country].filter(Boolean) as string[];
  return parts.flatMap((s) => s.toLowerCase().split(/\s+/));
}

// Build the v5 active-table row shape from a real Project + metrics + buildings.
function toActiveTableRow(
  p: Project,
  metrics: ProjectMetrics | undefined,
  totalDeployedDollars: number,
  buildingCount: number,
): any {
  const strategy = PROJECT_TYPE_TO_STRATEGY[p.types[0] ?? ''] ?? 'Apartment Buildings';
  const region = regionCodeFor(p.country);
  const deployedK = metrics && metrics.deployed_value > 0 ? metrics.deployed_value / 1000 : 0;
  const apyPct = metrics && metrics.yield_rate > 0 ? metrics.yield_rate * 100 : 0;
  const share =
    metrics && metrics.deployed_value > 0 && totalDeployedDollars > 0
      ? (metrics.deployed_value / totalDeployedDollars) * 100
      : 0;
  const mark = STRATEGY_MARK[strategy] ?? STRATEGY_MARK['Apartment Buildings'];
  const tag = buildingCount > 0
    ? { label: `${buildingCount} BUILDING${buildingCount === 1 ? '' : 'S'}`, color: '#5BA8E6' }
    : undefined;
  return {
    name: p.name,
    region,
    strategy,
    deployed: deployedK,
    apy: apyPct,
    share,
    blurb: p.description || '',
    mark: { letter: (p.name?.[0] ?? '?').toUpperCase(), grad: mark.grad, fg: mark.fg },
    ...(tag ? { tag } : {}),
    searchTokens: tokensFor(p),
  };
}

// Build the v5 upcoming-table row shape.
function toUpcomingTableRow(
  p: Project,
  metrics: ProjectMetrics | undefined,
  totalReservedDollars: number,
): any {
  const strategy = PROJECT_TYPE_TO_STRATEGY[p.types[0] ?? ''] ?? 'Apartment Buildings';
  const region = regionCodeFor(p.country);
  const reservedK = metrics && metrics.deployed_value > 0 ? metrics.deployed_value / 1000 : 0;
  const share =
    metrics && metrics.deployed_value > 0 && totalReservedDollars > 0
      ? (metrics.deployed_value / totalReservedDollars) * 100
      : 0;
  const progress = STATUS_PROGRESS_V5[p.status] ?? { step: 1, label: 'Contract signed' };
  return {
    name: p.name,
    region,
    strategy,
    reserved: reservedK,
    live: formatQuarter(p.launch_date),
    share,
    phase: progress.label,
    phaseStep: progress.step,
    searchTokens: tokensFor(p),
  };
}

// Translate a BuildingPlanRecord → v5 building shape consumed by
// AssetVisualizerPanel and BuildingsListPanel: {id, name, address, units,
// floors, accessType, mdfPlacement, subscribers, uptime}.
function toV5Building(b: BuildingPlanRecord): any {
  const plan = b.plan as { _rendered?: any } | null;
  const r = plan?._rendered;
  // v5 expects 'gpon' | 'ethernet' | 'coax' | 'hallway'. Our schema uses
  // 'hallway-wifi' for the hallway variant — translate at the boundary.
  const accessTechRaw = r?.distribution?.accessTech ?? 'ethernet';
  const accessType = accessTechRaw === 'hallway-wifi' ? 'hallway' : accessTechRaw;
  return {
    id: b.id,
    name: b.name,
    address: r?.building?.city ?? '—',
    units: r?.geometry?.floorCount ?? 0,
    floors: r?.geometry?.floorCount ?? 0,
    accessType,
    mdfPlacement: r?.infra?.mdf?.placement ?? 'basement',
    subscribers: r?.building?.metadata?.subscribers ?? 0,
    uptime: b.uptime ?? '99.96%',
    // Full renderer snapshot — the asset visualizer reads geometry/infra
    // from this to drive the 3D model with the manager-entered values.
    plan: r ?? null,
  };
}

// Build the v5-shape deployment array from real Projects.
function projectsToDeployments(
  projects: Project[],
  metricsById: Map<string, ProjectMetrics>,
  buildingsByProject: Record<string, BuildingPlanRecord[]>,
  coordsByLocation: Record<string, GeoCoords | null>,
): any[] {
  const out: any[] = [];
  for (const p of projects) {
    const status = bucketFromApiStatus(p.status);
    if (!status) continue;
    // Projects whose city+country hasn't geocoded yet (or returned no result)
    // are still kept so the tables can select them — DeploymentGlobe filters
    // non-finite coords (project() → NaN → vis=false) so they just don't
    // render as pins on the map.
    const region = regionCodeFor(p.country);
    const strategy = PROJECT_TYPE_LABEL[p.types[0] ?? ''] ?? 'Deployment';
    const labelTail =
      status === 'active' ? 'Active'
      : status === 'upcoming' ? 'Upcoming'
      : 'diligence';
    const m = metricsById.get(p.id);
    // v5 stores `value` in $K. Our metrics.deployed_value is dollars.
    const valueK = m && m.deployed_value > 0 ? m.deployed_value / 1000 : 0;
    // City key: v5 uses CamelCase like "GreatFalls"; project.city is already
    // human-readable. Keep the human form — locationLabel() handles the
    // pretty-print downstream.
    const city = p.city ?? '';
    const apiBuildings = buildingsByProject[p.id] ?? [];
    // Coords come from the Nominatim geocode cache (city+country lookup).
    // NaN signals "no coords" — null would coerce to 0 in the globe's
    // project() math and place a phantom pin at (0,0).
    const coords = p.city && p.country
      ? coordsByLocation[geocodeKey(p.city, p.country)]
      : null;
    out.push({
      id: p.id,
      name: p.name,
      city,
      region,
      // Full human-readable country name (e.g., "Latvia"). `locationLabel`
      // prefers this over the 3-letter region code when present.
      country: p.country ?? null,
      // Carried through for locationLabel ("State · Country"); city is omitted
      // from the label but still drives geocoding above.
      state: p.state ?? null,
      lng: coords?.lng ?? Number.NaN,
      lat: coords?.lat ?? Number.NaN,
      label: `${strategy} · ${labelTail}`,
      value: valueK,
      status,
      // Only attach the buildings field when we actually have buildings —
      // v5 uses `Array.isArray(pin.buildings) && pin.buildings.length > 0`
      // to decide whether to show the "View buildings" button.
      ...(apiBuildings.length > 0 ? { buildings: apiBuildings.map(toV5Building) } : {}),
    });
  }
  return out;
}

// ── Overview / detail panel content ─────────────────────────────
// The left panel reuses one card and swaps content between an aggregate
// "overview" view and a single-project "detail" view based on selection.
// Each component is keyed at the call site so a fresh mount runs the
// fade-in animation, giving a sense of continuity from the map.

// Instructional panel shown in the globe section's left card when no
// deployment is selected. The page-level hero/stats/portfolio now live
// above the table, so this panel focuses on guiding the user into the map.
const INSPECT_STEPS = [
  "Click a row in the table",
  "Map highlights the project",
  "View buildings & topology",
];

function InspectPanel() {
  return (
    <div className="reserves-panel-fade" style={{ display: "flex", flexDirection: "column", gap: 22, height: "100%", justifyContent: "center" }}>
      <div className="kicker" style={{ color: "var(--fg-3)" }}>Map · Project explorer</div>
      <h2 className="h-display" style={{ fontSize: 36, margin: 0, lineHeight: 1.04, letterSpacing: "-0.03em" }}>
        Click a row to inspect <br />the deployment.
      </h2>
      <p style={{ fontSize: 13, color: "var(--fg-2)", lineHeight: 1.6, margin: 0, maxWidth: 360 }}>
        Pick any project from the table above. The map will fly to its location and the building list will appear here — click any building to drill into its network topology.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 4 }}>
        {INSPECT_STEPS.map((s, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{
              width: 24, height: 24, borderRadius: "50%", flexShrink: 0,
              border: "1px solid var(--line-strong)",
              display: "inline-flex", alignItems: "center", justifyContent: "center",
              fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--fg-3)",
            }}>{i + 1}</span>
            <span style={{ fontSize: 13, color: "var(--fg-2)" }}>{s}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Empty-table illustration — folder with a "no entry" mark, used by both
// the Active and Upcoming tables when filters exclude every row.
function EmptyDeployments({ compact = false }: { compact?: boolean }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, padding: compact ? "28px 12px" : "56px 12px" }}>
      <svg width="54" height="54" viewBox="0 0 54 54" fill="none" aria-hidden="true">
        <path d="M7 16.5C7 14.6 8.6 13 10.5 13H21l4 4h18.5C45.4 17 47 18.6 47 20.5V40c0 1.9-1.6 3.5-3.5 3.5h-33C8.6 43.5 7 41.9 7 40V16.5Z"
          fill="rgba(255,255,255,0.03)" stroke="var(--line-strong)" strokeWidth="1.3" />
        <circle cx="27" cy="30" r="7.5" stroke="var(--dawn-amber)" strokeWidth="1.4" />
        <line x1="22" y1="35" x2="32" y2="25" stroke="var(--dawn-amber)" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
      <div style={{ fontSize: 14, color: "var(--fg-2)", fontWeight: 500 }}>No matching deployments</div>
      <div style={{ fontSize: 12, color: "var(--fg-4)" }}>Try another region, strategy, or status.</div>
    </div>
  );
}

// Deployment-table column template — widths chosen so the Strategy / value /
// APY / Share column centers land on the Figma positions within the panel.
// Shared by both the Active and Upcoming tables so the header does not shift
// position when switching tabs.
const TABLE_COLS = "minmax(0,1fr) 186px 238px 78px 178px";

// Table head cell (Figma: Inter Medium 10.3px, ink-60, wide tracking).
function HeadCell({ label, onClick }: { label: string; onClick?: () => void }) {
  return (
    <div
      onClick={onClick}
      style={{
        textAlign: "center", fontFamily: "var(--font-sans)", fontSize: 10.324, fontWeight: 500,
        letterSpacing: "1.4454px", color: "#8C8A85", cursor: onClick ? "pointer" : "default", userSelect: "none",
      }}
    >
      {label}
    </div>
  );
}

function DeploymentHeadCell({ label }: { label: string }) {
  return (
    <div style={{
      paddingLeft: 40, textAlign: "left", fontFamily: "var(--font-sans)", fontSize: 10.324, fontWeight: 500,
      letterSpacing: "1.4454px", color: "#8C8A85", userSelect: "none",
    }}>
      {label}
    </div>
  );
}

function ProjectDetailPanel({ pin, onClose, onViewBuildings, view, onBackToGlobe, selectedBuilding, onBackToBuildings }: any) {
  const color = STATUS_COLORS[pin.status];
  const statusLabel = pin.status === "active" ? "ACTIVE · LIVE" : pin.status === "upcoming" ? "UPCOMING · RESERVED" : "DILIGENCE";
  // Pull strategy out of the label string ("Strategy · Note")
  const [strategy, ...noteParts] = (pin.label || "").split(" · ");
  const note = noteParts.join(" · ");
  // Color the strategy headline by category, matching the portfolio palette.
  const STRATEGY_COLORS: any = {
    "Acquisition": "#C73E7C",
    "Cellular": "#EA5270",
    "5G mesh": "#EA5270",
    "Fixed wireless": "#EA5270",
    "Fiber": "#F3A24A",
    "FTTP": "#F3A24A",
    "Deployment": "#F3A24A",
    "Build-Out": "#F3A24A",
    "Backbone": "#7BD9FF",
    "Backhaul": "#7BD9FF",
    "Backhaul partner": "#7BD9FF",
    "Edge compute": "#A8E063",
  };
  const strategyColor = STRATEGY_COLORS[strategy] || color;
  // Fake but plausible derived metrics for the demo
  const apy = pin.status === "active" ? "8.5%" : "—";
  const share = ((pin.value / 37.5) * 100).toFixed(1) + "%";
  const subs = pin.status === "active" ? "2,140" : "—";
  const nodes = pin.status === "active" ? "1,418" : "—";
  const hasBuildings = Array.isArray(pin.buildings) && pin.buildings.length > 0;
  const isGlobe = view === "globe" || !view;
  return (
    <div className="reserves-panel-fade" style={{ display: "flex", flexDirection: "column", gap: 18, height: "100%" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 8, minWidth: 0 }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: color, boxShadow: `0 0 10px ${color}` }} />
            <span className="kicker" style={{ color: "var(--fg-3)", letterSpacing: "0.18em" }}>{statusLabel}</span>
          </div>
          <h1 className="h-display" style={{ fontSize: 34, margin: 0, lineHeight: 1.05, letterSpacing: "-0.02em" }}>{pin.name}</h1>
          <div className="mono" style={{ fontSize: 11, color: "var(--fg-3)", letterSpacing: "0.06em" }}>
            {locationLabel(pin)}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flex: "0 0 auto" }}>
          {isGlobe && hasBuildings && (
            <button onClick={onViewBuildings} style={{
              display: "inline-flex", alignItems: "center", gap: 8,
              padding: "8px 14px", borderRadius: 999,
              background: `linear-gradient(90deg, ${color}26, ${color}14)`,
              border: `1px solid ${color}80`,
              color: color,
              fontFamily: "var(--font-sans)", fontSize: 12, fontWeight: 500,
              letterSpacing: "-0.005em", cursor: "pointer",
              boxShadow: `0 0 24px -8px ${color}99`,
            }}>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                <rect x="2" y="4.5" width="3" height="6" stroke="currentColor" strokeWidth="1.1" fill="none" />
                <rect x="5.5" y="2" width="4.5" height="8.5" stroke="currentColor" strokeWidth="1.1" fill="none" />
                <line x1="7" y1="4.5" x2="8.5" y2="4.5" stroke="currentColor" strokeWidth="0.9" />
                <line x1="7" y1="6.5" x2="8.5" y2="6.5" stroke="currentColor" strokeWidth="0.9" />
                <line x1="7" y1="8.5" x2="8.5" y2="8.5" stroke="currentColor" strokeWidth="0.9" />
              </svg>
              View buildings
              <span style={{ opacity: 0.7 }}>→</span>
            </button>
          )}
          {!isGlobe && (
            <button onClick={onBackToGlobe} style={{
              display: "inline-flex", alignItems: "center", gap: 6,
              padding: "8px 12px", borderRadius: 8,
              background: "transparent",
              border: "1px solid var(--line)",
              color: "var(--fg-2)",
              fontFamily: "var(--font-sans)", fontSize: 12, fontWeight: 500,
              letterSpacing: "-0.005em", cursor: "pointer",
            }}>
              <span style={{ opacity: 0.7 }}>←</span>
              Back to map
            </button>
          )}
          <button onClick={onClose} aria-label="Close detail" style={{
            width: 28, height: 28, borderRadius: 8,
            background: "transparent", border: "1px solid var(--line)",
            color: "var(--fg-3)", cursor: "pointer",
            fontFamily: "var(--font-mono)", fontSize: 14, lineHeight: 1,
          }}>×</button>
        </div>
      </div>

      {/* Money grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 0, borderTop: "1px solid var(--line)", borderBottom: "1px solid var(--line)" }}>
        {[
          { v: formatDeployedValue(pin.value), l: pin.status === "active" ? "Deployed" : "Reserved" },
          { v: apy, l: "APY" },
          { v: share, l: "Pool Share" },
        ].map((s, i) => (
          <div key={i} style={{ padding: "16px 14px", borderRight: i < 2 ? "1px solid var(--line)" : "none" }}>
            <div className="tabular" style={{ fontFamily: "var(--font-display)", fontSize: 22, fontWeight: 500, letterSpacing: "-0.025em", marginBottom: 4 }}>{s.v}</div>
            <div className="kicker" style={{ fontSize: 9 }}>{s.l}</div>
          </div>
        ))}
      </div>

      {/* Strategy headline — colored by asset type */}
      <div style={{
        fontFamily: "var(--font-display)",
        fontSize: 26, fontWeight: 500, letterSpacing: "-0.02em",
        color: strategyColor, textTransform: "none",
      }}>{strategy}</div>

      {/* Operational metrics — only for active */}
      {pin.status === "active" && (
        <div className="card-flat" style={{ padding: 14 }}>
          <div className="kicker" style={{ marginBottom: 10 }}>Operational metrics</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 14 }}>
            <div>
              <div className="tabular" style={{ fontFamily: "var(--font-display)", fontSize: 16, fontWeight: 500 }}>10 Gbps</div>
              <div className="kicker" style={{ fontSize: 9 }}>Backhaul capacity</div>
            </div>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                  <circle cx="8" cy="8" r="7" fill="var(--pos)" fillOpacity="0.18" stroke="var(--pos)" strokeWidth="1.2" />
                  <path d="M4.5 8.2 L7 10.5 L11.5 5.8" stroke="var(--pos)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" fill="none" />
                </svg>
                <span className="tabular" style={{ fontFamily: "var(--font-display)", fontSize: 14, fontWeight: 500, color: "var(--fg)" }}>Enabled</span>
              </div>
              <div className="kicker" style={{ fontSize: 9, marginTop: 2 }}>DAWN open access wireless</div>
            </div>
            <div>
              <div className="tabular" style={{ fontFamily: "var(--font-display)", fontSize: 16, fontWeight: 500, color: "var(--pos)" }}>${(pin.value * 0.78).toFixed(1)}K</div>
              <div className="kicker" style={{ fontSize: 9 }}>30D revenue</div>
            </div>
            <div>
              <div className="tabular" style={{ fontFamily: "var(--font-display)", fontSize: 16, fontWeight: 500 }}>99.97%</div>
              <div className="kicker" style={{ fontSize: 9 }}>Uptime</div>
            </div>
          </div>
        </div>
      )}

      {/* Spacer — pushes timeline toward bottom of card */}
      <div style={{ marginTop: "auto" }} />

      {/* Timeline */}
      <div>
        <div className="kicker" style={{ marginBottom: 10 }}>Timeline</div>
        <div style={{ display: "flex", gap: 6 }}>
          {[
            { label: "Sourced", done: true },
            { label: "Diligence", done: pin.status !== "diligence" },
            { label: "Reserved", done: pin.status === "active" || pin.status === "upcoming" },
            { label: "Deployed", done: pin.status === "active" },
            { label: "Yielding", done: pin.status === "active" },
          ].map((s, i, arr) => (
            <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ height: 3, background: s.done ? color : "var(--line-strong)", borderRadius: 2 }} />
              <div className="mono" style={{ fontSize: 9, color: s.done ? "var(--fg-2)" : "var(--fg-4)", letterSpacing: "0.06em" }}>{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Footer / spacer below timeline (matches top spacer to center it) */}
      <div style={{ marginTop: "auto" }} />
    </div>
  );
}

// ============================================================
// Mobile project detail bottom-sheet (Figma 6676-76398). Replaces the
// inline left detail card on small screens — clicking a deployment row or
// a globe pin slides this sheet up from the bottom. Mirrors the derived
// metrics of ProjectDetailPanel and embeds the live-network globe (focused
// on the selected pin) as the map at the foot of the sheet.
// ============================================================
const STRATEGY_BADGE_COLORS: { match: RegExp; color: string }[] = [
  { match: /carrier|offload/i, color: "#7BDC8D" },
  { match: /apartment/i, color: "#7DD1FF" },
  { match: /backhaul|backbone/i, color: "#7BD9FF" },
  { match: /cellular|wireless|mesh/i, color: "#EA5270" },
  { match: /acquisition/i, color: "#C73E7C" },
  { match: /fiber|fttp|deployment|build/i, color: "#F3A24A" },
];
function strategyBadgeColor(strategy: string, fallback: string): string {
  return STRATEGY_BADGE_COLORS.find((s) => s.match.test(strategy))?.color ?? fallback;
}

function MobileProjectSheet({ pin, onClose }: any) {
  const [closing, setClosing] = useState(false);
  // Buildings drill-down. The globe/map is intentionally omitted on mobile;
  // the sheet instead offers a direct path into the buildings → asset views.
  const [view, setView] = useState<"detail" | "buildings" | "asset">("detail");
  const [selBuilding, setSelBuilding] = useState<any>(null);
  const hasBuildings = Array.isArray(pin.buildings) && pin.buildings.length > 0;

  const color = STATUS_COLORS[pin.status];
  const [strategy] = (pin.label || "").split(" · ");
  const badgeColor = strategyBadgeColor(strategy, color);
  const apy = pin.status === "active" ? "8.5%" : "—";
  const share = ((pin.value / 37.5) * 100).toFixed(1) + "%";
  const valueLabel = pin.status === "active" ? "Deployed" : "Reserved";

  // Lock background scroll while the sheet is open.
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, []);

  function requestClose() {
    setClosing(true);
    setTimeout(onClose, 260);
  }

  const divider = <div style={{ height: 1, background: "var(--line)", width: "100%" }} />;

  return createPortal(
    <div style={{ position: "fixed", inset: 0, zIndex: 1000, display: "flex", flexDirection: "column", justifyContent: "flex-end" }}>
      <div
        onClick={requestClose}
        className={closing ? "reserves-sheet-backdrop-out" : "reserves-sheet-backdrop"}
        style={{ position: "absolute", inset: 0, background: "rgba(18,18,18,0.35)", backdropFilter: "blur(5px)", WebkitBackdropFilter: "blur(5px)" }}
      />
      <div
        className={closing ? "reserves-sheet-panel-out" : "reserves-sheet-panel"}
        style={{
          position: "relative", background: "#13151A", borderTopLeftRadius: 20, borderTopRightRadius: 20,
          padding: "12px 20px 24px", maxHeight: "88vh", overflowY: "auto",
          display: "flex", flexDirection: "column", gap: 23, alignItems: "center",
        }}
      >
        {/* Drag handle */}
        <div style={{ width: 40, height: 4, borderRadius: 2, background: "rgba(255,255,255,0.18)", flexShrink: 0 }} />

        <div style={{ display: "flex", flexDirection: "column", gap: 25, width: "100%" }}>
          {/* Header — name + close, location, strategy badge */}
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                <span style={{ fontFamily: "var(--font-sans)", fontSize: 22, fontWeight: 700, letterSpacing: "-0.3px", color: "#FBF7F3", lineHeight: "28.5px" }}>{pin.name}</span>
                <button onClick={requestClose} aria-label="Close detail" style={{
                  width: 27, height: 25, display: "inline-flex", alignItems: "center", justifyContent: "center",
                  background: "transparent", border: "none", color: "#8C8A84", cursor: "pointer",
                  fontFamily: "var(--font-mono)", fontSize: 22, lineHeight: 1, flexShrink: 0,
                }}>×</button>
              </div>
              <span style={{ fontFamily: "var(--font-sans)", fontSize: 14, color: "#8C8A84", lineHeight: "23.1px" }}>{locationLabel(pin)}</span>
            </div>
            <span style={{
              display: "inline-flex", alignSelf: "flex-start", alignItems: "center", justifyContent: "center",
              fontFamily: "var(--font-sans)", fontSize: 9, fontWeight: 400, lineHeight: "14.08px",
              padding: "3px 12px", borderRadius: 7.04,
              background: `${badgeColor}0a`, border: `0.575px solid ${badgeColor}33`, color: badgeColor, whiteSpace: "nowrap",
            }}>{strategy}</span>
          </div>

          {/* Stats — Deployed / APY / Pool share */}
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            {divider}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
              {[
                { l: valueLabel, v: formatDeployedValue(pin.value) },
                { l: "APY", v: apy },
                { l: "Pool share", v: share },
              ].map((s) => (
                <div key={s.l} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <span style={{ fontFamily: "var(--font-sans)", fontSize: 12, color: "#8C8A84", opacity: 0.5, lineHeight: "15px" }}>{s.l}</span>
                  <span className="tabular" style={{ fontFamily: "var(--font-sans)", fontSize: 16, fontWeight: 500, color: "#FBF7F3", lineHeight: "15px" }}>{s.v}</span>
                </div>
              ))}
            </div>
            {divider}
          </div>

          {/* Backhaul partner — operational metrics (active only) */}
          {pin.status === "active" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
              <span style={{ fontFamily: "var(--font-sans)", fontSize: 16, fontWeight: 500, letterSpacing: "-0.3px", color: "#FBF7F3", lineHeight: "28.5px" }}>Backhaul partner</span>
              <div className="card-flat" style={{ padding: 14, borderRadius: 10 }}>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 14 }}>
                  <div>
                    <div className="tabular" style={{ fontFamily: "var(--font-display)", fontSize: 16, fontWeight: 500 }}>10 Gbps</div>
                    <div className="kicker" style={{ fontSize: 9 }}>Backhaul capacity</div>
                  </div>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                        <circle cx="8" cy="8" r="7" fill="var(--pos)" fillOpacity="0.18" stroke="var(--pos)" strokeWidth="1.2" />
                        <path d="M4.5 8.2 L7 10.5 L11.5 5.8" stroke="var(--pos)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" fill="none" />
                      </svg>
                      <span className="tabular" style={{ fontFamily: "var(--font-display)", fontSize: 14, fontWeight: 500, color: "var(--fg)" }}>Enabled</span>
                    </div>
                    <div className="kicker" style={{ fontSize: 9, marginTop: 2 }}>DAWN open access wireless</div>
                  </div>
                  <div>
                    <div className="tabular" style={{ fontFamily: "var(--font-display)", fontSize: 16, fontWeight: 500, color: "var(--pos)" }}>${(pin.value * 0.78).toFixed(1)}K</div>
                    <div className="kicker" style={{ fontSize: 9 }}>30D revenue</div>
                  </div>
                  <div>
                    <div className="tabular" style={{ fontFamily: "var(--font-display)", fontSize: 16, fontWeight: 500 }}>99.97%</div>
                    <div className="kicker" style={{ fontSize: 9 }}>Uptime</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Timeline */}
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <span style={{ fontFamily: "var(--font-sans)", fontSize: 11, color: "#8C8A84", letterSpacing: "0.04em" }}>Timeline</span>
            <div style={{ display: "flex", gap: 6 }}>
              {[
                { label: "Sourced", done: true },
                { label: "Diligence", done: pin.status !== "diligence" },
                { label: "Reserved", done: pin.status === "active" || pin.status === "upcoming" },
                { label: "Deployed", done: pin.status === "active" },
                { label: "Yielding", done: pin.status === "active" },
              ].map((s, i) => (
                <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", gap: 6, minWidth: 0 }}>
                  <div style={{ height: 3, borderRadius: 1, background: s.done ? color : "var(--line-strong)" }} />
                  <span className="mono" style={{ fontSize: 9, color: s.done ? "var(--fg-2)" : "var(--fg-4)", letterSpacing: "0.04em" }}>{s.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Buildings drill-down — the globe/map is omitted on mobile; the
              sheet exposes a direct "View buildings" → asset path instead. */}
          {(hasBuildings || view !== "detail") && (
            <div style={{ display: "flex", flexDirection: "column", gap: 10, width: "100%" }}>
              {view === "detail" ? (
                hasBuildings && (
                  <button onClick={() => setView("buildings")} style={{
                    display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8, width: "100%",
                    padding: "12px 14px", borderRadius: 10,
                    background: `linear-gradient(90deg, ${color}26, ${color}14)`,
                    border: `1px solid ${color}80`,
                    color: color,
                    fontFamily: "var(--font-sans)", fontSize: 13, fontWeight: 500,
                    letterSpacing: "-0.005em", cursor: "pointer",
                    boxShadow: `0 0 24px -8px ${color}99`,
                  }}>
                    <svg width="13" height="13" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                      <rect x="2" y="4.5" width="3" height="6" stroke="currentColor" strokeWidth="1.1" fill="none" />
                      <rect x="5.5" y="2" width="4.5" height="8.5" stroke="currentColor" strokeWidth="1.1" fill="none" />
                      <line x1="7" y1="4.5" x2="8.5" y2="4.5" stroke="currentColor" strokeWidth="0.9" />
                      <line x1="7" y1="6.5" x2="8.5" y2="6.5" stroke="currentColor" strokeWidth="0.9" />
                      <line x1="7" y1="8.5" x2="8.5" y2="8.5" stroke="currentColor" strokeWidth="0.9" />
                    </svg>
                    View buildings
                    <span style={{ opacity: 0.7 }}>→</span>
                  </button>
                )
              ) : (
                <>
                  {/* Back navigation */}
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, minHeight: 32 }}>
                    <span style={{ fontFamily: "var(--font-sans)", fontSize: 11, color: "#8C8A84", letterSpacing: "0.04em", minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {view === "buildings" ? `Buildings · ${pin.buildings.length}` : selBuilding?.name}
                    </span>
                    <button
                      onClick={() => {
                        if (view === "asset") { setView("buildings"); setSelBuilding(null); }
                        else { setView("detail"); }
                      }}
                      style={{
                        display: "inline-flex", alignItems: "center", gap: 6, flexShrink: 0,
                        padding: "8px 12px", borderRadius: 8,
                        background: "transparent", border: "1px solid var(--line)",
                        color: "var(--fg-2)",
                        fontFamily: "var(--font-sans)", fontSize: 12, fontWeight: 500,
                        letterSpacing: "-0.005em", cursor: "pointer",
                      }}>
                      <span style={{ opacity: 0.7 }}>←</span>
                      {view === "asset" ? "Buildings" : "Back"}
                    </button>
                  </div>

                  {view === "buildings" && (
                    <div style={{ position: "relative", width: "100%", height: "60vh", maxHeight: 460 }}>
                      <BuildingsListPanel
                        pin={pin}
                        onSelectBuilding={(b: any) => { setSelBuilding(b); setView("asset"); }}
                        mobile
                      />
                    </div>
                  )}
                  {view === "asset" && selBuilding && (
                    <div style={{ position: "relative", width: "100%", height: "70vh", maxHeight: 560, borderRadius: 6, border: "1px solid var(--line)", overflow: "hidden" }}>
                      <AssetVisualizerPanel
                        building={selBuilding}
                        pin={pin}
                        onBack={() => { setView("buildings"); setSelBuilding(null); }}
                        compact
                      />
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}

// ============================================================
// Buildings list — shown in place of the globe when user clicks
// "View N buildings" on a deployment that has a `buildings` array.
// Each row drills into the asset visualizer for that building.
// ============================================================
function BuildingsListPanel({ pin, onSelectBuilding, liftingId: extLiftingId, outgoing, mobile }: any) {
  const buildings = pin.buildings || [];
  const accent = STATUS_COLORS[pin.status];
  const [internalLiftingId, setLiftingId] = useState<any>(null);
  const liftingId = extLiftingId !== undefined && extLiftingId !== null ? extLiftingId : internalLiftingId;
  const containerRef = useRef<any>(null);

  function handleRowClick(e: any, b: any) {
    setLiftingId(b.id);
    // Capture the row's viewport rect (for the FLIP morph into the asset
    // panel) and pass it up.
    const rowEl = e.currentTarget;
    if (rowEl) {
      const r = rowEl.getBoundingClientRect();
      onSelectBuilding(b, { left: r.left, top: r.top, width: r.width, height: r.height });
    } else {
      onSelectBuilding(b, null);
    }
  }

  // Per-building derived display values, shared by the desktop table rows and
  // the mobile cards so the two layouts stay in lockstep.
  function buildingMeta(b: any) {
    const t = lookupAccessSpec(b.accessType);
    const isFWA = b.mdfPlacement === "roof";
    const backhaul = ({
      gpon: "10 Gbps", ethernet: "10 Gbps", coax: "2.5 Gbps", hallway: "1 Gbps",
    } as any)[b.accessType] || "—";
    const idHash = (b.id || "").split("").reduce((s: number, c: string) => s + c.charCodeAt(0), 0);
    return {
      accessColor: t?.color || "var(--fg-3)",
      accessShort: t?.short || b.accessType,
      poeLabel: isFWA ? "Fixed Wireless" : "Fiber",
      poeColor: isFWA ? "var(--dawn-violet)" : "var(--dawn-cyan)",
      backhaul,
      dawn: (idHash % 10) < 7,
    };
  }

  // ── Mobile: stacked cards instead of the 5-column table (which overflows
  // a phone-width sheet). Same data, same tap-to-open-asset behaviour. ──
  if (mobile) {
    return (
      <div ref={containerRef} className={`reserves-buildings-in${outgoing ? " reserves-buildings-out" : ""}`} style={{
        position: "relative", width: "100%", height: "100%",
        background: "var(--bg-2)", border: "1px solid var(--line)",
        borderRadius: 12, overflow: "hidden",
        display: "flex", flexDirection: "column",
      }}>
        <div style={{ flex: 1, overflowY: "auto", padding: 10, display: "flex", flexDirection: "column", gap: 8 }}>
          {buildings.map((b: any) => {
            const m = buildingMeta(b);
            return (
              <button key={b.id}
                onClick={(e) => handleRowClick(e, b)}
                className={liftingId === b.id ? "lifting" : ""}
                style={{
                  display: "flex", flexDirection: "column", gap: 10, width: "100%",
                  padding: "12px 13px", borderRadius: 10, textAlign: "left",
                  background: "rgba(255,255,255,0.02)", border: "1px solid var(--line)",
                  color: "var(--fg)", cursor: "pointer",
                }}>
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10 }}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontFamily: "var(--font-sans)", fontWeight: 600, fontSize: 14, color: "var(--fg)", lineHeight: 1.2 }}>{b.name}</div>
                    <div className="mono" style={{ fontSize: 10, color: "var(--fg-4)", letterSpacing: "0.04em", marginTop: 3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{b.address}</div>
                  </div>
                  <span style={{ flexShrink: 0, color: "var(--fg-4)", fontSize: 16, lineHeight: 1, marginTop: 2 }}>›</span>
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6 }}>
                  <span style={{
                    display: "inline-flex", alignItems: "center", gap: 5,
                    padding: "3px 8px", borderRadius: 4,
                    border: `1px solid ${m.accessColor}55`, background: `${m.accessColor}11`, color: m.accessColor,
                    fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.06em",
                  }}>
                    <span style={{ width: 5, height: 5, borderRadius: "50%", background: m.accessColor }} />
                    {m.accessShort}
                  </span>
                  <span style={{
                    padding: "3px 8px", borderRadius: 4,
                    fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.06em",
                    border: `1px solid ${m.poeColor}55`, background: `${m.poeColor}11`, color: m.poeColor,
                  }}>{m.poeLabel.toUpperCase()}</span>
                  <span className="tabular" style={{
                    padding: "3px 8px", borderRadius: 4,
                    fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.04em",
                    border: "1px solid var(--line)", color: "var(--fg-2)",
                  }}>{m.backhaul}</span>
                  {m.dawn && (
                    <span style={{
                      display: "inline-flex", alignItems: "center", gap: 4,
                      padding: "3px 8px", borderRadius: 4,
                      border: "1px solid rgba(120,220,140,0.4)", background: "rgba(120,220,140,0.12)", color: "#7BDC8C",
                      fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.06em",
                    }}>✓ DAWN</span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} className={`reserves-buildings-in${outgoing ? " reserves-buildings-out" : ""}`} style={{
      position: "relative", width: "100%", height: "100%",
      background: "var(--bg-2)", border: "1px solid var(--line)",
      borderRadius: 14, overflow: "hidden",
      display: "flex", flexDirection: "column",
    }}>
      {/* Header strip */}
      <div style={{
        padding: "16px 22px", borderBottom: "1px solid var(--line)",
        display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12,
        background: "var(--bg-2)",
      }}>
        <div>
          <div className="kicker" style={{ color: "var(--fg-3)", marginBottom: 4 }}>Buildings · {pin.name}</div>
          <div style={{ fontFamily: "var(--font-display)", fontSize: 18, fontWeight: 500, letterSpacing: "-0.015em" }}>
            {buildings.length} buildings
          </div>
        </div>
        <div style={{
          display: "inline-flex", alignItems: "center", gap: 8,
          padding: "8px 14px", borderRadius: 999,
          background: "linear-gradient(180deg, rgba(125,209,255,0.18), rgba(125,209,255,0.08))",
          border: "1px solid rgba(125,209,255,0.55)",
          color: "var(--dawn-cyan)",
          fontFamily: "var(--font-sans)", fontSize: 12, fontWeight: 600,
          letterSpacing: "0.01em",
          animation: "cta-pulse-glow 2.4s ease-in-out infinite",
        }}>
          Click a row to view the infrastructure
        </div>
      </div>

      {/* List */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        <table className="table" style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead style={{ position: "sticky", top: 0, background: "var(--bg-2)", zIndex: 1 }}>
            <tr>
              <th style={{ padding: "10px 22px", textAlign: "left" }}>Building</th>
              <th style={{ padding: "10px 12px", textAlign: "left" }}>Access</th>
              <th style={{ padding: "10px 12px", textAlign: "center" }} title="DAWN Open Access Wireless">DAWN</th>
              <th style={{ padding: "10px 12px", textAlign: "center" }}>Backhaul</th>
              <th style={{ padding: "10px 12px", textAlign: "center" }}>POE</th>
            </tr>
          </thead>
          <tbody>
            {buildings.map((b: any) => {
              const t = lookupAccessSpec(b.accessType);
              const tColor = t?.color || "var(--fg-3)";
              const tShort = t?.short || b.accessType;
              const isFWA = b.mdfPlacement === "roof";
              const poeLabel = isFWA ? "Fixed Wireless" : "Fiber";
              const poeColor = isFWA ? "var(--dawn-violet)" : "var(--dawn-cyan)";
              const backhaul = ({
                gpon: "10 Gbps",
                ethernet: "10 Gbps",
                coax: "2.5 Gbps",
                hallway: "1 Gbps",
              } as any)[b.accessType] || "—";
              // Deterministic DAWN flag from id hash — ~65% of buildings on DAWN.
              const idHash = (b.id || "").split("").reduce((s: number, c: string) => s + c.charCodeAt(0), 0);
              const dawn = (idHash % 10) < 7;
              return (
                <tr key={b.id}
                    className={`reserves-buildings-row${liftingId === b.id ? " lifting" : ""}`}
                    onClick={(e) => handleRowClick(e, b)}
                    style={{ cursor: "pointer" }}>
                  <td style={{ padding: "12px 22px" }}>
                    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                      <span style={{ color: "var(--fg)", fontWeight: 500, fontSize: 13 }}>{b.name}</span>
                      <span className="mono" style={{ fontSize: 10, color: "var(--fg-4)", letterSpacing: "0.04em" }}>{b.address}</span>
                    </div>
                  </td>
                  <td style={{ padding: "12px" }}>
                    <span style={{
                      display: "inline-flex", alignItems: "center", gap: 6,
                      padding: "3px 8px", borderRadius: 4,
                      border: `1px solid ${tColor}55`,
                      background: `${tColor}11`,
                      color: tColor,
                      fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.08em",
                    }}>
                      <span style={{ width: 5, height: 5, borderRadius: "50%", background: tColor }} />
                      {tShort}
                    </span>
                  </td>
                  <td style={{ padding: "12px", textAlign: "center" }}>
                    {dawn ? (
                      <span style={{
                        display: "inline-flex", alignItems: "center", justifyContent: "center",
                        width: 18, height: 18, borderRadius: "50%",
                        background: "rgba(120, 220, 140, 0.18)",
                        color: "#7BDC8C",
                        fontSize: 11, lineHeight: 1, fontWeight: 600,
                      }} aria-label="DAWN Open Access Wireless">✓</span>
                    ) : (
                      <span style={{ color: "var(--fg-4)", fontSize: 14, lineHeight: 1 }} aria-label="Not on DAWN">—</span>
                    )}
                  </td>
                  <td className="tabular" style={{ padding: "12px", textAlign: "center", color: "var(--fg-2)", fontSize: 12 }}>{backhaul}</td>
                  <td style={{
                    padding: "12px", textAlign: "center",
                    fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.08em",
                    color: poeColor,
                  }}>
                    {poeLabel.toUpperCase()}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============================================================
// Slim context strip shown above the full-width asset visualizer.
// Replaces the left ProjectDetailPanel when in asset view — keeps
// the project context discoverable in one row, with crumb-style
// navigation to drill back up to the buildings list or the map.
// ============================================================
function ProjectAssetContextStrip({ pin, building, onBackToBuildings, onBackToGlobe, onClose }: any) {
  if (!pin || !building) return null;
  const color = STATUS_COLORS[pin.status];
  const t = lookupAccessSpec(building.accessType);
  return (
    <div className="card-strong" style={{
      padding: "14px 22px",
      display: "flex", alignItems: "center", gap: 18,
      borderTop: `2px solid ${color}`,
    }}>
      {/* Crumb */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0, flex: 1 }}>
        <button onClick={onBackToGlobe} style={{
          background: "transparent", border: "none", padding: 0, cursor: "pointer",
          fontFamily: "var(--font-sans)", fontSize: 13, fontWeight: 500,
          color: "var(--fg-2)", letterSpacing: "-0.005em",
        }}>{pin.name}</button>
        <span style={{ color: "var(--fg-4)", fontSize: 11 }}>/</span>
        <button onClick={onBackToBuildings} style={{
          background: "transparent", border: "none", padding: 0, cursor: "pointer",
          fontFamily: "var(--font-sans)", fontSize: 13, fontWeight: 500,
          color: "var(--fg-2)", letterSpacing: "-0.005em",
        }}>Buildings</button>
        <span style={{ color: "var(--fg-4)", fontSize: 11 }}>/</span>
        <span style={{
          fontFamily: "var(--font-display)", fontSize: 16, fontWeight: 500,
          color: "var(--fg)", letterSpacing: "-0.015em",
          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
        }}>{building.name}</span>
        {t && (
          <span style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            padding: "3px 8px", borderRadius: 4,
            border: `1px solid ${t.color}55`,
            background: `${t.color}11`,
            color: t.color,
            fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.08em",
            marginLeft: 4,
          }}>
            <span style={{ width: 5, height: 5, borderRadius: "50%", background: t.color }} />
            {t.short}
          </span>
        )}
        <span className="mono" style={{ fontSize: 10, color: "var(--fg-4)", letterSpacing: "0.06em" }}>
          {building.units} UNITS · {building.subscribers} SUBS · MDF IN {(building.mdfPlacement || "").toUpperCase()}
        </span>
      </div>

      {/* Actions */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, flex: "0 0 auto" }}>
        <button onClick={onBackToBuildings} style={{
          display: "inline-flex", alignItems: "center", gap: 6,
          padding: "8px 12px", borderRadius: 8,
          background: "transparent",
          border: "1px solid var(--line)",
          color: "var(--fg-2)",
          fontFamily: "var(--font-sans)", fontSize: 12, fontWeight: 500,
          letterSpacing: "-0.005em", cursor: "pointer",
        }}>
          <span style={{ opacity: 0.7 }}>←</span>
          Buildings list
        </button>
        <button onClick={onBackToGlobe} style={{
          display: "inline-flex", alignItems: "center", gap: 6,
          padding: "8px 12px", borderRadius: 8,
          background: "transparent",
          border: "1px solid var(--line)",
          color: "var(--fg-3)",
          fontFamily: "var(--font-sans)", fontSize: 12, fontWeight: 500,
          letterSpacing: "-0.005em", cursor: "pointer",
        }}>
          Map view
        </button>
        {/* Corner close — dismisses the asset popup back to the table
            (Figma 6852-11428: 32×32, 8px radius, #26272B hairline, thin ×). */}
        <button onClick={onClose} aria-label="Close" style={{
          width: 32, height: 32, borderRadius: 8, padding: 0, flexShrink: 0,
          display: "inline-flex", alignItems: "center", justifyContent: "center",
          background: "rgba(255,255,255,0.02)",
          border: "1px solid #26272B",
          color: "var(--fg-3)", cursor: "pointer",
        }}>
          <svg width="11" height="11" viewBox="0 0 11 11" fill="none" aria-hidden="true">
            <path d="M1.5 1.5 9.5 9.5 M9.5 1.5 1.5 9.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
          </svg>
        </button>
      </div>
    </div>
  );
}

function ReservesScreen() {
  // ── Live data from the API ───────────────────────────────────
  // Projects + per-project metrics drive the globe pins and tables.
  // Buildings are lazy-loaded per project; when a pin is selected the
  // effect below kicks off a fetch so the BuildingsListPanel can render.
  const projects = useProjects((s) => s.projects);
  const projectMetrics = useProjects((s) => s.projectMetrics);
  const buildingsByProject = useProjects((s) => s.buildingsByProject);
  const coordsByLocation = useProjects((s) => s.coordsByLocation);
  const fetchProjects = useProjects((s) => s.fetchProjects);
  const fetchProjectMetrics = useProjects((s) => s.fetchProjectMetrics);
  const fetchProjectBuildings = useProjects((s) => s.fetchProjectBuildings);
  const fetchProjectCoords = useProjects((s) => s.fetchProjectCoords);
  useEffect(() => {
    fetchProjects();
    fetchProjectMetrics();
  }, [fetchProjects, fetchProjectMetrics]);

  // Geocode each project's city+country via Nominatim. The store dedupes by
  // key, caches in localStorage, and serializes requests to respect OSM's
  // 1 req/s policy — so this effect can fire freely as `projects` updates.
  useEffect(() => {
    for (const p of projects) {
      if (p.city && p.country) {
        void fetchProjectCoords(p.city, p.country);
      }
    }
  }, [projects, fetchProjectCoords]);

  const [tab, setTab] = useState("active");
  // Mobile-only "Show more" disclosure (Figma 6667-40648) — collapses the
  // deployment card list to the first few cards until expanded. Reset when
  // the tab changes so a fresh list starts collapsed.
  const [mobileExpanded, setMobileExpanded] = useState(false);
  const changeTab = (t: string) => { setTab(t); setMobileExpanded(false); };
  const MOBILE_CARD_LIMIT = 3;
  const [isSmallScreen, setIsSmallScreen] = useState(false);
  const [query, setQuery] = useState("");
  const [strategyFilter, setStrategyFilter] = useState("All");
  const [filterOpen, setFilterOpen] = useState(false);
  const [searchFocused, setSearchFocused] = useState(false);
  const [sort, setSort] = useState<any>({ key: "deployed", dir: "desc" }); // upcoming uses "reserved"
  const [hoverIdx, setHoverIdx] = useState<any>(null);
  const [selectedPin, setSelectedPin] = useState<any>(null);
  const [flyToken, setFlyToken] = useState(0);
  const filterRef = useRef<any>(null);
  const filterMenuRef = useRef<any>(null);
  const [filterPos, setFilterPos] = useState<{ top: number; right: number } | null>(null);

  // Sentence-case a Title-Case strategy name for display ("Apartment
  // Buildings" → "Apartment buildings") without altering the underlying
  // filter value used for matching.
  const toSentence = (s: string) =>
    s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase() : s;

  // Cycle the sort key/direction for a clickable column header.
  const sortBy = (k: string) =>
    setSort((s: any) => (s.key === k ? { key: k, dir: s.dir === "asc" ? "desc" : "asc" } : { key: k, dir: "desc" }));

  // Close the strategy filter dropdown on outside click. The menu renders in a
  // portal, so the trigger and the menu are checked separately.
  useEffect(() => {
    if (!filterOpen) return;
    const onDown = (e: any) => {
      const inTrigger = filterRef.current?.contains(e.target);
      const inMenu = filterMenuRef.current?.contains(e.target);
      if (!inTrigger && !inMenu) setFilterOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [filterOpen]);

  // Anchor the portaled strategy filter menu to the trigger so it escapes the
  // table panel's overflow clipping while staying aligned on scroll/resize.
  useEffect(() => {
    if (!filterOpen) return;
    const update = () => {
      const rect = filterRef.current?.getBoundingClientRect();
      if (!rect) return;
      setFilterPos({ top: rect.bottom + 6, right: window.innerWidth - rect.right });
    };
    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [filterOpen]);

  // Build the v5-shape deployments array from real projects + metrics +
  // buildings. The DeploymentGlobe accepts this via its `deployments`
  // prop; everything below that consumes pins (pinByName, table rows,
  // selectedPin lookups) reads from the same array.
  const metricsById = useMemo(() => {
    const m = new Map<string, ProjectMetrics>();
    for (const x of projectMetrics) m.set(x.project_id, x);
    return m;
  }, [projectMetrics]);
  const apiDeployments = useMemo(
    () => projectsToDeployments(projects, metricsById, buildingsByProject, coordsByLocation),
    [projects, metricsById, buildingsByProject, coordsByLocation],
  );

  // Overview panel data — driven by the same metrics/projects.
  const dryPowder = useDryPowder();
  const overviewStats = useMemo(() => {
    const totalDeployed = projectMetrics.reduce((s, m) => s + m.deployed_value, 0);
    // APY only accrues on ACTIVE projects — upcoming/other non-draft projects
    // are still returned by /project/metrics, so weight the yield over the
    // active subset only (joined by id since metrics carry no status).
    const activeIds = new Set(projects.filter((p) => p.status === 'ACTIVE').map((p) => p.id));
    const activeMetrics = projectMetrics.filter((m) => activeIds.has(m.project_id));
    const activeDeployed = activeMetrics.reduce((s, m) => s + m.deployed_value, 0);
    const weightedYield =
      activeDeployed > 0
        ? activeMetrics.reduce((s, m) => s + m.deployed_value * m.yield_rate, 0) / activeDeployed
        : 0;
    const reserves = dryPowder ?? 0;
    const totalCapital = totalDeployed + reserves;
    const utilization = totalCapital > 0 ? totalDeployed / totalCapital : 0;
    const effectiveApy = weightedYield * utilization;
    const activeCount = projects.filter((p) => p.status === 'ACTIVE').length;
    return [
      { v: totalDeployed > 0 ? formatMoneyCompact(totalDeployed) : '—', l: 'Total Deployed' },
      { v: effectiveApy > 0 ? `${(effectiveApy * 100).toFixed(1)}%` : '—', l: 'APY' },
      { v: totalCapital > 0 ? `${(utilization * 100).toFixed(1)}%` : '—', l: 'Vault Utilization' },
      { v: String(activeCount), l: 'Active Projects' },
    ];
  }, [projectMetrics, dryPowder, projects]);
  const overviewStrategies = useMemo(() => {
    const reserves = dryPowder ?? 0;
    const totalDeployed = projectMetrics.reduce((s, m) => s + m.deployed_value, 0);
    const denom = totalDeployed + reserves;
    const STRATEGY_BAR_COLOR: Record<string, string> = {
      'Apartment Buildings': '#7DD1FF',
      'Carrier Offload': '#7BDC8D',
      'Acquisitions': '#F3A24A',
    };
    // Seed all strategy categories so the portfolio always renders one card
    // per category (Figma shows Apartment Buildings / Carrier Offload /
    // Acquisitions alongside Dry Powder), then fold active deployed value in.
    const byStrategy = new Map<string, { value: number; count: number }>(
      Object.keys(STRATEGY_BAR_COLOR).map((s) => [s, { value: 0, count: 0 }]),
    );
    for (const p of projects) {
      if (p.status !== 'ACTIVE') continue;
      const strategy = PROJECT_TYPE_TO_STRATEGY[p.types[0] ?? ''] ?? 'Apartment Buildings';
      const m = metricsById.get(p.id);
      const v = m?.deployed_value ?? 0;
      const cur = byStrategy.get(strategy) ?? { value: 0, count: 0 };
      cur.value += v;
      cur.count += 1;
      byStrategy.set(strategy, cur);
    }
    const strategyCards = Array.from(byStrategy.entries()).map(([name, info]) => ({
      v: info.value > 0 ? formatMoneyCompact(info.value) : '—',
      l: name,
      sub: `${info.count} ${info.count === 1 ? 'Site' : 'Sites'}`,
      pct: denom > 0 ? Math.round((info.value / denom) * 100) : 0,
      color: STRATEGY_BAR_COLOR[name] ?? '#7DD1FF',
    }));
    const dryCard = {
      v: reserves > 0 ? formatMoneyCompact(reserves) : '—',
      l: 'Dry Powder',
      sub: 'Undeployed',
      pct: denom > 0 ? Math.round((reserves / denom) * 100) : 0,
      color: '#ED7C5B',
    };
    return [dryCard, ...strategyCards];
  }, [dryPowder, projectMetrics, projects, metricsById]);

  // When a pin gets selected, lazy-fetch its buildings so the buildings
  // list (and the asset visualizer) has something to draw.
  useEffect(() => {
    if (!selectedPin?.id) return;
    void fetchProjectBuildings(selectedPin.id);
  }, [selectedPin?.id, fetchProjectBuildings]);

  // After the buildings fetch resolves, refresh `selectedPin` so the
  // detail panel's "View N buildings" pill updates without needing a
  // re-click. The deployments array is the source of truth — find the
  // pin with the same id.
  useEffect(() => {
    if (!selectedPin?.id) return;
    const fresh = apiDeployments.find((d) => d.id === selectedPin.id);
    if (fresh && fresh !== selectedPin) {
      setSelectedPin(fresh);
    }
  }, [apiDeployments, selectedPin]);
  // view: "globe" (default) | "buildings" | "asset"
  const [view, setView] = useState("globe");
  const [selectedBuilding, setSelectedBuilding] = useState<any>(null);
  // FLIP-morph state for buildings-row → asset-panel transition.
  // originRect: row's viewport rect at click time (kept around so close-morph
  // animates back to the same spot).
  // assetPhase: "closed" | "opening" | "open" | "closing"
  const [originRect, setOriginRect] = useState<any>(null);
  const [assetPhase, setAssetPhase] = useState("closed");
  const [targetRect, setTargetRect] = useState<any>(null);
  const assetFrameRef = useRef<any>(null);
  const stretchBeamRef = useRef<any>(null);
  // buildingsClosing: when true, the BuildingsListPanel renders with the
  // out-animation class, then unmounts after the wipe completes. Set by
  // backToGlobe / closeProject when leaving the buildings view directly
  // (not via the asset frame).
  const [buildingsClosing, setBuildingsClosing] = useState(false);
  const BUILDINGS_OUT_MS = 460;

  useEffect(() => {
    const media = window.matchMedia('(max-width: 1024px)');
    const sync = () => setIsSmallScreen(media.matches);
    sync();
    media.addEventListener('change', sync);
    return () => media.removeEventListener('change', sync);
  }, []);

  // Bridge for table → globe: select + bump flyToken so the globe's effect fires.
  // If the project has no lat/lng we still select it (the detail panel + buildings
  // fetch should work) but skip the fly — the globe has nothing to navigate to.
  function selectAndFly(pin: any) {
    setSelectedPin(pin);
    if (Number.isFinite(pin?.lng) && Number.isFinite(pin?.lat)) {
      setFlyToken(t => t + 1);
    }
    setView("globe");
    setSelectedBuilding(null);
  }
  // Globe-triggered selection: just set the pin (globe already handled fly internally).
  function selectFromGlobe(pin: any) {
    setSelectedPin(pin);
  }
  function closeProject() {
    // If we're inside the asset view, run the close-morph first.
    if (view === "asset" && assetPhase === "open") {
      setAssetPhase("closing");
      setTimeout(() => {
        setAssetPhase("closed");
        setSelectedPin(null);
        setView("globe");
        setSelectedBuilding(null);
        setOriginRect(null);
        setTargetRect(null);
      }, 790);
      return;
    }
    // From the buildings list — run the reverse wipe back into the
    // detail card before unmounting the panel.
    if (view === "buildings") {
      setBuildingsClosing(true);
      setTimeout(() => {
        setBuildingsClosing(false);
        setSelectedPin(null);
        setView("globe");
        setSelectedBuilding(null);
        setOriginRect(null);
      }, BUILDINGS_OUT_MS);
      return;
    }
    setSelectedPin(null);
    setView("globe");
    setSelectedBuilding(null);
    setOriginRect(null);
  }
  function openBuildingsList() {
    setView("buildings");
    setSelectedBuilding(null);
    setOriginRect(null);
  }
  function openBuilding(b: any, rect: any) {
    // Keep the row's raw viewport rect — the asset panel now opens as a
    // centered, viewport-fixed modal (blurred backdrop), so the FLIP morph
    // runs entirely in viewport coordinates.
    if (rect) {
      setOriginRect({ left: rect.left, top: rect.top, width: rect.width, height: rect.height });
    }
    setSelectedBuilding(b);
    setView("asset");
    setAssetPhase("opening");
    setTargetRect(null);
  }
  function backToBuildings() {
    if (view === "asset" && assetPhase === "open") {
      setAssetPhase("closing");
      setTimeout(() => {
        setAssetPhase("closed");
        setSelectedBuilding(null);
        setView("buildings");
        setTargetRect(null);
      }, 790);
      return;
    }
    setSelectedBuilding(null);
    setView("buildings");
  }
  function backToGlobe() {
    if (view === "asset" && assetPhase === "open") {
      // Two-phase exit: (1) visualizer shrinks back into its building row
      // (790ms WAAPI morph), (2) buildings panel wipes out to reveal the
      // globe (BUILDINGS_OUT_MS). Chained so the wipe is visible — without
      // it the globe just pops in once the visualizer is gone.
      setAssetPhase("closing");
      setTimeout(() => {
        setAssetPhase("closed");
        setSelectedBuilding(null);
        setOriginRect(null);
        setTargetRect(null);
        setView("buildings");
        setBuildingsClosing(true);
        setTimeout(() => {
          setBuildingsClosing(false);
          setView("globe");
        }, BUILDINGS_OUT_MS);
      }, 790);
      return;
    }
    if (view === "buildings") {
      setBuildingsClosing(true);
      setTimeout(() => {
        setBuildingsClosing(false);
        setView("globe");
        setSelectedBuilding(null);
        setOriginRect(null);
      }, BUILDINGS_OUT_MS);
      return;
    }
    setView("globe");
    setSelectedBuilding(null);
    setOriginRect(null);
  }

  // Asset-frame morph using Web Animations API. CSS transitions get
  // unreliable in this layout (parent fade-up animation, transformed
  // ancestor creating a containing block, and immediate re-renders
  // were causing transitions to start with currentTime:0 indefinitely).
  // WAAPI fires deterministically and gives us a `finished` promise.
  //
  // Critical: this is `useLayoutEffect`, not `useEffect`. The first pass
  // (when targetRect is null) calls setTargetRect, which triggers a
  // re-render that mounts the asset frame at full size. With plain
  // useEffect, the browser would paint that re-render BEFORE the second
  // pass attaches WAAPI — flashing the frame at full size for one frame
  // before the morph plays. useLayoutEffect runs synchronously after DOM
  // commit but before paint, so both passes complete in one flush.
  const animatingRef = useRef(false);
  useLayoutEffect(() => {
    if (assetPhase !== "opening") return;
    if (!targetRect) {
      // Centered modal rect in viewport coords (mirrors the dashboard's
      // CardModal): a large panel held to a 1440×893 aspect, clamped to
      // the viewport with a 32px gutter.
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const width = Math.min(1376, vw - 64);
      const height = Math.min(Math.round(width * 893 / 1440), vh - 64);
      setTargetRect({
        left: Math.round((vw - width) / 2),
        top: Math.round((vh - height) / 2),
        width,
        height,
      });
      return;
    }
    if (!originRect || !assetFrameRef.current) return;
    if (animatingRef.current) return;
    const frame = assetFrameRef.current;
    const dx = (originRect.left + originRect.width / 2) - (targetRect.left + targetRect.width / 2);
    const dy = (originRect.top + originRect.height / 2) - (targetRect.top + targetRect.height / 2);
    const sx = originRect.width / targetRect.width;
    const sy = originRect.height / targetRect.height;
    const ringColor = selectedPin
      ? (STATUS_COLORS[selectedPin.status] || "#F3A24A")
      : "#F3A24A";
    animatingRef.current = true;
    // Two-stage opening:
    //  (A) Row pulse + a "stretch beam" (rendered alongside the frame)
    //      grows from the row footprint to the target rect over ~220ms.
    //      The frame itself is delayed and stays invisible during this
    //      stage so the row stays visible underneath.
    //  (B) Frame fades in (opacity 0 → 1) WHILE morphing scale+translate
    //      to its docked state, accent-glowing through the descent so it
    //      feels like the row has stretched up and "filled in" with the
    //      visualizer.
    const ANTICIPATE = 180;
    const anim = frame.animate(
      [
        {
          offset: 0,
          transform: `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})`,
          opacity: 0,
          borderColor: ringColor,
          boxShadow: `0 0 0 6px ${ringColor}55, 0 0 40px ${ringColor}77, 0 30px 80px -20px rgba(0,0,0,0.6)`,
        },
        {
          offset: 0.18,
          // Hold at row footprint for the anticipation, fully transparent.
          transform: `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})`,
          opacity: 0,
          borderColor: ringColor,
          boxShadow: `0 0 0 6px ${ringColor}55, 0 0 40px ${ringColor}77, 0 30px 80px -20px rgba(0,0,0,0.6)`,
        },
        {
          offset: 0.55,
          opacity: 0.7,
          borderColor: ringColor,
          boxShadow: `0 0 0 3px ${ringColor}55, 0 0 32px ${ringColor}55, 0 30px 80px -25px rgba(0,0,0,0.6)`,
        },
        {
          offset: 1,
          transform: "translate(0px, 0px) scale(1, 1)",
          opacity: 1,
          borderColor: "rgba(255,255,255,0.08)",
          boxShadow: "0 30px 80px -30px rgba(0,0,0,0.55)",
        },
      ],
      {
        duration: 790,
        easing: "cubic-bezier(.55,.05,.25,1)",
        fill: "both",
      },
    );
    anim.onfinish = () => {
      animatingRef.current = false;
      setAssetPhase("open");
      // Drop the WAAPI fill so the element follows its inline style.
      try { anim.cancel(); } catch (e) {}
    };
    // Stretch beam — an amber-glow block that visibly grows from the
    // row footprint to the target rect during the first half of the
    // morph, then fades out as the frame opacity ramps in. Reads as
    // "the row is stretching upward into the slot".
    let beamAnim: any = null;
    if (stretchBeamRef.current) {
      const beam = stretchBeamRef.current;
      // Beam tracks the frame's geometric trajectory exactly: same offsets,
      // same easing — anticipation hold (0→0.18), then expand (0.18→1.0).
      // Opacity fades in fast on the row, holds during anticipation, then
      // fades out as the frame fades in so they hand off cleanly.
      beamAnim = beam.animate(
        [
          {
            offset: 0,
            left: `${originRect.left}px`,
            top: `${originRect.top}px`,
            width: `${originRect.width}px`,
            height: `${originRect.height}px`,
            opacity: 0,
            borderRadius: "8px",
          },
          {
            offset: 0.08,
            left: `${originRect.left}px`,
            top: `${originRect.top}px`,
            width: `${originRect.width}px`,
            height: `${originRect.height}px`,
            opacity: 0.95,
            borderRadius: "8px",
          },
          {
            offset: 0.18,
            left: `${originRect.left}px`,
            top: `${originRect.top}px`,
            width: `${originRect.width}px`,
            height: `${originRect.height}px`,
            opacity: 0.95,
            borderRadius: "8px",
          },
          {
            offset: 0.55,
            // Halfway between row and target (linear in left/top/w/h, but
            // easing comes from the animation timing function — same as
            // the frame, so the geometric interpolation matches).
            left: `${originRect.left + (targetRect.left - originRect.left) * 0.55}px`,
            top: `${originRect.top + (targetRect.top - originRect.top) * 0.55}px`,
            width: `${originRect.width + (targetRect.width - originRect.width) * 0.55}px`,
            height: `${originRect.height + (targetRect.height - originRect.height) * 0.55}px`,
            opacity: 0.55,
            borderRadius: "11px",
          },
          {
            offset: 1,
            left: `${targetRect.left}px`,
            top: `${targetRect.top}px`,
            width: `${targetRect.width}px`,
            height: `${targetRect.height}px`,
            opacity: 0,
            borderRadius: "14px",
          },
        ],
        {
          duration: 790,
          easing: "cubic-bezier(.55,.05,.25,1)",
          fill: "both",
        },
      );
    }
    return () => {
      animatingRef.current = false;
      try { anim.cancel(); } catch (e) {}
      try { if (beamAnim) beamAnim.cancel(); } catch (e) {}
    };
  }, [assetPhase, targetRect, originRect, selectedPin]);

  // Closing morph: animate from docked state back to the row rect.
  // useLayoutEffect for the same reason as the opening morph: keep WAAPI
  // attachment synchronous with the phase transition so the browser never
  // paints the frame in an unanimated intermediate state.
  useLayoutEffect(() => {
    if (assetPhase !== "closing") return;
    if (!assetFrameRef.current || !originRect || !targetRect) return;
    if (animatingRef.current) return;
    const frame = assetFrameRef.current;
    const dx = (originRect.left + originRect.width / 2) - (targetRect.left + targetRect.width / 2);
    const dy = (originRect.top + originRect.height / 2) - (targetRect.top + targetRect.height / 2);
    const sx = originRect.width / targetRect.width;
    const sy = originRect.height / targetRect.height;
    const ringColor = selectedPin
      ? (STATUS_COLORS[selectedPin.status] || "#F3A24A")
      : "#F3A24A";
    animatingRef.current = true;
    const anim = frame.animate(
      [
        {
          offset: 0,
          transform: "translate(0px, 0px) scale(1, 1)",
          opacity: 1,
          borderColor: "rgba(255,255,255,0.08)",
          boxShadow: "0 30px 80px -30px rgba(0,0,0,0.55)",
        },
        {
          offset: 0.45,
          opacity: 0.6,
          borderColor: ringColor,
          boxShadow: `0 0 0 3px ${ringColor}55, 0 0 32px ${ringColor}55, 0 30px 80px -25px rgba(0,0,0,0.6)`,
        },
        {
          offset: 0.85,
          transform: `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})`,
          opacity: 0,
          borderColor: ringColor,
          boxShadow: `0 0 0 6px ${ringColor}55, 0 0 40px ${ringColor}77, 0 30px 80px -20px rgba(0,0,0,0.6)`,
        },
        {
          offset: 1,
          transform: `translate(${dx}px, ${dy}px) scale(${sx}, ${sy})`,
          opacity: 0,
          borderColor: ringColor,
          boxShadow: "none",
        },
      ],
      {
        duration: 790,
        easing: "cubic-bezier(.75,0,.45,.95)",
        fill: "forwards",
      },
    );
    // Mirror beam: fades in over the frame, contracts target → row in
    // lockstep with the frame's transform, then fades out as it lands.
    let beamAnim: any = null;
    if (stretchBeamRef.current) {
      const beam = stretchBeamRef.current;
      beamAnim = beam.animate(
        [
          {
            offset: 0,
            left: `${targetRect.left}px`,
            top: `${targetRect.top}px`,
            width: `${targetRect.width}px`,
            height: `${targetRect.height}px`,
            opacity: 0,
            borderRadius: "14px",
          },
          {
            offset: 0.15,
            left: `${targetRect.left}px`,
            top: `${targetRect.top}px`,
            width: `${targetRect.width}px`,
            height: `${targetRect.height}px`,
            opacity: 0.85,
            borderRadius: "14px",
          },
          {
            offset: 0.55,
            // Halfway between target and row.
            left: `${targetRect.left + (originRect.left - targetRect.left) * 0.55}px`,
            top: `${targetRect.top + (originRect.top - targetRect.top) * 0.55}px`,
            width: `${targetRect.width + (originRect.width - targetRect.width) * 0.55}px`,
            height: `${targetRect.height + (originRect.height - targetRect.height) * 0.55}px`,
            opacity: 0.95,
            borderRadius: "11px",
          },
          {
            offset: 0.85,
            left: `${originRect.left}px`,
            top: `${originRect.top}px`,
            width: `${originRect.width}px`,
            height: `${originRect.height}px`,
            opacity: 0.95,
            borderRadius: "8px",
          },
          {
            offset: 1,
            left: `${originRect.left}px`,
            top: `${originRect.top}px`,
            width: `${originRect.width}px`,
            height: `${originRect.height}px`,
            opacity: 0,
            borderRadius: "8px",
          },
        ],
        {
          duration: 790,
          easing: "cubic-bezier(.75,0,.45,.95)",
          fill: "forwards",
        },
      );
    }
    return () => {
      animatingRef.current = false;
      try { anim.cancel(); } catch (e) {}
      try { if (beamAnim) beamAnim.cancel(); } catch (e) {}
    };
  }, [assetPhase, originRect, targetRect, selectedPin]);
  // Find a pin in apiDeployments by name (used by table rows where rows
  // pass the deployment name to bridge into the globe selection).
  function pinByName(name: string) {
    const i = apiDeployments.findIndex((d: any) => d.name === name);
    if (i < 0) return null;
    return { ...apiDeployments[i], idx: i };
  }

  // Tables — derived from real projects + metrics. The shapes match v5's
  // hardcoded fixtures so the table render code stays byte-identical.
  const totalDeployedDollars = useMemo(
    () => projectMetrics.reduce((s, m) => s + m.deployed_value, 0),
    [projectMetrics],
  );
  const activeProjects: any[] = useMemo(() => {
    return projects
      .filter((p) => p.status === 'ACTIVE')
      .map((p) => {
        const buildingCount = (buildingsByProject[p.id] ?? []).length;
        return toActiveTableRow(p, metricsById.get(p.id), totalDeployedDollars, buildingCount);
      });
  }, [projects, metricsById, totalDeployedDollars, buildingsByProject]);
  const upcoming: any[] = useMemo(() => {
    const upcomingProjects = projects.filter((p) => p.status in STATUS_PROGRESS_V5);
    const totalReserved = upcomingProjects.reduce(
      (s, p) => s + (metricsById.get(p.id)?.deployed_value ?? 0),
      0,
    );
    return upcomingProjects.map((p) => toUpcomingTableRow(p, metricsById.get(p.id), totalReserved));
  }, [projects, metricsById]);

  // Strategy → chip palette (Figma: 4% fill / 20% border / solid accent text)
  const STRATEGY_CHIP: any = {
    "Apartment Buildings": { bg: "rgba(125,209,255,0.04)", border: "rgba(125,209,255,0.2)", fg: "#7DD1FF" },
    "Carrier Offload":     { bg: "rgba(123,220,141,0.04)", border: "rgba(123,220,141,0.2)", fg: "#7BDC8D" },
    "Acquisitions":        { bg: "rgba(243,162,74,0.04)",  border: "rgba(243,162,74,0.2)",  fg: "#F3A24A" },
  };
  const StrategyChip = ({ name }: any) => {
    const s = STRATEGY_CHIP[name] || { bg: "rgba(232,224,240,0.04)", border: "rgba(232,224,240,0.2)", fg: "var(--fg-2)" };
    return (
      <span style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        fontFamily: "var(--font-sans)", fontSize: 10.56, fontWeight: 400, lineHeight: "14.08px",
        padding: "3px 10px", borderRadius: 7.04,
        background: s.bg, border: `0.575px solid ${s.border}`, color: s.fg,
        whiteSpace: "nowrap",
      }}>
        {toSentence(name)}
      </span>
    );
  };

  // Region badge (Figma: 7px radius, ink-tinted fill/border, ink-60 text)
  const RegionTag = ({ code }: any) => (
    <span style={{
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      fontFamily: "var(--font-sans)", fontSize: 10.56, fontWeight: 400, lineHeight: "14.08px",
      padding: "2px 7px", borderRadius: 7.04,
      background: "rgba(140,138,132,0.08)", border: "0.575px solid rgba(140,138,132,0.4)",
      color: "#8C8A84", whiteSpace: "nowrap",
    }}>{code}</span>
  );

  // Labelled metric cell for the mobile deployment cards (Figma 6667-40093).
  const ReserveCardMetric = ({ label, children }: { label: string; children: ReactNode }) => (
    <div style={{ minWidth: 0 }}>
      <div style={{
        fontFamily: "var(--font-sans)", fontSize: 12, lineHeight: "20px", color: "#8C8A84",
        letterSpacing: "0.24px", marginBottom: 2,
      }}>{label}</div>
      <div style={{ display: "flex", alignItems: "center" }}>{children}</div>
    </div>
  );

  // Q-quarter / year string → comparable number for sorting "Est. GO-LIVE"
  const parseQ = (s: string) => {
    const m = /Q(\d)\s+(\d{4})/.exec(s || "");
    return m ? parseInt(m[2]) * 4 + parseInt(m[1]) : 0;
  };

  const matchesQuery = (p: any) => {
    if (!query) return true;
    const q = query.toLowerCase().trim();
    if (!q) return true;
    const hay = [p.name, p.region, p.strategy, p.blurb, ...(p.searchTokens || [])]
      .filter(Boolean).join(" ").toLowerCase();
    // Match if every whitespace-separated term appears somewhere in the haystack
    return q.split(/\s+/).every(t => hay.includes(t));
  };
  const matchesStrategy = (p: any) => strategyFilter === "All" || p.strategy === strategyFilter;
  const sortRows = (rows: any[], defaultKey: string) => {
    const key = sort.key === "deployed" && rows[0] && !("deployed" in rows[0]) ? "reserved"
              : sort.key === "reserved" && rows[0] && !("reserved" in rows[0]) ? "deployed"
              : sort.key;
    const safeKey = (rows[0] && key in rows[0]) ? key : defaultKey;
    return [...rows].sort((a, b) => {
      let va = a[safeKey], vb = b[safeKey];
      if (safeKey === "live") { va = parseQ(va); vb = parseQ(vb); }
      const r = va > vb ? 1 : va < vb ? -1 : 0;
      return r * (sort.dir === "asc" ? 1 : -1);
    });
  };
  const visibleActive = sortRows(activeProjects.filter(p => matchesQuery(p) && matchesStrategy(p)), "deployed");
  const visibleUpcoming = sortRows(upcoming.filter(p => matchesQuery(p) && matchesStrategy(p)), "reserved");
  const activeCount = activeProjects.filter(p => matchesStrategy(p) && matchesQuery(p)).length;
  const upcomingCount = upcoming.filter(p => matchesStrategy(p) && matchesQuery(p)).length;

  // Available strategies for the filter dropdown, in display order
  const STRATEGY_ORDER = ["All", "Apartment Buildings", "Carrier Offload", "Acquisitions"];

  // Portfolio summary line shown above the strategy cards. Derived from the
  // same real metrics that drive the cards — no fixtures.
  const portfolioReserves = dryPowder ?? 0;
  const portfolioAum = totalDeployedDollars + portfolioReserves;
  const strategyCount = overviewStrategies.length;

  return (
    <div data-screen-label="05 Reserves" className="fade-up app-container" style={{ width: "100%", padding: isSmallScreen ? "28px 16px 56px" : "48px 32px 80px", display: "flex", flexDirection: "column", gap: 28, position: "relative" }}>
      {/* ── Hero — centered title + subtitle + summary stat bar ─────── */}
      <header style={{ order: 1, display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", gap: 22, paddingTop: isSmallScreen ? 4 : 20 }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
          <h1 style={{
            display: "flex", gap: 12, justifyContent: "center", alignItems: "center", flexWrap: "wrap",
            maxWidth: "100%",
            fontFamily: "var(--font-sans)", fontWeight: 500, fontSize: isSmallScreen ? 30 : 36,
            letterSpacing: "-0.9px", lineHeight: 1.05, margin: 0, color: "#FBF7F3",
          }}>
            <span>Telecom</span>
            <span style={{
              background: "linear-gradient(to right, #f1994f, #e84066)",
              WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent",
            }}>infrastructure</span>
          </h1>
          <p style={{ fontFamily: "var(--font-sans)", fontSize: 16, color: "#8C8A84", lineHeight: "20px", margin: 0, maxWidth: 540, textAlign: "center" }}>
            Track active telecom projects and upcoming deployments backed by subscriber revenue.
          </p>
        </div>
        {isSmallScreen ? (
          /* Mobile (Figma 6667-40165): borderless 2-column grid, value above
             label, with a top hairline. */
          <div style={{ position: "relative", width: "100%", maxWidth: 372, borderTop: "1px solid rgba(250,247,242,0.08)", paddingTop: 18 }}>
            <div style={{ position: "relative", display: "grid", gridTemplateColumns: "auto auto", justifyContent: "space-evenly", rowGap: 18 }}>
              {overviewStats.map((s, i) => (
                <div key={i} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <span className="tabular" style={{ fontFamily: "var(--font-sans)", fontSize: 18, fontWeight: 500, lineHeight: "25px", color: "#FBF7F3" }}>{s.v}</span>
                  <span style={{ fontFamily: "var(--font-sans)", fontSize: 12, lineHeight: "14px", color: "#8C8A84" }}>{s.l}</span>
                </div>
              ))}
            </div>
          </div>
        ) : (
        <div style={{
          display: "inline-flex",
          alignItems: "stretch", justifyContent: "center",
          borderRadius: 999, border: "1px solid rgba(250,247,242,0.1)",
          background: "rgba(255,255,255,0.02)",
          overflow: "hidden",
        }}>
          {overviewStats.map((s, i) => {
            return (
              <Fragment key={i}>
                {/* Short, vertically-centered divider between stats (desktop). */}
                {i > 0 && (
                  <span aria-hidden style={{ alignSelf: "center", flex: "0 0 auto", width: 1, height: 28.5, background: "rgba(250,247,242,0.1)" }} />
                )}
                <div style={{
                  display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 5,
                  boxSizing: "border-box",
                  minWidth: 180,
                  padding: "13px 12px",
                }}>
                  <span style={{ fontFamily: "var(--font-sans)", fontSize: 9, fontWeight: 600, letterSpacing: "1.62px", color: "#8C8A84", textAlign: "center" }}>{s.l}</span>
                  <span className="tabular" style={{ fontFamily: "var(--font-sans)", fontSize: 13, fontWeight: 500, color: "#FBF7F3", letterSpacing: "-0.065px" }}>{s.v}</span>
                </div>
              </Fragment>
            );
          })}
        </div>
        )}
      </header>

      {/* ── Portfolio by strategy — full-width row of strategy cards ── */}
      <section style={{ order: 2, display: "flex", flexDirection: "column", gap: 28 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14, maxWidth: 480 }}>
          <h2 style={{ fontFamily: "var(--font-sans)", fontSize: 20, fontWeight: 600, lineHeight: "20px", margin: 0, color: "#FBF7F3" }}>Portfolio by strategy</h2>
          <p style={{ fontFamily: "var(--font-sans)", fontSize: 16, fontWeight: 400, lineHeight: "20px", margin: 0, color: "#8C8A84" }}>
            {strategyCount} {strategyCount === 1 ? "Strategy" : "Strategies"} · {portfolioAum > 0 ? formatMoneyCompact(portfolioAum) : "—"} AUM
          </p>
        </div>
        {isSmallScreen ? (
          /* Mobile (Figma 6667-40190): compact 95px cards — value, label,
             progress bar, then pct (left) + sub (right). */
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 9 }}>
            {overviewStrategies.map((s: any, i: number) => (
              <div key={i} style={{ position: "relative", height: 95, borderRadius: 20, background: "#13151A", border: "1px solid #26272B", overflow: "hidden", padding: 10 }}>
                <div aria-hidden style={{ position: "absolute", right: -40, top: -60, width: 160, height: 160, background: "radial-gradient(circle, rgba(243,162,74,0.07), transparent 70%)", pointerEvents: "none" }} />
                <div style={{ position: "relative", display: "flex", flexDirection: "column", height: "100%" }}>
                  <span className="tabular" style={{ fontFamily: "var(--font-sans)", fontSize: 18, fontWeight: 500, lineHeight: "21px", color: "#FBF7F3" }}>{s.v}</span>
                  <span style={{ fontFamily: "var(--font-sans)", fontSize: 9, color: "#8C8A84", letterSpacing: "-0.3px", marginTop: 8, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{s.l}</span>
                  <div style={{ position: "relative", height: 4, borderRadius: 3, marginTop: 6, background: "rgba(140,138,132,0.2)", overflow: "hidden" }}>
                    <div style={{ position: "absolute", left: 0, top: 0, height: 4, borderRadius: 3, width: `${s.pct}%`, background: s.color }} />
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8 }}>
                    <span style={{ fontFamily: "var(--font-sans)", fontSize: 9, color: "#8C8A84", letterSpacing: "-0.3px" }}>{s.pct}%</span>
                    <span style={{ fontFamily: "var(--font-sans)", fontSize: 9, color: "#8C8A84", letterSpacing: "-0.3px" }}>{s.sub}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${Math.max(overviewStrategies.length, 1)}, 1fr)`, gap: 10 }}>
          {overviewStrategies.map((s: any, i: number) => (
            <div key={i} className="glow-card" style={{ position: "relative", height: 160, borderRadius: 20, background: "var(--bg-2)", overflow: "hidden", padding: 21 }}>
              <div style={{ position: "relative" }}>
                <div className="tabular" style={{ fontFamily: "var(--font-sans)", fontSize: 30, fontWeight: 500, lineHeight: 1.15, color: "#FBF7F3" }}>{s.v}</div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, marginTop: 26 }}>
                  <span style={{ fontFamily: "var(--font-sans)", fontSize: 14, color: "#8C8A84", letterSpacing: "-0.31px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{s.l}</span>
                  <span style={{ fontFamily: "var(--font-sans)", fontSize: 14, color: "#8C8A84", letterSpacing: "-0.31px", whiteSpace: "nowrap" }}>{s.sub}</span>
                </div>
                <div style={{ position: "relative", height: 6, borderRadius: 3, marginTop: 8, background: "rgba(140,138,132,0.2)", overflow: "hidden" }}>
                  <div style={{ position: "absolute", left: 0, top: 0, height: 6, borderRadius: 3, width: `${s.pct}%`, background: s.color }} />
                </div>
                <div style={{ fontFamily: "var(--font-sans)", fontSize: 14, color: "rgba(140,138,132,0.7)", letterSpacing: "-0.31px", marginTop: 10 }}>{s.pct}%</div>
              </div>
            </div>
          ))}
        </div>
        )}
      </section>

      {/* Grid wrapper — the asset detail now opens as a centered,
          viewport-fixed modal (portaled to <body> with a blurred
          backdrop), so the grid keeps its natural height and is simply
          blurred behind the overlay. Rendered last (order: 4) so the map
          explorer sits below the table. */}
      <div className="reserves-grid-wrapper" style={{
        order: 4,
        position: "relative",
      }}>
      {isSmallScreen ? (
        /* Mobile: no inline detail card — the "Live network" section holds
           the globe; tapping a row or pin opens MobileProjectSheet instead. */
        <div style={{ display: "flex", flexDirection: "column", gap: 21 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <h2 style={{ fontFamily: "var(--font-sans)", fontSize: 16, fontWeight: 600, color: "#FAF7F2", margin: 0, lineHeight: "normal" }}>Live network</h2>
            <div style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <span style={{ fontFamily: "var(--font-sans)", fontSize: 12, color: "#8C8A84", lineHeight: "20.25px" }}>How to use live network</span>
              <DashboardInfoPopover
                ariaLabel="How to use live network"
                content="Each marker is a telecom deployment funded by the vault. Tap a marker on the globe — or a project in the list above — to view its location, status, and details."
                widthClassName="w-[260px]"
                trigger={
                  <span style={{
                    width: 12, height: 12, borderRadius: 6, border: "1px solid #8C8A84",
                    display: "inline-flex", alignItems: "center", justifyContent: "center",
                    fontFamily: "var(--font-mono)", fontSize: 9, lineHeight: 1, color: "#8C8A84",
                  }}>i</span>
                }
              />
            </div>
          </div>
          <div style={{ position: "relative", width: "100%", aspectRatio: "742/529", borderRadius: 10, border: "1px solid #26272B", overflow: "hidden" }}>
            <DeploymentGlobe
              hoverIdx={hoverIdx} setHoverIdx={setHoverIdx}
              selectedPin={selectedPin}
              onSelectPin={selectFromGlobe}
              flyToken={flyToken}
              deployments={apiDeployments}
            />
          </div>
        </div>
      ) : (
      <>
      {/* Grid (left detail card + right globe/buildings list) — stays
          mounted underneath the asset overlay so the morph reads as
          the asset growing OUT of the building row. */}
      <div style={{
        display: "grid", gridTemplateColumns: isSmallScreen ? "1fr" : "1fr 1.3fr", gap: 20, alignItems: "stretch",
      }}>
        <div className="card-strong" style={{ padding: 0, position: "relative", overflow: "hidden", display: "flex", flexDirection: "column" }}>
          <div style={{ padding: 28, position: "absolute", inset: 0, display: "flex", flexDirection: "column", overflow: "auto" }}>
            {selectedPin ? (
              <ProjectDetailPanel
                key={`d-${selectedPin.idx}`}
                pin={selectedPin}
                onClose={closeProject}
                onViewBuildings={openBuildingsList}
                view={view}
                onBackToGlobe={backToGlobe}
                selectedBuilding={selectedBuilding}
                onBackToBuildings={backToBuildings}
              />
            ) : (
              <InspectPanel key="ov" />
            )}
          </div>
        </div>

        {/* Globe / buildings list. Both can be present simultaneously
            during the buildings open/close wipe — the panel is rendered
            absolutely on top of the globe so the wipe reveals the globe
            beneath, no pop-in when the panel unmounts. */}
        <div style={{ position: "relative" }}>
          <div style={{ position: "relative", height: "100%" }}>
            <DeploymentGlobe
              hoverIdx={hoverIdx} setHoverIdx={setHoverIdx}
              selectedPin={selectedPin}
              onSelectPin={selectFromGlobe}
              flyToken={flyToken}
              deployments={apiDeployments}
            />
          </div>
          {(view === "buildings" || view === "asset" || assetPhase === "closing" || buildingsClosing) && selectedPin && (
            <div style={{ position: "absolute", inset: 0 }}>
              <BuildingsListPanel pin={selectedPin} onSelectBuilding={openBuilding} liftingId={view === "asset" || assetPhase === "closing" ? selectedBuilding?.id : null} outgoing={buildingsClosing} />
            </div>
          )}
        </div>
      </div>

      {/* Asset overlay — opens as a centered, viewport-fixed modal
          (portaled to <body>) with a blurred backdrop, mirroring the
          dashboard's CardModal. The FLIP morph still grows the frame from
          the clicked row's viewport rect up to the centered panel. */}
      {(view === "asset" || assetPhase === "closing") && createPortal((() => {
        // The frame is rendered at its DOCKED/resting state. The morph
        // (open and close) is driven by WAAPI in the effects above —
        // no inline transform/transition juggling.
        const ringColor = selectedPin ? STATUS_COLORS[selectedPin.status] : "var(--dawn-amber)";
        const beamColor = selectedPin
          ? (STATUS_COLORS[selectedPin.status] || "#F3A24A")
          : "#F3A24A";
        return (
          <div className="reserves-asset-modal-root theme-midnight">
            <div
              className={assetPhase === "closing" ? "reserves-asset-backdrop-out" : "reserves-asset-backdrop"}
              onMouseDown={closeProject}
            />
            {targetRect && originRect && (
              <div
                ref={stretchBeamRef}
                aria-hidden="true"
                style={{
                  position: "fixed",
                  left: originRect.left,
                  top: originRect.top,
                  width: originRect.width,
                  height: originRect.height,
                  zIndex: 49,
                  borderRadius: 8,
                  pointerEvents: "none",
                  background: `linear-gradient(180deg, ${beamColor}aa 0%, ${beamColor}77 35%, ${beamColor}55 70%, ${beamColor}22 100%)`,
                  boxShadow: `0 0 0 1px ${beamColor}88, 0 0 40px ${beamColor}66, 0 0 80px ${beamColor}44`,
                  opacity: 0,
                  willChange: "left, top, width, height, opacity",
                }}
              />
            )}
            {targetRect && (
              <div
                ref={assetFrameRef}
                className="reserves-asset-frame docked"
                style={{
                  position: "fixed",
                  left: targetRect.left,
                  top: targetRect.top,
                  width: targetRect.width,
                  height: targetRect.height,
                  transformOrigin: "center center",
                  zIndex: 50,
                  borderRadius: 14,
                  border: "1px solid var(--line)",
                  boxShadow: "0 30px 80px -30px rgba(0,0,0,0.55)",
                  background: "var(--bg-2)",
                  overflow: "hidden",
                }}
              >
                <div className="reserves-asset-content" style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column" }}>
                  <div className={assetPhase === "closing" ? "reserves-strip-out" : "reserves-strip-in"} style={{ flex: "0 0 auto" }}>
                    <ProjectAssetContextStrip
                      pin={selectedPin}
                      building={selectedBuilding}
                      onBackToBuildings={backToBuildings}
                      onBackToGlobe={backToGlobe}
                      onClose={closeProject}
                    />
                  </div>
                  <div style={{ flex: 1, minHeight: 0 }}>
                    <AssetVisualizerPanel
                      building={selectedBuilding}
                      pin={selectedPin}
                      onBack={backToBuildings}
                    />
                  </div>
                </div>
              </div>
            )}
          </div>
        );
      })(), document.body)}
      </>
      )}
      </div>{/* end grid wrapper */}

      {/* Mobile detail bottom-sheet (Figma 6676-76398) — slides up when a
          deployment is selected on small screens. */}
      {isSmallScreen && selectedPin && (
        <MobileProjectSheet
          key={`sheet-${selectedPin.id}`}
          pin={selectedPin}
          onClose={closeProject}
        />
      )}

      {/* Tables — single bordered panel: idle callout + controls, then the
          deployment table (grid layout matching the Figma column centers). */}
      <div style={{ order: 3, ...(isSmallScreen ? {} : { background: "#13151A", border: "1px solid #26272B", borderRadius: 20, overflow: "hidden" }) }}>
        {/* Top controls region (idle callout + tabs + search/filter) */}
        <div style={{ padding: isSmallScreen ? 0 : "18px 21px 16px" }}>
          {/* Idle reserves callout */}
          <div style={{
            display: "flex", alignItems: isSmallScreen ? "flex-start" : "center", gap: 16,
            flexDirection: isSmallScreen ? "column" : "row",
            minHeight: isSmallScreen ? undefined : 71, padding: isSmallScreen ? "16px" : "0 22px", borderRadius: 15,
            border: "1px solid rgba(243,162,74,0.3)",
            background: "rgba(243,162,74,0.04)",
            marginBottom: 20,
          }}>
            <div style={{ flex: 1, minWidth: 0, paddingTop: isSmallScreen ? 0 : 14, paddingBottom: isSmallScreen ? 0 : 14 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontFamily: "var(--font-sans)", color: "#FBF7F3", fontWeight: 600, fontSize: 14, lineHeight: "20px" }}>USD.tel · Idle reserves</span>
                <span style={{
                  display: "inline-flex", alignItems: "center", justifyContent: "center",
                  fontFamily: "var(--font-sans)", fontSize: 10.56, fontWeight: 400, lineHeight: "14.08px",
                  padding: "3px 10px", borderRadius: 7.04,
                  background: "rgba(243,162,74,0.08)", border: "0.575px solid rgba(243,162,74,0.2)",
                  color: "#F3A24A",
                }}>Undeployed</span>
              </div>
              <div style={{ fontFamily: "var(--font-sans)", fontSize: 12, color: "#8C8A84", lineHeight: 1.4, marginTop: 4 }}>
                Stablecoin awaiting deployment to telecom projects.
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", width: isSmallScreen ? "100%" : "auto", justifyContent: isSmallScreen ? "space-between" : "flex-start" }}>
              {[
                {
                  k: "IDLE",
                  v: dryPowder !== null && dryPowder > 0 ? formatMoneyCompact(dryPowder) : "—",
                  color: "#FBF7F3",
                },
                { k: "APY · T-BILLS", v: "4.8%", color: "#FBF7F3" },
                {
                  k: "OF TVL",
                  v: (() => {
                    const reserves = dryPowder ?? 0;
                    const totalDeployed = projectMetrics.reduce((s, m) => s + m.deployed_value, 0);
                    const denom = totalDeployed + reserves;
                    return denom > 0 ? `${((reserves / denom) * 100).toFixed(1)}%` : "—";
                  })(),
                  color: "#FBF7F3",
                },
              ].map((cell, i) => (
                <div key={cell.k} style={{
                  display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 2,
                  minWidth: isSmallScreen ? 0 : 88,
                  padding: isSmallScreen ? "0" : "0 22px",
                  borderLeft: !isSmallScreen && i > 0 ? "1px solid rgba(250,247,242,0.1)" : "none",
                }}>
                  <span style={{ fontFamily: "var(--font-sans)", fontSize: 12, color: "#8C8A84", opacity: 0.5, lineHeight: "15px" }}>{cell.k}</span>
                  <span className="tabular" style={{ fontFamily: "var(--font-sans)", fontSize: 16, fontWeight: 600, color: cell.color, lineHeight: "15px" }}>{cell.v}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Mobile controls (Figma 6667-40517 / 40527): "Deployments" heading +
              compact toggle, full-width search, horizontal filter chips. */}
          {isSmallScreen && (
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                <span style={{ fontFamily: "var(--font-sans)", fontSize: 16, fontWeight: 600, color: "#FAF7F2" }}>Deployments</span>
                <div style={{ display: "inline-flex", alignItems: "center", gap: 8, height: 39, padding: "0 6px", borderRadius: 12, border: "1px solid #26272B", background: "#13151A" }}>
                  {([["active", `Active (${activeCount})`], ["upcoming", `Upcoming (${upcomingCount})`]] as const).map(([val, label]) => {
                    const on = tab === val;
                    return (
                      <button
                        key={val}
                        type="button"
                        onClick={() => changeTab(val)}
                        style={{
                          display: "inline-flex", alignItems: "center", justifyContent: "center",
                          height: 29, padding: on ? "0 14px" : "0 4px", borderRadius: 20, border: "none",
                          background: on ? "linear-gradient(90deg, #f1994f, #e84066)" : "transparent",
                          color: on ? "#07080B" : "#8C8A84",
                          fontFamily: "var(--font-sans)", fontSize: 12, fontWeight: on ? 600 : 500,
                          whiteSpace: "nowrap", cursor: "pointer",
                        }}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
              </div>
              <div style={{ position: "relative", width: "100%" }}>
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true" style={{
                  position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", pointerEvents: "none",
                }}>
                  <circle cx="8" cy="8" r="5.25" stroke="#8C8A84" strokeWidth="1.3" />
                  <line x1="12" y1="12" x2="16" y2="16" stroke="#8C8A84" strokeWidth="1.3" strokeLinecap="round" />
                </svg>
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onFocus={() => setSearchFocused(true)}
                  onBlur={() => setSearchFocused(false)}
                  placeholder="Search name, region, strategy"
                  style={{
                    width: "100%", boxSizing: "border-box", height: 40, padding: "0 14px 0 40px",
                    background: "#121419",
                    border: `1px solid ${searchFocused ? "#F3A24A" : "#313234"}`,
                    borderRadius: 10,
                    fontFamily: "var(--font-sans)", fontSize: 16,
                    color: "#FBF7F3", outline: "none",
                    transition: "border-color 140ms ease",
                  }} />
              </div>
              <div className="boost-tabs-scroll" style={{ display: "flex", gap: 10, overflowX: "auto", paddingBottom: 2 }}>
                {STRATEGY_ORDER.map((s) => {
                  const active = strategyFilter === s;
                  const label = s === "All" ? "All" : toSentence(s);
                  return (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setStrategyFilter(s)}
                      style={{
                        flexShrink: 0, display: "inline-flex", alignItems: "center", justifyContent: "center",
                        height: 30, padding: "0 16px", borderRadius: 10,
                        border: `0.6px solid ${active ? "#F1994F" : "#26272B"}`,
                        background: active ? "rgba(243,162,74,0.05)" : "#13151A",
                        fontFamily: "var(--font-sans)", fontSize: 12, cursor: "pointer", whiteSpace: "nowrap",
                      }}
                    >
                      {active ? (
                        <span style={{ backgroundImage: "linear-gradient(90deg, #f1994f, #e84066)", WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent", fontWeight: 600 }}>{label}</span>
                      ) : (
                        <span style={{ color: "#C6C2BB", fontWeight: 400 }}>{label}</span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Tabs + search/filter row (desktop) */}
          {!isSmallScreen && (
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            gap: 16, flexWrap: "wrap",
          }}>
            <SegmentedToggle
              value={tab}
              onChange={changeTab}
              options={[
                { value: "active", label: `Active (${activeCount})` },
                { value: "upcoming", label: `Upcoming (${upcomingCount})` },
              ]}
            />
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <div style={{ position: "relative" }}>
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true" style={{
                  position: "absolute", left: 16, top: "50%", transform: "translateY(-50%)", pointerEvents: "none",
                }}>
                  <circle cx="8" cy="8" r="5.25" stroke="#8C8A84" strokeWidth="1.3" />
                  <line x1="12" y1="12" x2="16" y2="16" stroke="#8C8A84" strokeWidth="1.3" strokeLinecap="round" />
                </svg>
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onFocus={() => setSearchFocused(true)}
                  onBlur={() => setSearchFocused(false)}
                  placeholder="Search name, region, strategy"
                  style={{
                    width: isSmallScreen ? 180 : 328, boxSizing: "border-box", padding: "10px 18px 10px 42px",
                    background: "#121419",
                    border: `1px solid ${searchFocused ? "#F3A24A" : "#313234"}`,
                    borderRadius: 10,
                    fontFamily: "var(--font-sans)", fontSize: 16,
                    color: "#FBF7F3", outline: "none",
                    transition: "border-color 140ms ease",
                  }} />
              </div>
              <div ref={filterRef} style={{ position: "relative" }}>
                <button
                  type="button"
                  onClick={() => setFilterOpen((o) => !o)}
                  style={{
                    display: "inline-flex", alignItems: "center", justifyContent: "space-between", gap: 14,
                    width: isSmallScreen ? 160 : 235, boxSizing: "border-box", padding: "10px 18px", borderRadius: 10,
                    background: "#121419",
                    border: `1px solid ${filterOpen ? "#F3A24A" : "#313234"}`,
                    color: "#FBF7F3", fontFamily: "var(--font-sans)", fontSize: 16, cursor: "pointer",
                    transition: "border-color 140ms ease",
                  }}
                >
                  <span>{strategyFilter === "All" ? "All" : toSentence(strategyFilter)}</span>
                  <svg width="14" height="14" viewBox="0 0 12 12" fill="none" aria-hidden="true" style={{
                    transform: filterOpen ? "rotate(180deg)" : "none", transition: "transform 160ms ease", color: "#8C8A84",
                  }}>
                    <path d="M2.5 4.5 L6 8 L9.5 4.5" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
                {filterOpen && filterPos && createPortal(
                  <div ref={filterMenuRef} style={{
                    position: "fixed", top: filterPos.top, right: filterPos.right, minWidth: 235, zIndex: 40,
                    borderRadius: 12, border: "1px solid rgba(243,162,74,0.35)", background: "#121419",
                    boxShadow: "0 24px 60px -24px rgba(0,0,0,0.75)", padding: 6,
                  }}>
                    {STRATEGY_ORDER.map((s) => {
                      const active = strategyFilter === s;
                      return (
                        <button
                          key={s}
                          type="button"
                          onClick={() => { setStrategyFilter(s); setFilterOpen(false); }}
                          style={{
                            display: "flex", width: "100%", alignItems: "center", padding: "10px 12px", borderRadius: 8,
                            border: "none", textAlign: "left", cursor: "pointer",
                            background: active ? "rgba(243,162,74,0.12)" : "transparent",
                            color: active ? "#F3A24A" : "#C6C2BB",
                            fontFamily: "var(--font-sans)", fontSize: 15, fontWeight: active ? 500 : 400,
                          }}
                          onMouseEnter={(e) => { if (!active) (e.currentTarget.style.background = "rgba(255,255,255,0.04)"); }}
                          onMouseLeave={(e) => { if (!active) (e.currentTarget.style.background = "transparent"); }}
                        >
                          {s === "All" ? "All" : toSentence(s)}
                        </button>
                      );
                    })}
                  </div>,
                  document.body
                )}
              </div>
            </div>
          </div>
          )}
        </div>

        {tab === "active" && (
          <div>
            {!isSmallScreen && (
              <>
                <div style={{ display: "grid", gridTemplateColumns: TABLE_COLS, alignItems: "center", minHeight: 46, borderTop: "1px solid #26272B", borderBottom: "1px solid #26272B" }}>
                  <DeploymentHeadCell label="Deployment" />
                  <HeadCell label="Strategy" />
                  <HeadCell label="Deployed value" onClick={() => sortBy("deployed")} />
                  <HeadCell label="APY" onClick={() => sortBy("apy")} />
                  <HeadCell label="Share" onClick={() => sortBy("share")} />
                </div>
                {visibleActive.length === 0 && <EmptyDeployments />}
                {visibleActive.map((p: any) => (
                  <div
                    key={p.name}
                    onClick={() => { const pp = pinByName(p.name); if (pp) selectAndFly(pp); }}
                    className={`reserves-trow${selectedPin && selectedPin.name === p.name ? " is-selected" : ""}`}
                    style={{ display: "grid", gridTemplateColumns: TABLE_COLS, alignItems: "center", minHeight: 79, borderBottom: "1px solid #26272B", cursor: "pointer" }}
                  >
                    <div style={{ paddingLeft: 38, paddingRight: 12, display: "flex", flexDirection: "column", gap: 1 }}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                        <span style={{ fontFamily: "var(--font-sans)", fontSize: 12, fontWeight: 600, color: "#FBF7F3", lineHeight: "20px" }}>{p.name}</span>
                        <RegionTag code={p.region} />
                        {p.tag && (
                          <span style={{
                            fontFamily: "var(--font-sans)", fontSize: 10.56, fontWeight: 400, lineHeight: "14.08px",
                            padding: "2px 7px", borderRadius: 7.04,
                            background: `${p.tag.color}14`, border: `0.575px solid ${p.tag.color}40`, color: p.tag.color,
                          }}>{p.tag.label}</span>
                        )}
                      </span>
                      <span style={{ fontFamily: "var(--font-sans)", fontSize: 11, color: "#8C8A84", lineHeight: "20px", letterSpacing: "0.22px" }}>{p.blurb}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "center" }}><StrategyChip name={p.strategy} /></div>
                    <div className="tabular" style={{ textAlign: "center", fontFamily: "var(--font-sans)", fontSize: 12, fontWeight: 500, color: "#FBF7F3" }}>{formatDeployedValue(p.deployed)}</div>
                    <div className="tabular" style={{ textAlign: "center", fontFamily: "var(--font-sans)", fontSize: 12, color: "#F3A24A" }}>{p.apy.toFixed(1)}%</div>
                    <div className="tabular" style={{ textAlign: "center", fontFamily: "var(--font-sans)", fontSize: 12, color: "#C6C2BB" }}>{p.share.toFixed(1)}%</div>
                  </div>
                ))}
              </>
            )}
            {isSmallScreen && (
              <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 20 }}>
                <p style={{ fontFamily: "var(--font-sans)", fontSize: 12, lineHeight: "20.25px", color: "#8C8A84", margin: 0 }}>
                  Tap a card to view details and map location.
                </p>
                {visibleActive.length === 0 && <EmptyDeployments compact />}
                {visibleActive.slice(0, mobileExpanded ? undefined : MOBILE_CARD_LIMIT).map((p: any) => (
                  <button
                    key={p.name}
                    type="button"
                    onClick={() => { const pp = pinByName(p.name); if (pp) selectAndFly(pp); }}
                    style={{
                      textAlign: "left", border: "1px solid #26272B", borderRadius: 20,
                      background: selectedPin && selectedPin.name === p.name ? "rgba(243,162,74,0.08)" : "#13151A",
                      padding: "20px", color: "inherit",
                    }}
                  >
                    {/* Header: name + region badge, chevron right (Figma 6667-40093) */}
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 6, minWidth: 0, flexWrap: "wrap" }}>
                        <span style={{ color: "#FBF7F3", fontWeight: 600, fontSize: 14 }}>{p.name}</span>
                        <RegionTag code={p.region} />
                      </span>
                      <span style={{ color: "#8C8A84", flexShrink: 0, fontSize: 18, lineHeight: 1 }} aria-hidden>›</span>
                    </div>
                    <div style={{ marginTop: 8, fontSize: 12, color: "#8C8A84", lineHeight: "15px", letterSpacing: "0.24px" }}>{p.blurb}</div>
                    <div style={{ height: 1, background: "#26272B", margin: "18px 0" }} />
                    {/* 2×2 labelled metrics */}
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "15px 16px" }}>
                      <ReserveCardMetric label="Strategy"><StrategyChip name={p.strategy} /></ReserveCardMetric>
                      <ReserveCardMetric label="Deployed value">
                        <span className="tabular" style={{ fontSize: 14, color: "#FBF7F3", fontWeight: 500 }}>{formatDeployedValue(p.deployed)}</span>
                      </ReserveCardMetric>
                      <ReserveCardMetric label="APY">
                        <span className="tabular" style={{ fontSize: 14, color: "#F3A24A", fontWeight: 500 }}>{p.apy.toFixed(1)}%</span>
                      </ReserveCardMetric>
                      <ReserveCardMetric label="Share">
                        <span className="tabular" style={{ fontSize: 14, color: "#C6C2BB", fontWeight: 500 }}>{p.share.toFixed(1)}%</span>
                      </ReserveCardMetric>
                    </div>
                  </button>
                ))}
                {visibleActive.length > MOBILE_CARD_LIMIT && (
                  <button
                    type="button"
                    onClick={() => setMobileExpanded((v) => !v)}
                    style={{
                      display: "flex", alignItems: "center", justifyContent: "center",
                      width: "100%", height: 47, borderRadius: 20, border: "1px solid #26272B",
                      background: "#13151A", color: "#C6C2BB",
                      fontFamily: "var(--font-sans)", fontSize: 13, fontWeight: 500, cursor: "pointer",
                    }}
                  >
                    {mobileExpanded ? "Show less" : "Show more"}
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {tab === "upcoming" && (
          <div>
            {!isSmallScreen && (
              <>
                <div style={{ display: "grid", gridTemplateColumns: TABLE_COLS, alignItems: "center", minHeight: 46, borderTop: "1px solid #26272B", borderBottom: "1px solid #26272B" }}>
                  <DeploymentHeadCell label="Deployment" />
                  <HeadCell label="Strategy" />
                  <HeadCell label="Deployed value" onClick={() => sortBy("reserved")} />
                  <HeadCell label="APY" onClick={() => sortBy("live")} />
                  <HeadCell label="Share" onClick={() => sortBy("share")} />
                </div>
                {visibleUpcoming.length === 0 && <EmptyDeployments />}
                {visibleUpcoming.map((u: any) => (
                  <div
                    key={u.name}
                    onClick={() => { const p = pinByName(u.name); if (p) selectAndFly(p); }}
                    className={`reserves-trow${selectedPin && selectedPin.name === u.name ? " is-selected" : ""}`}
                    style={{ display: "grid", gridTemplateColumns: TABLE_COLS, alignItems: "center", minHeight: 79, borderBottom: "1px solid #26272B", cursor: "pointer" }}
                  >
                    <div style={{ paddingLeft: 38, paddingRight: 12, display: "flex", flexDirection: "column", gap: 6 }}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                        <span style={{ fontFamily: "var(--font-sans)", fontSize: 12, fontWeight: 600, color: "#FBF7F3", lineHeight: "20px" }}>{u.name}</span>
                        <RegionTag code={u.region} />
                      </span>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                        {[0, 1, 2, 3, 4].map((j) => (
                          <span key={j} style={{ width: 14, height: 2, background: j < u.phaseStep ? "#F3A24A" : "#26272B", borderRadius: 1 }} />
                        ))}
                        <span style={{ fontFamily: "var(--font-sans)", fontSize: 10, color: "#8C8A84", letterSpacing: "0.08em" }}>{u.phase}</span>
                      </span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "center" }}><StrategyChip name={u.strategy} /></div>
                    <div className="tabular" style={{ textAlign: "center", fontFamily: "var(--font-sans)", fontSize: 12, fontWeight: 500, color: "#FBF7F3" }}>{formatDeployedValue(u.reserved)}</div>
                    <div className="tabular" style={{ textAlign: "center", fontFamily: "var(--font-sans)", fontSize: 12, color: "#C6C2BB" }}>{u.live}</div>
                    <div className="tabular" style={{ textAlign: "center", fontFamily: "var(--font-sans)", fontSize: 12, color: "#C6C2BB" }}>{u.share.toFixed(1)}%</div>
                  </div>
                ))}
              </>
            )}
            {isSmallScreen && (
              <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 20 }}>
                <p style={{ fontFamily: "var(--font-sans)", fontSize: 12, lineHeight: "20.25px", color: "#8C8A84", margin: 0 }}>
                  Tap a card to view details and map location.
                </p>
                {visibleUpcoming.length === 0 && <EmptyDeployments compact />}
                {visibleUpcoming.slice(0, mobileExpanded ? undefined : MOBILE_CARD_LIMIT).map((u: any) => (
                  <button
                    key={u.name}
                    type="button"
                    onClick={() => { const p = pinByName(u.name); if (p) selectAndFly(p); }}
                    style={{
                      textAlign: "left", border: "1px solid #26272B", borderRadius: 20,
                      background: selectedPin && selectedPin.name === u.name ? "rgba(243,162,74,0.08)" : "#13151A",
                      padding: "20px", color: "inherit",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 6, minWidth: 0, flexWrap: "wrap" }}>
                        <span style={{ color: "#FBF7F3", fontWeight: 600, fontSize: 14 }}>{u.name}</span>
                        <RegionTag code={u.region} />
                      </span>
                      <span style={{ color: "#8C8A84", flexShrink: 0, fontSize: 18, lineHeight: 1 }} aria-hidden>›</span>
                    </div>
                    {/* Phase progress (Figma upcoming card 6667-41865) */}
                    <div style={{ marginTop: 10, display: "inline-flex", alignItems: "center", gap: 7 }}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                        {[0, 1, 2, 3, 4].map((j) => (
                          <span key={j} style={{ width: 12, height: 3, borderRadius: 1, background: j < u.phaseStep ? "linear-gradient(90deg, #f1994f, #e84066)" : "#2B2B2B" }} />
                        ))}
                      </span>
                      <span style={{ fontFamily: "var(--font-sans)", fontSize: 12, lineHeight: "20px", color: "#8C8A84" }}>{u.phase}</span>
                    </div>
                    <div style={{ height: 1, background: "#26272B", margin: "18px 0" }} />
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "15px 16px" }}>
                      <ReserveCardMetric label="Strategy"><StrategyChip name={u.strategy} /></ReserveCardMetric>
                      <ReserveCardMetric label="Reserved">
                        <span className="tabular" style={{ fontSize: 14, color: "#FBF7F3", fontWeight: 500 }}>{formatDeployedValue(u.reserved)}</span>
                      </ReserveCardMetric>
                      <ReserveCardMetric label="Est. GO-LIVE">
                        <span className="tabular" style={{ fontSize: 14, color: "#FBF7F3", fontWeight: 500 }}>{u.live}</span>
                      </ReserveCardMetric>
                      <ReserveCardMetric label="Share">
                        <span className="tabular" style={{ fontSize: 14, color: "#FBF7F3", fontWeight: 500 }}>{u.share.toFixed(1)}%</span>
                      </ReserveCardMetric>
                    </div>
                  </button>
                ))}
                {visibleUpcoming.length > MOBILE_CARD_LIMIT && (
                  <button
                    type="button"
                    onClick={() => setMobileExpanded((v) => !v)}
                    style={{
                      display: "flex", alignItems: "center", justifyContent: "center",
                      width: "100%", height: 47, borderRadius: 20, border: "1px solid #26272B",
                      background: "#13151A", color: "#C6C2BB",
                      fontFamily: "var(--font-sans)", fontSize: 13, fontWeight: 500, cursor: "pointer",
                    }}
                  >
                    {mobileExpanded ? "Show less" : "Show more"}
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* Pagination — only renders if rows exceed page size (currently never). */}
        {((tab === "active" && visibleActive.length > 10) ||
          (tab === "upcoming" && visibleUpcoming.length > 10)) && (
          <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", padding: "18px 22px", gap: 8 }}>
            <GradientButton size="sm" style={{ width: 32, height: 32, padding: 0 }}>1</GradientButton>
            <button className="btn btn-ghost btn-sm">Next ›</button>
            <button className="btn btn-ghost btn-sm">Last »</button>
          </div>
        )}
      </div>
    </div>
  );
}

export default ReservesScreen;
export { ReservesScreen as MidnightReservesPage };
