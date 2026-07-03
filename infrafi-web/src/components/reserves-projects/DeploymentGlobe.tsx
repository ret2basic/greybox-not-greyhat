'use client';

// ============================================================
// Reserves & Projects — interactive orthographic globe
// ============================================================
import { useState, useMemo, useRef, useEffect, startTransition } from 'react';
import { WORLD_COUNTRIES } from './world-data/world-countries';
import { WORLD_LAND_POLYS } from './world-data/world-land';

// ── World coastline / country data ───────────────────────────────
// Countries from Natural Earth 50m via world-atlas.
// window.WORLD_COUNTRIES = [{ id, name, polys: [[ring, ring, ...], ...] }]
const COUNTRIES: any[] = WORLD_COUNTRIES || [];
// World land outline (continents) — used under the countries to give a clean
// coast silhouette without drawing every country-vs-country border.
const WORLD_POLYS: any[] = WORLD_LAND_POLYS || [];

// Compute each country's "main body" centroid + fit zoom by picking the LARGEST
// polygon (by signed area, in lng/lat space) and using its bbox center. This
// avoids overseas-territory pull (France→French Guiana, USA→Alaska/Hawaii,
// Netherlands→Caribbean, Norway→Svalbard, etc.) — the camera lands on the
// mainland the user actually sees.
function ringArea(ring: any) {
  let a = 0;
  for (let i = 0, n = ring.length; i < n; i++) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[(i + 1) % n];
    a += x1 * y2 - x2 * y1;
  }
  return Math.abs(a) / 2;
}
const COUNTRY_META: any[] = COUNTRIES.map((c: any) => {
  // Find the largest polygon (by outer-ring area)
  let bestPoly: any = null, bestArea = -1;
  for (const poly of c.polys) {
    if (!poly[0] || poly[0].length < 3) continue;
    const a = ringArea(poly[0]);
    if (a > bestArea) { bestArea = a; bestPoly = poly; }
  }
  // Fallback if no valid polys (shouldn't happen)
  const ring = bestPoly ? bestPoly[0] : [[0, 0]];
  // Compute bbox of THE LARGEST polygon only
  let mnL = Infinity, mxL = -Infinity, mnLa = Infinity, mxLa = -Infinity;
  for (const [lng, lat] of ring) {
    if (lng < mnL) mnL = lng; if (lng > mxL) mxL = lng;
    if (lat < mnLa) mnLa = lat; if (lat > mxLa) mxLa = lat;
  }
  let lngSpan = mxL - mnL;
  let centerLng = (mnL + mxL) / 2;
  // Antimeridian: a single polygon spanning >180° is the largest landmass
  // crossing the dateline (Russia's mainland, Fiji, etc.). Recompute in 0..360.
  if (lngSpan > 180) {
    let mnL2 = Infinity, mxL2 = -Infinity;
    for (const [lng] of ring) {
      const w = lng < 0 ? lng + 360 : lng;
      if (w < mnL2) mnL2 = w; if (w > mxL2) mxL2 = w;
    }
    let c2 = (mnL2 + mxL2) / 2;
    centerLng = c2 > 180 ? c2 - 360 : c2;
    lngSpan = mxL2 - mnL2;
  }
  const latSpan = mxLa - mnLa;
  const centerLat = (mnLa + mxLa) / 2;
  // Fit zoom: bigger span should occupy ~60% of disc width.
  const maxSpan = Math.max(lngSpan * Math.cos(centerLat * Math.PI / 180), latSpan);
  const fitZoom = Math.max(1.4, Math.min(10, 110 / Math.max(8, maxSpan)));
  return { ...c, centerLng, centerLat, lngSpan, latSpan, fitZoom };
});

// Convert lat/lng to 3D unit-sphere coords, then project orthographically.
// Returns [x,y,visible] in viewBox space; visible=false if behind globe.
// rotLng = longitude of view center; rotLat = latitude of view center (tilt).
function project(lng: number, lat: number, rotLng: number, rotLat: number, R: number, cx: number, cy: number): [number, number, boolean] {
  const φ = lat * Math.PI / 180;
  const λ = (lng - rotLng) * Math.PI / 180;
  const φ0 = rotLat * Math.PI / 180;
  // Rotate so view center sits at (0,0,1)
  const x0 = Math.cos(φ) * Math.sin(λ);
  const y0 = Math.sin(φ);
  const z0 = Math.cos(φ) * Math.cos(λ);
  const x = x0;
  const y = y0 * Math.cos(φ0) - z0 * Math.sin(φ0);
  const z = y0 * Math.sin(φ0) + z0 * Math.cos(φ0);
  return [cx + R * x, cy - R * y, z > 0];
}

// Project a single point. Returns { x, y, vis, x3, y3, z3 } — 3D unit-sphere coords too,
// so callers can interpolate horizon crossings.
function project3(lng: number, lat: number, rotLng: number, rotLat: number) {
  const φ = lat * Math.PI / 180;
  const λ = (lng - rotLng) * Math.PI / 180;
  const φ0 = rotLat * Math.PI / 180;
  const x0 = Math.cos(φ) * Math.sin(λ);
  const y0 = Math.sin(φ);
  const z0 = Math.cos(φ) * Math.cos(λ);
  return {
    x3: x0,
    y3: y0 * Math.cos(φ0) - z0 * Math.sin(φ0),
    z3: y0 * Math.sin(φ0) + z0 * Math.cos(φ0),
  };
}

// Build a polygon path in screen space, properly clipped to the visible hemisphere.
// Approach: walk the ring as a stream of events. Each edge of the polygon either
// (a) stays visible — emit a line-to,
// (b) stays hidden — skip,
// (c) exits — emit line-to-horizon-point, then push the exit-theta onto a stack,
// (d) enters — pop the matching exit-theta, sample horizon arc to here.
// We start at any vertex; if the polygon is entirely visible, no horizon work needed.
// If we end with a pending exit, we close it with the FIRST entry's theta — this
// handles polygons with multiple crossings as long as we treat the ring as cyclic.
function polyPath(poly: any, rotLng: number, rotLat: number, R: number, cx: number, cy: number) {
  const N = poly.length;
  if (N < 3) return { d: "", crossed: false };
  const pts3 = poly.map(([lng, lat]: [number, number]) => project3(lng, lat, rotLng, rotLat));

  // Quick bail: all hidden → empty
  let anyVisible = false;
  let allVisible = true;
  for (const p of pts3) {
    if (p.z3 > 0) anyVisible = true;
    else allVisible = false;
  }
  if (!anyVisible) return { d: "", crossed: false };

  // All visible: simple ring
  if (allVisible) {
    let d = "";
    for (let i = 0; i < N; i++) {
      const p = pts3[i];
      d += (i === 0 ? "M" : "L") + (cx + R * p.x3).toFixed(1) + " " + (cy - R * p.y3).toFixed(1);
    }
    return { d: d + " Z", crossed: false };
  }

  // Crossing case: rotate the start so we begin at a HIDDEN→VISIBLE transition.
  // This guarantees the first emitted point is an entry, the path opens cleanly,
  // and any pending exit at the end pairs back to the first entry.
  let startIdx = -1;
  for (let i = 0; i < N; i++) {
    const a = pts3[i], b = pts3[(i + 1) % N];
    if (a.z3 <= 0 && b.z3 > 0) { startIdx = (i + 1) % N; break; }
  }
  if (startIdx === -1) return { d: "", crossed: true }; // shouldn't happen given anyVisible && !allVisible

  const horizonPt = (theta: number) => ({ x: cx + R * Math.cos(theta), y: cy - R * Math.sin(theta) });
  const horizonTheta = (a: any, b: any) => {
    const t = a.z3 / (a.z3 - b.z3);
    const x = a.x3 + (b.x3 - a.x3) * t;
    const y = a.y3 + (b.y3 - a.y3) * t;
    const len = Math.hypot(x, y) || 1;
    return Math.atan2(y / len, x / len);
  };
  const sampleArc = (theta1: number, theta2: number) => {
    let dt = theta2 - theta1;
    while (dt > Math.PI) dt -= 2 * Math.PI;
    while (dt <= -Math.PI) dt += 2 * Math.PI;
    // Higher density at high zoom — limb arcs are visible at full size when
    // the globe fills the viewport, so 1° sampling avoids visible facets.
    const steps = Math.max(2, Math.ceil(Math.abs(dt) / (Math.PI / 180)));
    const out = [];
    for (let s = 1; s <= steps; s++) {
      const th = theta1 + (dt * s / steps);
      out.push(horizonPt(th));
    }
    return out;
  };

  // First pending entry theta — used to close the loop if we end on an exit
  let firstEntryTheta: number | null = null;
  let pendingExitTheta: number | null = null;
  let d = "";

  // Emit the entry point at startIdx (which we know is the visible vertex right
  // after a hidden→visible transition).
  {
    const a = pts3[(startIdx - 1 + N) % N], b = pts3[startIdx];
    const theta = horizonTheta(a, b);
    firstEntryTheta = theta;
    const hp = horizonPt(theta);
    d += "M" + hp.x.toFixed(1) + " " + hp.y.toFixed(1);
  }

  // Walk N edges starting from startIdx. At each step we examine vertex pts3[i]
  // (the destination of edge from prev to cur).
  let prev = pts3[(startIdx - 1 + N) % N];
  for (let k = 0; k < N; k++) {
    const i = (startIdx + k) % N;
    const cur = pts3[i];
    const prevVis = prev.z3 > 0;
    const curVis = cur.z3 > 0;

    if (prevVis && curVis) {
      // Both visible: line to cur
      d += "L" + (cx + R * cur.x3).toFixed(1) + " " + (cy - R * cur.y3).toFixed(1);
    } else if (prevVis && !curVis) {
      // Exit: line to horizon, record exit theta
      pendingExitTheta = horizonTheta(prev, cur);
      const ep = horizonPt(pendingExitTheta);
      d += "L" + ep.x.toFixed(1) + " " + ep.y.toFixed(1);
    } else if (!prevVis && curVis) {
      // Entry: walk horizon from pendingExitTheta to entry, then line to cur
      const entryTheta = horizonTheta(prev, cur);
      if (pendingExitTheta !== null) {
        for (const p of sampleArc(pendingExitTheta, entryTheta)) {
          d += "L" + p.x.toFixed(1) + " " + p.y.toFixed(1);
        }
        pendingExitTheta = null;
      }
      d += "L" + (cx + R * cur.x3).toFixed(1) + " " + (cy - R * cur.y3).toFixed(1);
    }
    // else both hidden: skip

    prev = cur;
  }

  // If we ended with a pending exit, close along horizon back to the first entry
  if (pendingExitTheta !== null && firstEntryTheta !== null) {
    for (const p of sampleArc(pendingExitTheta, firstEntryTheta)) {
      d += "L" + p.x.toFixed(1) + " " + p.y.toFixed(1);
    }
  }

  return { d: d + " Z", crossed: true };
}

// Lat/lng grid (graticule) lines
function GraticuleSphere({ rotLng, rotLat, R, cx, cy, color }: { rotLng: number; rotLat: number; R: number; cx: number; cy: number; color: string }) {
  const lines: any[] = [];
  // Meridians (lng lines) every 30°
  for (let lng = -180; lng < 180; lng += 30) {
    const pts = [];
    for (let lat = -85; lat <= 85; lat += 5) {
      const [x, y, vis] = project(lng, lat, rotLng, rotLat, R, cx, cy);
      pts.push({ x, y, vis });
    }
    let cur: any[] = [];
    for (const p of pts) {
      if (p.vis) cur.push([p.x, p.y]);
      else if (cur.length) { lines.push(cur); cur = []; }
    }
    if (cur.length) lines.push(cur);
  }
  // Parallels (lat lines) every 30°
  for (let lat = -60; lat <= 60; lat += 30) {
    const pts = [];
    for (let lng = -180; lng <= 180; lng += 5) {
      const [x, y, vis] = project(lng, lat, rotLng, rotLat, R, cx, cy);
      pts.push({ x, y, vis });
    }
    let cur: any[] = [];
    for (const p of pts) {
      if (p.vis) cur.push([p.x, p.y]);
      else if (cur.length) { lines.push(cur); cur = []; }
    }
    if (cur.length) lines.push(cur);
  }
  return (
    <g stroke={color} strokeWidth="0.5" fill="none" opacity="0.3">
      {lines.map((seg, i) => (
        <path key={i} d={seg.map((p: any, j: number) => `${j ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ")} />
      ))}
    </g>
  );
}

// ── The Globe ────────────────────────────────────────────────────
// Real deployment cities — lat/lng, named explicitly.
// `active` cities are larger, pulse, and connect with arcs.
//
// Some projects expose a `buildings` array — when present, the project detail
// panel shows a "View buildings" button that swaps the globe out for a list
// of buildings; clicking a building drops into the asset visualizer.
//
// Buildings have: id, name, address, units, accessType, mdfPlacement, status.
// accessType maps to keys in window.ACCESS_TYPES (gpon, ethernet, coax,
// hallway). mdfPlacement is "basement" | "roof".
export const DEPLOYMENTS: any[] = [
  // ── USA mainland ────────────────────────────────────────────────
  { name: "Great Falls, MT", city: "GreatFalls", region: "USA", lng: -111.3, lat: 47.5, label: "Acquisition · Glacier Connect", value: 5.0, status: "active" },
  { name: "Twin Cities", city: "Minneapolis", region: "USA", lng: -93.3, lat: 44.95, label: "FTTP · Active", value: 4.2, status: "active" },
  { name: "Boston Metro", city: "Boston", region: "USA", lng: -71.06, lat: 42.36, label: "Cellular · Active 7.9%", value: 6.1, status: "active" },
  { name: "Ohio River Valley", city: "Cincinnati", region: "USA", lng: -82.5, lat: 39.0, label: "Fiber · Q4 2029", value: 12.0, status: "upcoming" },
  { name: "NM High Plains", city: "Albuquerque", region: "USA", lng: -104.5, lat: 34.5, label: "Deployment · Q3 2028", value: 10.5, status: "upcoming" },
  { name: "Houston Urban", city: "Houston", region: "USA", lng: -95.37, lat: 29.76, label: "Cellular · Q1 2026", value: 3.0, status: "upcoming" },
  { name: "Appalachian FTTP", city: "Knoxville", region: "USA", lng: -82.0, lat: 36.5, label: "Build-Out · Q1 2027", value: 7.0, status: "upcoming" },
  { name: "Pacific NW", city: "Seattle", region: "USA", lng: -122.6, lat: 47.6, label: "Backbone · diligence", value: 2.5, status: "diligence" },

  // ── NYC metro: 3 in NYC + 1 in Jersey City (different cities) ───
  { name: "Manhattan FTTP", city: "NewYork", region: "USA", lng: -73.97, lat: 40.78, label: "Fiber · Active 8.4%", value: 14.0, status: "active",
    buildings: [
      { id: "mh-01", name: "Liberty Tower", address: "200 Park Ave · Midtown East", units: 384, floors: 14, accessType: "gpon", mdfPlacement: "basement", subscribers: 318, uptime: "99.96%" },
      { id: "mh-02", name: "Hudson Yards 50", address: "50 Hudson Yards · Chelsea", units: 256, floors: 14, accessType: "ethernet", mdfPlacement: "basement", subscribers: 214, uptime: "99.94%" },
      { id: "mh-03", name: "The Vanderbilt", address: "418 Madison Ave · Midtown", units: 192, floors: 14, accessType: "coax", mdfPlacement: "basement", subscribers: 176, uptime: "99.91%" },
      { id: "mh-04", name: "SoHo Mercer", address: "127 Mercer St · SoHo", units: 96, floors: 14, accessType: "hallway", mdfPlacement: "basement", subscribers: 84, uptime: "99.97%" },
      { id: "mh-05", name: "Tribeca Heights", address: "88 Greenwich St · Tribeca", units: 142, floors: 14, accessType: "ethernet", mdfPlacement: "roof", subscribers: 121, uptime: "99.93%" },
      { id: "mh-06", name: "Battery Wharf", address: "17 State St · Financial District", units: 220, floors: 14, accessType: "gpon", mdfPlacement: "roof", subscribers: 198, uptime: "99.98%" },
    ],
  },
  { name: "Brooklyn Backbone", city: "NewYork", region: "USA", lng: -73.95, lat: 40.65, label: "Backhaul · Active", value: 6.5, status: "active" },
  { name: "Queens 5G Mesh", city: "NewYork", region: "USA", lng: -73.79, lat: 40.73, label: "Cellular · Q2 2027", value: 8.2, status: "upcoming" },
  { name: "Jersey City Edge", city: "JerseyCity", region: "USA", lng: -74.05, lat: 40.72, label: "Edge compute · diligence", value: 3.4, status: "diligence" },

  // ── SF Bay: SF, Oakland, San Jose (3 different cities) ──────────
  { name: "SF Mission Fiber", city: "SanFrancisco", region: "USA", lng: -122.42, lat: 37.76, label: "FTTP · Q3 2026", value: 9.1, status: "upcoming" },
  { name: "Oakland Backhaul", city: "Oakland", region: "USA", lng: -122.27, lat: 37.80, label: "Backbone · Active", value: 5.2, status: "active" },
  { name: "South Bay Wireless", city: "SanJose", region: "USA", lng: -121.89, lat: 37.34, label: "Fixed wireless · diligence", value: 2.8, status: "diligence" },

  // ── Latin America ───────────────────────────────────────────────
  { name: "Mexico City", city: "MexicoCity", region: "MEX", lng: -99.13, lat: 19.43, label: "5G mesh · Q2 2027", value: 5.5, status: "upcoming" },
  { name: "São Paulo", city: "SaoPaulo", region: "BRA", lng: -46.63, lat: -23.55, label: "Fiber · diligence", value: 8.0, status: "diligence" },

  // ── London: 2 in central London + 1 in greater London ──────────
  { name: "London City Fiber", city: "London", region: "GBR", lng: -0.13, lat: 51.51, label: "Backhaul · Q3 2027", value: 9.0, status: "upcoming" },
  { name: "Canary Wharf", city: "London", region: "GBR", lng: -0.02, lat: 51.50, label: "FTTP · diligence", value: 4.5, status: "diligence" },
  { name: "Greater London", city: "London", region: "GBR", lng: -0.34, lat: 51.55, label: "Cellular · Active", value: 7.2, status: "active" },

  // ── Frankfurt cluster (same city) ───────────────────────────────
  { name: "Frankfurt CIX", city: "Frankfurt", region: "DEU", lng: 8.68, lat: 50.11, label: "Peering · Active", value: 11.4, status: "active" },
  { name: "Frankfurt Edge", city: "Frankfurt", region: "DEU", lng: 8.74, lat: 50.05, label: "Edge compute · Q4 2026", value: 5.8, status: "upcoming" },

  // ── Africa / Asia ───────────────────────────────────────────────
  { name: "Lagos", city: "Lagos", region: "NGA", lng: 3.38, lat: 6.45, label: "Fixed wireless · diligence", value: 4.0, status: "diligence" },
  { name: "Mumbai", city: "Mumbai", region: "IND", lng: 72.87, lat: 19.07, label: "Cellular · Q4 2027", value: 11.0, status: "upcoming" },
  { name: "Manila", city: "Manila", region: "PHL", lng: 120.98, lat: 14.6, label: "Fiber · diligence", value: 3.5, status: "diligence" },
  { name: "Tokyo Bay", city: "Tokyo", region: "JPN", lng: 139.65, lat: 35.68, label: "Backhaul partner", value: 6.8, status: "active" },

  // ── Singapore: 3 in same city ───────────────────────────────────
  { name: "Singapore CBD", city: "Singapore", region: "SGP", lng: 103.85, lat: 1.29, label: "Submarine landing · Active", value: 13.2, status: "active" },
  { name: "Jurong DC", city: "Singapore", region: "SGP", lng: 103.71, lat: 1.32, label: "DC backhaul · Q2 2026", value: 7.8, status: "upcoming" },
  { name: "Changi Edge", city: "Singapore", region: "SGP", lng: 103.99, lat: 1.36, label: "Edge node · diligence", value: 2.4, status: "diligence" },
];

// Status colors — module-level so both Globe and ReservesScreen can reach them.
export const STATUS_COLORS: any = {
  active: "#F3A24A",
  upcoming: "#EA5270",
  diligence: "rgba(220,200,255,0.5)",
};

// Friendly "City, State, Country" derivation from deployment metadata.
export const COUNTRY_NAMES: any = {
  USA: "United States", MEX: "Mexico", BRA: "Brazil", GBR: "United Kingdom",
  DEU: "Germany", NGA: "Nigeria", IND: "India", PHL: "Philippines",
  JPN: "Japan", SGP: "Singapore",
};
export const CITY_LOCATIONS: any = {
  GreatFalls: { city: "Great Falls", state: "MT" },
  Minneapolis: { city: "Minneapolis", state: "MN" },
  Boston: { city: "Boston", state: "MA" },
  Cincinnati: { city: "Cincinnati", state: "OH" },
  Albuquerque: { city: "Albuquerque", state: "NM" },
  Houston: { city: "Houston", state: "TX" },
  Knoxville: { city: "Knoxville", state: "TN" },
  Seattle: { city: "Seattle", state: "WA" },
  NewYork: { city: "New York", state: "NY" },
  JerseyCity: { city: "Jersey City", state: "NJ" },
  SanFrancisco: { city: "San Francisco", state: "CA" },
  Oakland: { city: "Oakland", state: "CA" },
  SanJose: { city: "San Jose", state: "CA" },
  MexicoCity: { city: "Mexico City" },
  SaoPaulo: { city: "São Paulo" },
  London: { city: "London" },
  Frankfurt: { city: "Frankfurt" },
  Lagos: { city: "Lagos" },
  Mumbai: { city: "Mumbai" },
  Manila: { city: "Manila" },
  Tokyo: { city: "Tokyo" },
  Singapore: { city: "Singapore" },
};
export function locationLabel(pin: any) {
  const loc = CITY_LOCATIONS[pin.city] || {};
  // Show region only — "State · Country", or just "Country" when there's no
  // state. The city is intentionally omitted. Prefer the pin's own fields
  // (set by the API → pin adapters); fall back to the v5 demo lookups so
  // standalone demo pins still render.
  const state = pin.state || loc.state;
  const country = pin.country || COUNTRY_NAMES[pin.region] || pin.region;
  const parts = [];
  if (state) parts.push(state);
  if (country) parts.push(country);
  return parts.join(" · ").toUpperCase();
}

// Format a deployed/reserved value (stored in $K) for display. At/above
// $0.1K we keep the compact "$X.XK" form; below that, the rounding to "$0.1K"
// hides the real figure, so show exact dollars instead (e.g. 0.06 → "$60").
export function formatDeployedValue(valueK: number): string {
  if (!Number.isFinite(valueK)) return "$0";
  if (valueK >= 0.1) return `$${valueK.toFixed(1)}K`;
  return `$${Math.round(valueK * 1000).toLocaleString()}`;
}

interface DeploymentGlobeProps {
  hoverIdx: any;
  setHoverIdx: any;
  selectedPin: any;
  onSelectPin: any;
  flyToken: any;
  // Optional override — when present, replaces the hardcoded DEPLOYMENTS
  // demo array with real data passed from above (e.g. derived from the
  // projects API). Same shape as v5's DEPLOYMENTS entries.
  deployments?: any[];
}

export function DeploymentGlobe({ hoverIdx, setHoverIdx, selectedPin, onSelectPin, flyToken, deployments: deploymentsProp }: DeploymentGlobeProps) {
  // Use the override when supplied; otherwise fall back to the hardcoded
  // demo deployments. Keeps v5 verbatim behaviour intact when used standalone.
  const ACTIVE_DEPLOYMENTS = deploymentsProp ?? DEPLOYMENTS;
  const W = 720, H = 520;
  const cx = W / 2, cy = H / 2;
  // Hover/pin keys are CLUSTER ids (string) — not pin idx — because clusters
  // re-form at every zoom. The parent's hoverIdx is kept in sync so the legend
  // works, but the source of truth here is hoverCluster / pinnedCluster.
  const [hoverCluster, setHoverCluster] = useState<any>(null);   // cluster id
  const [pinnedCluster, setPinnedCluster] = useState<any>(null); // cluster id (sticky)
  const [hoveredMemberIdx, setHoveredMemberIdx] = useState<any>(null); // pin idx of row being hovered in the popup list
  const [isSmallScreen, setIsSmallScreen] = useState(false);
  const R = 220;

  const [rotLng, setRotLng] = useState(-90); // start centered on Americas
  const [rotLat, setRotLat] = useState(20);  // slight northern tilt
  const [zoom, setZoom] = useState(1);
  const [dragging, setDragging] = useState(false);
  const [autoSpin, setAutoSpin] = useState(true);
  const [hoverCountry, setHoverCountry] = useState<any>(null); // index into COUNTRY_META
  const [selectedCountry, setSelectedCountry] = useState<any>(null);
  const [animTarget, setAnimTarget] = useState<any>(null); // { rotLng, rotLat, zoom, startedAt, from: { rotLng, rotLat, zoom } }
  const dragStart = useRef<any>({ x: 0, y: 0, rotLng: 0, rotLat: 0 });
  const rafRef = useRef<any>(null);
  const lastT = useRef<any>(0);

  const Reff = R * zoom;

  useEffect(() => {
    const media = window.matchMedia('(max-width: 1024px)');
    const sync = () => setIsSmallScreen(media.matches);
    sync();
    media.addEventListener('change', sync);
    return () => media.removeEventListener('change', sync);
  }, []);

  // Auto-spin animation — paused while animTarget is active.
  //
  // setRotLng must be wrapped in React.startTransition. Without it,
  // 60 high-priority state updates per second from this RAF loop
  // STARVE React 18's transition lane — meaning router.push (which
  // uses startTransition under the hood for client-side nav) can't
  // commit while this loop is running. Symptom: clicking any TopNav
  // link from the reserves page hangs indefinitely until something
  // pauses the spin (animTarget set, drag started, etc.).
  // Wrapping marks the spin updates as low-priority so they yield
  // to navigation and other user interactions.
  useEffect(() => {
    if (!autoSpin || dragging || animTarget) return;
    let mounted = true;
    const tick = (t: number) => {
      if (!mounted) return;
      const dt = lastT.current ? (t - lastT.current) : 16;
      lastT.current = t;
      startTransition(() => {
        setRotLng(r => r - dt * 0.012);
      });
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => { mounted = false; cancelAnimationFrame(rafRef.current); lastT.current = 0; };
  }, [autoSpin, dragging, animTarget]);

  // Camera tween — runs while animTarget is set
  useEffect(() => {
    if (!animTarget) return;
    let mounted = true;
    const DUR = 850;
    const ease = (t: number) => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; // ease-in-out quad
    // Pick the SHORT longitude path (handles -180/+180 wrap)
    let dLng = animTarget.rotLng - animTarget.from.rotLng;
    while (dLng > 180) dLng -= 360;
    while (dLng < -180) dLng += 360;
    const tick = (t: number) => {
      if (!mounted) return;
      const elapsed = t - animTarget.startedAt;
      const k = Math.min(1, elapsed / DUR);
      const e = ease(k);
      setRotLng(animTarget.from.rotLng + dLng * e);
      setRotLat(animTarget.from.rotLat + (animTarget.rotLat - animTarget.from.rotLat) * e);
      setZoom(animTarget.from.zoom + (animTarget.zoom - animTarget.from.zoom) * e);
      if (k < 1) rafRef.current = requestAnimationFrame(tick);
      else setAnimTarget(null);
    };
    animTarget.startedAt = performance.now();
    rafRef.current = requestAnimationFrame(tick);
    return () => { mounted = false; cancelAnimationFrame(rafRef.current); };
  }, [animTarget]);

  const flyTo = (targetLng: number, targetLat: number, targetZoom: number) => {
    setAutoSpin(false);
    setAnimTarget({
      rotLng: targetLng,
      rotLat: targetLat,
      zoom: targetZoom,
      from: { rotLng, rotLat, zoom },
      startedAt: 0,
    });
  };

  // External fly trigger: parent bumps `flyToken` whenever something outside
  // the globe (e.g. a table row click) wants the camera to swing onto a pin.
  const lastFlyToken = useRef<any>(flyToken);
  useEffect(() => {
    if (flyToken === lastFlyToken.current) return;
    lastFlyToken.current = flyToken;
    if (!selectedPin) return;
    // Need to know the city to use the explode-zoom helper, but that helper
    // is defined later in this component — use the same math inline here.
    // (It's the same `explodeZoomForCity` body, applied after cityGroups is
    // available. The closure picks up the latest function reference.)
    const fn = explodeZoomForCityRef.current;
    if (!fn) return;
    const z = fn(selectedPin.city);
    flyTo(selectedPin.lng, selectedPin.lat, z);
  }, [flyToken]);

  // Stash explodeZoomForCity in a ref so the effect above can use it without
  // hoisting concerns.
  const explodeZoomForCityRef = useRef<any>(null);

  // Drag handlers — drag right = world spins right; drag down = tilt south
  const onMouseDown = (e: any) => {
    setAutoSpin(false);
    dragStart.current = { x: e.clientX, y: e.clientY, rotLng, rotLat, moved: false };
    // past a small threshold. This lets clicks on country paths through.
    const onMove = (ev: any) => {
      const dx = ev.clientX - dragStart.current.x;
      const dy = ev.clientY - dragStart.current.y;
      if (!dragStart.current.moved && Math.hypot(dx, dy) < 6) return;
      dragStart.current.moved = true;
      setDragging(true);
      setAnimTarget(null); // cancel any in-flight fly-to
      setPinnedCluster(null); // dragging dismisses pinned tooltip
      // Scale pan speed inverse to zoom — feels constant on screen
      const k = 0.4 / zoom;
      setRotLng(dragStart.current.rotLng - dx * k);
      setRotLat(Math.max(-85, Math.min(85, dragStart.current.rotLat + dy * k)));
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      setDragging(false);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };
  const onMouseMove = () => {}; // legacy no-op
  const onMouseUp = () => setDragging(false);

  const onWheel = (e: any) => {
    e.preventDefault();
    setZoom(z => Math.max(0.6, Math.min(12, z * (e.deltaY < 0 ? 1.12 : 0.9))));
  };

  // Project world land outline once per rotation — drawn UNDER countries to
  // give a clean coast silhouette without internal country borders.
  const landPaths = useMemo(
    () => WORLD_POLYS.map(p => polyPath(p, rotLng, rotLat, Reff, cx, cy)).filter(o => o.d),
    [rotLng, rotLat, Reff]
  );

  // Project all countries — each country becomes one combined path string
  // (every ring in every polygon, joined). Front-only filtering is handled
  // by polyPath which culls invisible segments.
  const countryPaths = useMemo(() => COUNTRY_META.map((c: any, idx: number) => {
    let d = "";
    for (const poly of c.polys) {
      for (const ring of poly) {
        const o = polyPath(ring, rotLng, rotLat, Reff, cx, cy);
        if (o.d) d += o.d + " ";
      }
    }
    return { idx, d: d.trim(), name: c.name };
  }).filter((o: any) => o.d), [rotLng, rotLat, Reff]);

  // Project pins
  const pins = ACTIVE_DEPLOYMENTS.map((d: any, i: number) => {
    const [x, y, vis] = project(d.lng, d.lat, rotLng, rotLat, Reff, cx, cy);
    return { ...d, x, y, vis, idx: i };
  });

  // ── Group pins by city (highest granularity) ────────────────────
  // Each city becomes a "site": one position (centroid of its pins) + members.
  // Cities NEVER split — even at max zoom, all of a city's projects stay
  // represented by a single pin.
  const cityGroups = useMemo(() => {
    const map = new Map();
    for (const p of pins) {
      if (!p.vis) continue;
      let g = map.get(p.city);
      if (!g) { g = { city: p.city, members: [], lng: 0, lat: 0 }; map.set(p.city, g); }
      g.members.push(p);
    }
    // Compute centroid (average lng/lat) per city; project to screen
    const out: any[] = [];
    for (const g of map.values()) {
      let sLng = 0, sLat = 0;
      for (const m of g.members) { sLng += m.lng; sLat += m.lat; }
      const cLng = sLng / g.members.length;
      const cLat = sLat / g.members.length;
      const [sx, sy] = project(cLng, cLat, rotLng, rotLat, Reff, cx, cy);
      out.push({ ...g, lng: cLng, lat: cLat, x: sx, y: sy });
    }
    return out;
  }, [pins, rotLng, rotLat, Reff]);

  // ── Cluster CITIES by screen proximity ─────────────────────────
  // At a given zoom, nearby cities merge into a multi-city cluster.
  // Cluster id is derived from sorted city names so it's stable across hover.
  const MERGE_PX = 26;
  function clusterSites(sites: any[], mergePx: number) {
    const out: any[] = []; // { x, y, cities: [site, ...] }
    const STATUS_RANK: any = { active: 3, upcoming: 2, diligence: 1 };
    for (const s of sites) {
      let bestI = -1, bestD = Infinity;
      for (let i = 0; i < out.length; i++) {
        const c = out[i];
        const dd = Math.hypot(c.x - s.x, c.y - s.y);
        if (dd < mergePx && dd < bestD) { bestD = dd; bestI = i; }
      }
      const sRank = Math.max(...s.members.map((m: any) => STATUS_RANK[m.status] || 0));
      if (bestI === -1) {
        out.push({ x: s.x, y: s.y, cities: [s], statusRank: sRank });
      } else {
        const c = out[bestI];
        c.cities.push(s);
        c.x = (c.x * (c.cities.length - 1) + s.x) / c.cities.length;
        c.y = (c.y * (c.cities.length - 1) + s.y) / c.cities.length;
        c.statusRank = Math.max(c.statusRank, sRank);
      }
    }
    return out;
  }
  const clusters = useMemo(() => {
    return clusterSites(cityGroups, MERGE_PX).map((c: any) => {
      const cityNames = c.cities.map((x: any) => x.city).sort();
      // Flatten members across all cities for tooltip listing
      const members = c.cities.flatMap((x: any) => x.members);
      const status = c.statusRank === 3 ? "active" : c.statusRank === 2 ? "upcoming" : "diligence";
      return { ...c, id: `c:${cityNames.join("|")}`, members, status };
    });
  }, [cityGroups]);

  // ── explodeZoomForCity: smallest zoom at which the target city is no
  // longer merged with its closest neighbor city. Analytical: pixel
  // distance ≈ R × z × sin(angular distance) when the view is centered
  // on the target. Solve for z, take the closest neighbor as the binding
  // constraint, and add visual headroom.
  //
  // We cap at 12× — beyond that the globe fills the whole viewport and
  // visually breaks. For ultra-close cities (e.g. NYC ↔ Jersey City,
  // ~12 km apart) the orthographic projection physically cannot separate
  // them within a reasonable zoom range. In those cases we fly to a
  // partial zoom and accept the merge — users still see/click individual
  // projects via the popup list.
  function explodeZoomForCity(targetCity: string) {
    const target = cityGroups.find((g: any) => g.city === targetCity);
    if (!target) return zoom;    let minAngle = Infinity;
    for (const g of cityGroups) {
      if (g.city === targetCity) continue;
      const φ1 = target.lat * Math.PI / 180, φ2 = g.lat * Math.PI / 180;
      const dλ = (g.lng - target.lng) * Math.PI / 180;
      const cosD = Math.sin(φ1) * Math.sin(φ2) + Math.cos(φ1) * Math.cos(φ2) * Math.cos(dλ);
      const angle = Math.acos(Math.max(-1, Math.min(1, cosD)));
      if (angle < minAngle) minAngle = angle;
    }
    if (!isFinite(minAngle) || minAngle === 0) return 6;
    const need = (MERGE_PX * 1.5) / (R * Math.sin(minAngle));
    // Target zoom = enough to separate from nearest neighbor, but never less
    // than 6 (so a click on a solo pin always gives a meaningful zoom-in) and
    // capped at 12. Crucially this does NOT depend on current zoom, so
    // clicking the same row repeatedly stays at the same level.
    return Math.min(12, Math.max(6, need));
  }
  // Keep ref in sync so the flyToken effect (defined earlier) can call this.
  explodeZoomForCityRef.current = explodeZoomForCity;

  const counts = {
    active: ACTIVE_DEPLOYMENTS.filter((d: any) => d.status === "active").length,
    upcoming: ACTIVE_DEPLOYMENTS.filter((d: any) => d.status === "upcoming").length,
    diligence: ACTIVE_DEPLOYMENTS.filter((d: any) => d.status === "diligence").length,
  };
  // Real network size = every deployment we plot, across all statuses (the
  // legend breaks it down below). Replaces the old hardcoded "14,287".
  const totalNodes = counts.active + counts.upcoming + counts.diligence;

  return (
    <div style={{ position: "relative", boxSizing: "content-box", width: "calc(100% - 2px)", aspectRatio: isSmallScreen ? "1 / 1.05" : `${W}/${H}`, paddingBottom: isSmallScreen ? 0 : 50, background: "linear-gradient(180deg, var(--bg-2), var(--bg-1))", border: "1px solid var(--line)", borderRadius: 14, overflow: "hidden" }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%" style={{ display: "block", position: "absolute", inset: 0, cursor: dragging ? "grabbing" : "grab", userSelect: "none" }} onMouseDown={onMouseDown} onWheel={onWheel}
        onClick={(e) => {
          // Clicks that bubble to the SVG (i.e. NOT on a country path or a
          // cluster pin — both stopPropagation) → background → clear pin.
          if (dragStart.current && dragStart.current.moved) return;
          setPinnedCluster(null);
        }}>
        <defs>
          <clipPath id="globe-clip">
            <circle cx={cx} cy={cy} r={Reff} />
          </clipPath>
          <radialGradient id="globe-ocean" cx="35%" cy="30%" r="80%">
            <stop offset="0%" stopColor="rgba(243,162,74,0.06)" />
            <stop offset="60%" stopColor="rgba(11,8,20,0.4)" />
            <stop offset="100%" stopColor="rgba(6,4,15,0.7)" />
          </radialGradient>
          <radialGradient id="globe-glow" cx="50%" cy="50%" r="60%">
            <stop offset="80%" stopColor="transparent" />
            <stop offset="92%" stopColor="rgba(243,162,74,0.14)" />
            <stop offset="100%" stopColor="rgba(243,162,74,0)" />
          </radialGradient>
          <radialGradient id="globe-shadow" cx="65%" cy="65%" r="55%">
            <stop offset="0%" stopColor="rgba(0,0,0,0)" />
            <stop offset="100%" stopColor="rgba(0,0,0,0.4)" />
          </radialGradient>
          <linearGradient id="land-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(243,162,74,0.18)" />
            <stop offset="60%" stopColor="rgba(199,62,124,0.10)" />
            <stop offset="100%" stopColor="rgba(199,62,124,0.05)" />
          </linearGradient>
        </defs>

        {/* Outer atmosphere glow */}
        <circle cx={cx} cy={cy} r={Reff + 18} fill="url(#globe-glow)" />

        {/* Globe ocean sphere */}
        <circle cx={cx} cy={cy} r={Reff} fill="url(#globe-ocean)" stroke="rgba(220,200,255,0.18)" strokeWidth="0.8" />

        {/* Graticule + continents — clipped to globe disc so out-of-bounds segments at high zoom can't bleed */}
        <g clipPath="url(#globe-clip)">
          <GraticuleSphere rotLng={rotLng} rotLat={rotLat} R={Reff} cx={cx} cy={cy} color="rgba(220,200,255,0.4)" />
          {/* Continent silhouette (no internal country borders) */}
          {landPaths.map((o: any, i: number) => (
            <path key={`L${i}`} d={o.d} fill="url(#land-grad)" stroke="rgba(243,162,74,0.55)" strokeWidth="0.7" strokeLinejoin="round" pointerEvents="none" />
          ))}
          {countryPaths.map((o: any) => {
            const isHover = hoverCountry === o.idx;
            const isSelected = selectedCountry === o.idx;
            return (
              <path
                key={o.idx}
                d={o.d}
                fill={isSelected ? "rgba(243,162,74,0.42)" : isHover ? "rgba(243,162,74,0.32)" : "rgba(0,0,0,0)"}
                stroke={isHover || isSelected ? "rgba(255,200,140,0.95)" : "none"}
                strokeWidth={isHover || isSelected ? 1.1 : 0}
                strokeLinejoin="round"
                style={{ cursor: "pointer", transition: "fill 120ms" }}
                pointerEvents="all"
                onMouseEnter={() => setHoverCountry(o.idx)}
                onMouseLeave={() => setHoverCountry((h: any) => h === o.idx ? null : h)}
                onClick={(e) => {
                  e.stopPropagation();
                  // Suppress click if the user just dragged (mouseup → click sequence)
                  if (dragStart.current && dragStart.current.moved) return;
                  // If this country is already focused, do nothing — let the
                  // user drag to pan within it instead of re-triggering fly-to.
                  if (selectedCountry === o.idx) return;
                  const c = COUNTRY_META[o.idx];
                  setSelectedCountry(o.idx);
                  flyTo(c.centerLng, c.centerLat, c.fitZoom);
                }}
              />
            );
          })}
        </g>

        {/* Day-side shadow */}
        <circle cx={cx} cy={cy} r={Reff} fill="url(#globe-shadow)" pointerEvents="none" />

        {/* Pins (clustered) */}
        {clusters.map((c: any) => {
          const isHover = hoverCluster === c.id;
          const isPinned = pinnedCluster === c.id;
          const isMulti = c.members.length > 1;
          // Is one of this cluster's members being hovered in the popup list?
          const hoveredMember = hoveredMemberIdx != null
            ? c.members.find((m: any) => m.idx === hoveredMemberIdx)
            : null;
          // Selected pin lives in this cluster?
          const selectedHere = selectedPin
            ? c.members.find((m: any) => m.idx === selectedPin.idx)
            : null;
          const isSelectedHere = !!selectedHere;
          const baseR = isMulti ? 5.5 + Math.min(4, c.members.length - 1) : (c.status === "active" ? 4.2 : c.status === "upcoming" ? 3.2 : 2.4);
          const r = (isHover || isPinned || isSelectedHere) ? baseR * 1.4 : baseR;
          const color = STATUS_COLORS[c.status];
          return (
            <g key={c.id} onMouseEnter={() => { setHoverCluster(c.id); setHoverIdx(c.members[0].idx); }} onMouseLeave={() => { setHoverCluster((h: any) => h === c.id ? null : h); setHoverIdx(null); }} style={{ cursor: "pointer" }}>
              {/* Attention pulse — drawn for every status (in its own colour)
                  so upcoming and diligence pins are as visible as active ones,
                  not just the active set. */}
              {!isMulti && (
                <circle cx={c.x} cy={c.y} r={baseR * 4} fill={color} opacity="0.18">
                  <animate attributeName="r" values={`${baseR*1.6};${baseR*5};${baseR*1.6}`} dur={`${2 + (c.members[0].idx)*0.15}s`} repeatCount="indefinite" />
                  <animate attributeName="opacity" values="0.45;0;0.45" dur={`${2 + (c.members[0].idx)*0.15}s`} repeatCount="indefinite" />
                </circle>
              )}
              {/* Outer halo for clusters */}
              {isMulti && (
                <circle cx={c.x} cy={c.y} r={r + 4} fill="none" stroke={color} strokeWidth="1" opacity="0.55" />
              )}
              <circle cx={c.x} cy={c.y} r={r} fill={color} stroke="#fff" strokeWidth={(isHover || isPinned || isSelectedHere) ? 1.6 : 0.6} style={{ transition: "r 160ms" }}
                onClick={(e) => {
                  e.stopPropagation();
                  if (dragStart.current && dragStart.current.moved) return;
                  if (isMulti) {
                    setPinnedCluster((p: any) => p === c.id ? null : c.id);
                  } else {
                    onSelectPin && onSelectPin(c.members[0]);
                  }
                }}
              />
              {isMulti && (
                <text x={c.x} y={c.y + 3.5} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="10" fontWeight="600" fill="#0B0814" pointerEvents="none">
                  {c.members.length}
                </text>
              )}
              {/* Static ring in the hovered-row's status color, layered on top */}
              {hoveredMember && (
                <circle cx={c.x} cy={c.y} r={r + 7} fill="none"
                  stroke={STATUS_COLORS[hoveredMember.status]} strokeWidth="1.6" opacity="1"
                  pointerEvents="none" />
              )}
              {/* Persistent selection ring — visually links the pin to the detail panel */}
              {isSelectedHere && !hoveredMember && (
                <>
                  <circle cx={c.x} cy={c.y} r={r + 9} fill="none"
                    stroke={STATUS_COLORS[selectedHere.status]} strokeWidth="1.4" opacity="0.9"
                    pointerEvents="none" />
                  <circle cx={c.x} cy={c.y} r={r + 14} fill="none"
                    stroke={STATUS_COLORS[selectedHere.status]} strokeWidth="0.8" opacity="0.4"
                    pointerEvents="none" />
                </>
              )}
            </g>
          );
        })}

        {/* Tooltip — drawn last so it's on top. Pinned beats hover. */}
        {(pinnedCluster || hoverCluster) && (() => {
          const id = pinnedCluster || hoverCluster;
          const c = clusters.find((x: any) => x.id === id);
          if (!c) return null;
          const right = c.x < cx;
          const TIP_W = 230;
          const isMulti = c.members.length > 1;
          const baseH = isMulti ? 38 + c.members.length * 26 : 58;
          const TIP_H = baseH;
          const tx = right ? c.x + 18 : c.x - 18 - TIP_W;
          const ty = Math.max(20, Math.min(H - TIP_H - 10, c.y - TIP_H / 2));
          return (
            <g>
              <line x1={c.x} y1={c.y} x2={right ? tx : tx + TIP_W} y2={ty + 28} stroke="rgba(255,255,255,0.4)" strokeWidth="0.6" pointerEvents="none" />
              {isMulti ? (
                <foreignObject x={tx} y={ty} width={TIP_W} height={TIP_H} style={{ overflow: "visible" }}>
                  <div
                    style={{
                      width: "100%",
                      boxSizing: "border-box",
                      background: "rgba(11,8,20,0.95)",
                      border: "1px solid var(--line-strong)",
                      borderLeft: `3px solid ${STATUS_COLORS[c.status]}`,
                      borderRadius: 6,
                      padding: "10px 12px",
                      display: "flex",
                      flexDirection: "column",
                      gap: 4,
                    }}
                  >
                    <div style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--fg-3)", letterSpacing: "0.14em", marginBottom: 2 }}>
                      {(() => {
                        const cityCount = new Set(c.members.map((m: any) => m.city)).size;
                        return cityCount > 1
                          ? `${c.members.length} PROJECTS · ${cityCount} CITIES · CLICK TO ZOOM`
                          : `${c.members.length} PROJECTS · ${c.members[0].city.toUpperCase()}`;
                      })()}
                    </div>
                    {c.members.map((m: any) => {
                      const isRowHover = hoveredMemberIdx === m.idx;
                      return (
                        <div key={m.idx}
                          onMouseEnter={() => setHoveredMemberIdx(m.idx)}
                          onMouseLeave={() => setHoveredMemberIdx((h: any) => h === m.idx ? null : h)}
                          onClick={(e) => {
                            e.stopPropagation();
                            // Find the city's centroid; fly to it at a zoom
                            // sufficient to isolate this city from any others.
                            const site = cityGroups.find((g: any) => g.city === m.city);
                            if (!site) return;
                            const z = explodeZoomForCity(m.city);
                            setPinnedCluster(null);
                            setHoveredMemberIdx(null);
                            flyTo(site.lng, site.lat, z);
                            onSelectPin && onSelectPin(m);
                          }}
                          style={{
                            display: "grid",
                            gridTemplateColumns: "8px minmax(0,1fr) auto",
                            alignItems: "center",
                            columnGap: 8,
                            padding: "3px 4px",
                            borderRadius: 3,
                            cursor: "pointer",
                            background: isRowHover ? `color-mix(in srgb, ${STATUS_COLORS[m.status]} 16%, transparent)` : "transparent",
                          }}
                        >
                          <span style={{ width: 8, height: 8, borderRadius: "50%", background: STATUS_COLORS[m.status], border: "0.5px solid #fff", boxSizing: "border-box" }} />
                          <span style={{ minWidth: 0, overflowWrap: "anywhere", fontFamily: "var(--font-display)", fontSize: 12, fontWeight: isRowHover ? 600 : 500, color: isRowHover ? "#fff" : "var(--fg)", letterSpacing: "-0.01em", lineHeight: 1.2 }}>{m.name}</span>
                          <span style={{ whiteSpace: "nowrap", fontFamily: "var(--font-mono)", fontSize: 10, color: STATUS_COLORS[m.status], letterSpacing: "0.06em" }}>{formatDeployedValue(m.value)}</span>
                        </div>
                      );
                    })}
                  </div>
                </foreignObject>
              ) : (() => {
                const m = c.members[0];
                return (
                  <>
                    <rect x={tx} y={ty} width={TIP_W} height={TIP_H} fill="rgba(11,8,20,0.95)" stroke="var(--line-strong)" strokeWidth="1" rx="6" pointerEvents="none" />
                    <rect x={tx} y={ty} width="3" height={TIP_H} fill={STATUS_COLORS[c.status]} pointerEvents="none" />
                    <text x={tx + 12} y={ty + 22} fontFamily="var(--font-display)" fontSize="13" fontWeight="500" fill="var(--fg)" letterSpacing="-0.01em" pointerEvents="none">{m.name}</text>
                    <text x={tx + 12} y={ty + 38} fontFamily="var(--font-mono)" fontSize="9" fill="var(--fg-3)" letterSpacing="0.1em" pointerEvents="none">{m.label.toUpperCase()}</text>
                    <text x={tx + 12} y={ty + 50} fontFamily="var(--font-mono)" fontSize="10" fill={STATUS_COLORS[m.status]} letterSpacing="0.06em" pointerEvents="none">{formatDeployedValue(m.value)} · {m.region}</text>
                  </>
                );
              })()}
            </g>
          );
        })()}
      </svg>

      {/* Overlay key */}
      <div style={{ position: "absolute", top: 14, left: 14, padding: "12px 14px", background: "rgba(11,8,20,0.78)", border: "1px solid var(--line-strong)", borderRadius: 8, backdropFilter: "blur(12px)" }}>
        <div className="kicker" style={{ marginBottom: 10 }}>{`// LIVE NETWORK · ${totalNodes.toLocaleString()} ${totalNodes === 1 ? "NODE" : "NODES"}`}</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ fontSize: 11, color: "var(--fg-2)", display: "inline-flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#F3A24A", boxShadow: "0 0 8px #F3A24A" }} />Active · {counts.active}
          </div>
          <div style={{ fontSize: 11, color: "var(--fg-2)", display: "inline-flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#EA5270" }} />Upcoming · {counts.upcoming}
          </div>
          <div style={{ fontSize: 11, color: "var(--fg-3)", display: "inline-flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "rgba(220,200,255,0.5)" }} />Diligence · {counts.diligence}
          </div>
        </div>
      </div>

      {/* Spin toggle */}
      <button
        onClick={() => setAutoSpin(s => !s)}
        style={{
          position: "absolute", bottom: 14, left: 14,
          padding: "8px 12px",
          background: "rgba(11,8,20,0.78)", border: "1px solid var(--line-strong)",
          borderRadius: 8, color: "var(--fg-2)", cursor: "pointer",
          fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.14em",
          display: "inline-flex", alignItems: "center", gap: 8,
          backdropFilter: "blur(12px)",
        }}>
        <span style={{ width: 6, height: 6, borderRadius: "50%", background: autoSpin ? "var(--pos)" : "var(--fg-4)" }} />
        {autoSpin ? "AUTO-SPIN" : "DRAG TO ROTATE"}
      </button>

      {/* Country focus indicator + reset */}
      {selectedCountry !== null && (
        <button
          onClick={() => {
            setSelectedCountry(null);
            flyTo(-90, 20, 1);
          }}
          style={{
            position: "absolute", bottom: 14, left: 180,
            padding: "8px 12px",
            background: "rgba(243,162,74,0.14)", border: "1px solid rgba(243,162,74,0.5)",
            borderRadius: 8, color: "var(--accent)", cursor: "pointer",
            fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.14em",
            display: "inline-flex", alignItems: "center", gap: 8,
            backdropFilter: "blur(12px)",
          }}>
          <span>← {(COUNTRY_META[selectedCountry]?.name || "").toUpperCase()}</span>
          <span style={{ opacity: 0.6 }}>RESET</span>
        </button>
      )}

      {/* Zoom controls */}
      <div style={{ position: "absolute", bottom: 14, right: 14, display: "flex", flexDirection: "column", gap: 4 }}>
        <button onClick={() => setZoom(z => Math.min(12, z * 1.25))} style={{
          width: 28, height: 28,
          background: "rgba(11,8,20,0.78)", border: "1px solid var(--line-strong)",
          borderRadius: 6, color: "var(--fg-2)", cursor: "pointer",
          fontFamily: "var(--font-mono)", fontSize: 14, lineHeight: 1,
          backdropFilter: "blur(12px)",
        }}>+</button>
        <button onClick={() => setZoom(z => Math.max(0.6, z * 0.8))} style={{
          width: 28, height: 28,
          background: "rgba(11,8,20,0.78)", border: "1px solid var(--line-strong)",
          borderRadius: 6, color: "var(--fg-2)", cursor: "pointer",
          fontFamily: "var(--font-mono)", fontSize: 14, lineHeight: 1,
          backdropFilter: "blur(12px)",
        }}>−</button>
        <button onClick={() => { setZoom(1); setRotLng(-90); setRotLat(20); }} style={{
          width: 28, height: 28,
          background: "rgba(11,8,20,0.78)", border: "1px solid var(--line-strong)",
          borderRadius: 6, color: "var(--fg-3)", cursor: "pointer",
          fontFamily: "var(--font-mono)", fontSize: 9, lineHeight: 1, letterSpacing: "0.06em",
          backdropFilter: "blur(12px)",
        }}>⌖</button>
      </div>

      {/* Coords — top-right on desktop, bottom-center on mobile.
          On mobile this container (aspectRatio 1/1.05) is rendered inside a
          landscape wrapper (aspectRatio 742/529, overflow hidden), so its
          bottom ~32% is clipped. Anchor the chip to ~64% down — just inside
          the visible window's bottom edge — rather than to the true bottom. */}
      <div
        className="mono"
        style={isSmallScreen
          ? { position: "absolute", bottom: "36%", left: "50%", transform: "translateX(-50%)", whiteSpace: "nowrap" }
          : { position: "absolute", top: 14, right: 14 }}
      >
        <span style={{ fontSize: 9, color: "var(--fg-4)", letterSpacing: "0.14em", padding: "6px 10px", background: "rgba(11,8,20,0.6)", border: "1px solid var(--line)", borderRadius: 6, backdropFilter: "blur(8px)" }}>
          ORTHO · LON {(-rotLng).toFixed(0)}° · LAT {rotLat.toFixed(0)}° · ZOOM {zoom.toFixed(1)}×
        </span>
      </div>
    </div>
  );
}

export { ringArea, COUNTRIES, WORLD_POLYS, COUNTRY_META, project, project3, polyPath, GraticuleSphere };
