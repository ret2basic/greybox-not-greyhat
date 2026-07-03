'use client';

import { Tower3D } from './Tower3D';
import { Node3D } from './scene-3d';
import { ACCESS_TYPES } from './access';

// Verbatim port of v5 ReservesScreen-v2.jsx 1407–1466. The ACCESS_TYPES
// import replaces v5's window.ACCESS_TYPES; Tower3D replaces window.Tower5;
// Node3D replaces window.Node3D. locationLabel is brought in from the host
// page (v5 had it in scope inside the same file); here we accept `pin` as a
// loose object with a precomputed `locationLabel` string OR fall back.

function locationLabel(pin: any): string {
  // Minimal fallback — the host page will normally pass a string-shaped
  // label via pin._label; otherwise stringify whatever's there. Region only
  // ("State · Country" / "Country") to match the project panels — no city.
  if (!pin) return "";
  if (typeof pin === "string") return pin;
  if (pin._label) return String(pin._label);
  return [pin.state, pin.country || pin.region].filter(Boolean).join(" · ").toUpperCase();
}

// The plan outline is in feet; Tower3D's interior layout is tuned for a
// stylized ~380×220 envelope. Scale to fit that envelope while preserving the
// real aspect ratio, returning the scene-space footprint + the scale factor
// (reused to place entered antennas in the same frame). Null when no outline.
function footprintFromOutline(outline?: Array<[number, number]>) {
  if (!outline || outline.length < 3) return null;
  let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
  for (const [x, z] of outline) {
    if (x < minX) minX = x;
    if (x > maxX) maxX = x;
    if (z < minZ) minZ = z;
    if (z > maxZ) maxZ = z;
  }
  const w = maxX - minX;
  const d = maxZ - minZ;
  if (w <= 0 || d <= 0) return null;
  const scale = Math.min(380 / w, 220 / d);
  return { w: w * scale, d: d * scale, scale };
}

export function AssetVisualizerPanel({ building, pin, onBack, compact }: { building: any; pin: any; onBack?: () => void; compact?: boolean }) {
  const ACCESS = ACCESS_TYPES;
  if (!ACCESS || !Tower3D) {
    return (
      <div style={{
        width: "100%", aspectRatio: "720/520",
        background: "var(--bg-2)", border: "1px solid var(--line)",
        borderRadius: 14, display: "flex", alignItems: "center", justifyContent: "center",
        color: "var(--fg-3)", fontFamily: "var(--font-mono)", fontSize: 12,
      }}>Asset visualizer not loaded</div>
    );
  }
  // The host page passes building.accessType using v5 keys ('hallway' for
  // the hallway-WiFi tech); our visualizer's ACCESS_TYPES table stores
  // that under 'hallway-wifi'. Alias here so the lookup matches.
  const accessKey = building.accessType === 'hallway' ? 'hallway-wifi' : building.accessType;
  const t = (ACCESS as any)[accessKey] || (ACCESS as any).gpon;
  // Match the per-tech access renderers in AVAccessConcepts.jsx
  const ACCESS_PROPS: any = {
    gpon:     { thickness: 0.7, dashed: false, size: 4.5 },
    ethernet: { thickness: 0.9, dashed: true,  size: 4.5 },
    coax:     { thickness: 1.4, dashed: false, size: 5.0 },
    hallway:  { thickness: 0.8, dashed: false, size: 4.5 }, // hallway uses APs, but Tower5 default is fine
  };
  const ap = ACCESS_PROPS[building.accessType] || ACCESS_PROPS.gpon;
  const renderAccess = ({ key, x, y, z, sceneYaw, scenePitch }: any) => (
    <Node3D key={key} x={x} y={y} z={z} size={ap.size} color={t.color}
      sceneYaw={sceneYaw} scenePitch={scenePitch} showLabel={false} />
  );
  // Roof-mounted MDFs typically use fixed-wireless POE (no fiber pulled to the roof);
  // basement MDFs use fiber. Mirrors the conventions from the concepts file.
  const isRoof = building.mdfPlacement === "roof";
  // DAWN flag — same deterministic formula as the buildings table. DAWN
  // buildings always render rooftop distribution antennas, regardless of
  // whether their MDF lives on the roof or in the basement.
  const idHash = (building.id || "").split("").reduce((s: number, c: string) => s + c.charCodeAt(0), 0);
  const dawn = (idHash % 10) < 7;

  // ── Manager-entered plan → renderer props ────────────────────────────
  // The rendered snapshot (centered design-pixel coords) drives floors, IDF
  // taps, footprint proportions, POE, and rooftop antennas. When a building
  // has no baked plan, these stay undefined and Tower3D's parametric defaults
  // apply.
  const plan = building.plan ?? null;
  const fp = footprintFromOutline(plan?.geometry?.outline);
  const poe = plan?.infra?.poe ?? null;
  const antennas = plan && fp
    ? (plan.infra?.broadcastAntennas ?? []).map((a: any) => ({
        id: a.id, x: a.x * fp.scale, z: a.z * fp.scale, height: a.height, label: a.label,
      }))
    : undefined;
  return (
    <div style={{
      position: "relative", width: "100%", height: "100%",
      background: "var(--bg-2)", border: "1px solid var(--line)",
      borderRadius: 14, overflow: "hidden",
    }}>
      <Tower3D
        accessLabel={t.label} accessShort={t.short} accessColor={t.color}
        accessThickness={ap.thickness} accessDashed={ap.dashed}
        accessMode={building.accessType === "hallway" ? "hallway" : "inUnit"}
        renderAccess={renderAccess}
        mdfPlacement={building.mdfPlacement || "basement"}
        poeKind={poe?.kind ?? (isRoof ? "fwa" : "fiber")}
        poeProvider={poe?.provider}
        poeStatLatency={poe?.stats?.latency}
        poeStatActive={poe?.stats?.active}
        poeStatCapacity={poe?.stats?.capacity}
        hasBroadcastAntennas={dawn || isRoof}
        floorCount={plan?.geometry?.floorCount}
        idfFloors={plan?.distribution?.idfFloors}
        footprintW={fp?.w}
        footprintD={fp?.d}
        broadcastAntennas={antennas}
        onBack={onBack}
        compact={compact}
        // Mobile opens the tower at half scale so the whole building fits the
        // smaller stacked scene area without an immediate pinch-out.
        initZoom={compact ? 0.425 : 0.85}
        project={{
          name: `${building.name} · ${building.address.split(" · ")[0]}`,
          city: locationLabel(pin),
          apr: "8.5%",
          tvl: `$${(building.units * 0.07).toFixed(1)}M`,
          sub: building.subscribers || 0,
        }}
      />
    </div>
  );
}
