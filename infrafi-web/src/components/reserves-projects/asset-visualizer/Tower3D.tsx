'use client';

// Shared building primitive (Concept 5 envelope) — used by access concepts.
// Hierarchy:
//   POE → MDF → trunk (riser) → IDFs (taps on trunk)
//                            ↳ per-floor center spine (branches off trunk)
//                                    ↳ left + right drops INTO units
//                                            ↳ access nodes (ONT/AP/CPE in unit)

import * as React from 'react';
import { useState } from 'react';
import { useOrbit } from './use-orbit';
import { Scene3D, Place3D, FloorPlane, WallPlane, Edge3D, Node3D, FloorLabel, AntennaWaves } from './scene-3d';
import { PanelChrome, ControlsHint, LayerBar, OrbitControls } from './chrome';
import { RightPanel } from './right-panel';

const TOWER_LINE = "rgba(232, 224, 240, 0.55)";
const TOWER_DIM = "rgba(232, 224, 240, 0.22)";
const TOWER_ACCENT = "#F3A24A";
// Hierarchy color coding
const POE_COLOR = "#7BD9FF";   // carrier handoff (blue)
const MDF_COLOR = "#F3A24A";   // main distribution (amber)
const IDF_COLOR = "#A8E063";   // intermediate distribution (lime)
const BCAST_COLOR = "#E48DD0"; // tenant rooftop broadcast (magenta)

const DEFAULT_FLOORS = 14;
const DEFAULT_IDF_FLOORS = [13, 10, 7, 4, 1];
// Plan design coords bake one floor at this many pixels (manager's
// DEFAULT_FLOOR_HEIGHT_PX); used to scale entered antenna heights (in feet)
// into the renderer's per-floor GAP.
const PLAN_FLOOR_PX = 38;

// Partition every floor (1..total) onto its nearest IDF tap, producing each
// IDF's serves-band. Reproduces the legacy 3-floor banding for the default
// [13,10,7,4,1] layout and generalizes to any entered set of IDF floors.
function computeIdfPlan(idfFloors: number[], total: number): Array<{ floor: number; serves: number[] }> {
  const idfs = idfFloors.filter((f) => f >= 1 && f <= total).sort((a, b) => a - b);
  if (idfs.length === 0) return [{ floor: 1, serves: Array.from({ length: total }, (_, i) => i + 1) }];
  const serves = new Map<number, number[]>(idfs.map((f) => [f, []]));
  for (let fl = 1; fl <= total; fl++) {
    let best = idfs[0];
    let bd = Infinity;
    for (const f of idfs) {
      const d = Math.abs(f - fl);
      if (d < bd) { bd = d; best = f; }
    }
    serves.get(best)!.push(fl);
  }
  return idfs.map((f) => ({ floor: f, serves: serves.get(f)! }));
}

export function Tower3D({
  accent = TOWER_ACCENT,
  accessLabel, accessShort, accessColor,
  accessThickness = 0.8, accessDashed = false,
  accessMode = "inUnit",
  yawInit = 90, autoOrbit = true,
  renderAccess, statsForIDF,
  // Hierarchy placement variants
  mdfPlacement = "basement",   // "basement" | "roof"
  poeKind = "fiber",           // "fiber" | "fwa" (fixed-wireless antenna)
  poeProvider = "Verizon",
  // Whether to render rooftop distribution antennas (for DAWN open-access
  // wireless). Defaults to roof-MDF buildings; can be forced on independently
  // — e.g. a basement-MDF building that's still on DAWN.
  hasBroadcastAntennas,
  poeStatLatency = "1.2 ms",
  poeStatActive = "23.4 Gbps",
  poeStatCapacity = "100 Gbps",
  // Display chrome — defaults preserve old hardcoded behavior
  project = { name: "Liberty Tower · 200 Park", city: "New York, NY", apr: "8.8%", tvl: "$12.4M", sub: 384 },
  // Close-button handler (× in PanelChrome). When set, the chrome × becomes
  // a "back to building list" affordance for the host app.
  onBack,
  initZoom = 0.95,
  // Manager-entered geometry. Undefined falls back to the parametric defaults
  // so buildings without a baked plan still render the generic tower.
  floorCount = DEFAULT_FLOORS,
  idfFloors = DEFAULT_IDF_FLOORS,
  footprintW = 380,
  footprintD = 220,
  broadcastAntennas,
  // Mobile/compact layout: stack the 3D scene over an in-flow detail dock
  // instead of the desktop floating-overlay chrome. Desktop path is untouched.
  compact = false,
}: {
  accent?: string;
  accessLabel?: string;
  accessShort?: string;
  accessColor?: string;
  accessThickness?: number;
  accessDashed?: boolean;
  accessMode?: string;
  yawInit?: number;
  autoOrbit?: boolean;
  renderAccess?: (args: any) => any;
  statsForIDF?: (p: any) => any;
  mdfPlacement?: string;
  poeKind?: string;
  poeProvider?: string;
  hasBroadcastAntennas?: boolean;
  poeStatLatency?: string;
  poeStatActive?: string;
  poeStatCapacity?: string;
  project?: any;
  onBack?: () => void;
  initZoom?: number;
  floorCount?: number;
  idfFloors?: number[];
  footprintW?: number;
  footprintD?: number;
  broadcastAntennas?: Array<{ id: string; x: number; z: number; height: number; label: string }>;
  compact?: boolean;
}) {
  // Default lean: slight isometric, oscillate around the IDF face
  const orbit = useOrbit({
    yaw: yawInit, pitch: 30, zoom: initZoom,
    oscillate: autoOrbit ? { range: 35, period: 32 } : null,
    autoRotate: autoOrbit,
  });
  const { yaw, pitch, zoom, panX, panY, reset, focusOn, bind, autoOn, enableAuto, setAutoOn } = orbit;
  const [selected, setSelected] = useState<any>(null);
  const [layers, setLayers] = useState<any>({ idf: true, access: true, bcast: true, labels: true });

  const TOTAL = Math.max(1, Math.round(floorCount));
  const idfPlan = computeIdfPlan(idfFloors, TOTAL);
  const FW = footprintW, FD = footprintD, GAP = 40;
  const yFor = (idx: number) => (idx - (TOTAL - 1) / 2) * GAP;          // idx 0 = floor 1
  const yForFloor = (floor: number) => yFor(floor - 1);
  const yTop = yFor(TOTAL - 1), yBot = yFor(0);
  const isRoof = mdfPlacement === "roof";
  // Entered antennas (when present) take precedence over the DAWN/roof heuristic.
  const showBcast = broadcastAntennas != null
    ? broadcastAntennas.length > 0
    : hasBroadcastAntennas != null ? hasBroadcastAntennas : isRoof;
  const yRoof = yTop + GAP * 0.5;   // top surface of the roof slab
  const yRoofCable = yRoof + 10;    // raised so the MDF node circle clears the roof slab
  // MDF y: basement is 1.4*GAP below floor 1; roof variant lifted off the bulkhead floor.
  const yMDF = isRoof ? yRoof + 16 : yBot - GAP * 1.4;
  const corners = [[-FW / 2, -FD / 2], [FW / 2, -FD / 2], [FW / 2, FD / 2], [-FW / 2, FD / 2]];

  // Trunk corner: front-left of the floor plate (riser shaft)
  const xC = -FW / 2 + 22, zC = -FD / 2 + 22;

  // Trunk (riser) vertical extents — always spans the floors only:
  //   basement variant: MDF sits at the BOTTOM of the trunk (xC, yMDF, zC)
  //   roof variant:    MDF lives separately on the roof, trunk top connects to it
  const yTrunkBot = isRoof ? yBot - 4 : yMDF;
  // In the roof variant, push the trunk up THROUGH the roof to meet the cable
  // height so the horizontal→vertical transition is clearly above the slab and
  // never gets clipped by the roof's opacity.
  const yTrunkTop = isRoof ? yRoof + 10 : yTop;

  // MDF position: basement variant lives at the trunk corner; roof variant
  // lives at the CENTER of the roof, inside its bulkhead.
  const xMDF = isRoof ? 0 : xC;
  const zMDF = isRoof ? 0 : zC;

  // Center spine z (down the middle of each floor)
  const zSpine = 0;
  const xSpineStart = xC + 10;
  const xSpineEnd = FW / 2 - 30;
  const zUnitFront = -FD / 2 + 38;
  const zUnitBack  =  FD / 2 - 38;
  const apXs = [xSpineStart + 30, xSpineEnd - 30];
  const unitSlots = [
    { side: "F", z: zUnitFront, dir: -1 },
    { side: "B", z: zUnitBack, dir: +1 },
  ];

  // POE position:
  //   basement+fiber: outside the building at MDF level (curb handoff)
  //   roof+fwa:      antenna sits on the OPPOSITE roof corner from the trunk,
  //                  so the antenna→MDF and MDF→riser-top cables both read clearly.
  const xPOEBase = isRoof ? FW / 2 - 22 : -FW / 2 - 90;
  const zPOEBase = isRoof ? FD / 2 - 22 : zC;
  const yPOEBase = isRoof ? yRoof : yMDF;   // antenna base sits on the roof
  // For FWA, the actual POE node is at the top of a mast above the antenna base.
  const xPOE = xPOEBase;
  const zPOE = zPOEBase;
  const yPOE = isRoof ? yPOEBase + GAP * 0.9 : yPOEBase;

  // Tenant rooftop broadcast antennas — hoisted out of the FWA branch so the
  // logic diagram can enumerate them as devices. Entered antennas come in
  // design-pixel coords (same frame as the footprint). Per DAWN-1490 we no
  // longer use a per-antenna mast height — every antenna renders at a fixed
  // standard height (STD_ANTENNA_FT), scaled into the renderer's per-floor GAP.
  const STD_ANTENNA_FT = 5;
  const broadcastSites = !showBcast ? [] : broadcastAntennas != null
    ? broadcastAntennas.map((a) => ({ id: a.id, x: a.x, z: a.z, h: STD_ANTENNA_FT * (GAP / PLAN_FLOOR_PX), label: a.label }))
    : [
        { id: "bcast-1", x: -FW / 2 + 60, z: FD / 2 - 30, h: GAP * 0.55, label: "Antenna 1 · Front-left" },
        { id: "bcast-2", x: 30,           z: FD / 2 - 30, h: GAP * 0.5,  label: "Antenna 2 · Front-center" },
        { id: "bcast-3", x: FW / 2 - 30,  z: -FD / 2 + 90, h: GAP * 0.6, label: "Antenna 3 · Right-back" },
      ];

  // Build a flat catalog of every clickable device for the logic diagram.
  // Each entry has a 3D position used by the focus-on-click camera move.
  // (Access Domain is intentionally omitted from the logical diagram — its
  // layer still renders in the 3D scene but isn't surfaced as a node; DAWN-1490.)
  const deviceCatalog = [
    { key: "poe", label: "Point of Entry", short: "POE", color: POE_COLOR, devices: [
        { id: "poe", label: poeKind === "fwa" ? `${poeProvider} · FWA antenna` : `${poeProvider} · 100G fiber`,
          x: xPOE, y: yPOE + 2, z: zPOE },
      ] },
    { key: "mdf", label: "Main Distribution Frame", short: "MDF", color: MDF_COLOR, devices: [
        { id: "mdf", label: isRoof ? "MDF · Roof bulkhead" : "MDF · Basement",
          x: xMDF, y: isRoof ? yRoofCable : yMDF + 2, z: zMDF },
      ] },
    { key: "idf", label: "Intermediate Distribution Frame", short: "IDF", color: IDF_COLOR, devices: idfPlan.map(p => ({
        id: `idf-${p.floor}`, label: `IDF · Floor ${p.floor}`,
        x: xC, y: yForFloor(p.floor) + 2, z: zC,
      })) },
    { key: "bcast", label: "Distribution Antennas", short: "Distribution Antennas", color: BCAST_COLOR,
      hidden: !showBcast,
      devices: broadcastSites.map(s => ({
        id: s.id, label: s.label, x: s.x, y: yRoof + s.h, z: s.z,
      })) },
  ].filter(c => !c.hidden);

  const sceneEl = (
      <Scene3D yaw={yaw} pitch={pitch} zoom={zoom} panX={panX} panY={panY} bind={bind}>
        {/* === ENVELOPE === */}
        {corners.map(([cx, cz], ci) => (
          <Edge3D key={`col-${ci}`}
            from={[cx, yBot - GAP / 2, cz]} to={[cx, yTop + GAP / 2, cz]}
            color="rgba(232,224,240,0.18)" thickness={1} />
        ))}
        <Place3D x={0} y={yTop + GAP / 2} z={0}>
          <FloorPlane w={FW} d={FD}
            color="rgba(28,34,46,0.96)"
            stroke="rgba(232,224,240,0.12)"
            grid gridStep={32} />
        </Place3D>
        <Place3D x={0} y={yBot - GAP / 2} z={0}>
          <FloorPlane w={FW} d={FD} color="rgba(232,224,240,0.02)" stroke={TOWER_LINE} dashed />
        </Place3D>

        {/* === FLOORS — outline + center spine + drops + access nodes === */}
        {Array.from({ length: TOTAL }).map((_, idx) => {
          const floor = idx + 1;
          const y = yFor(idx);
          return (
            <React.Fragment key={floor}>
              {/* Floor outline */}
              <Edge3D from={[-FW / 2, y, -FD / 2]} to={[FW / 2, y, -FD / 2]} color={TOWER_LINE} thickness={0.5} />
              <Edge3D from={[FW / 2, y, -FD / 2]} to={[FW / 2, y, FD / 2]} color={TOWER_LINE} thickness={0.5} />
              <Edge3D from={[FW / 2, y, FD / 2]} to={[-FW / 2, y, FD / 2]} color={TOWER_LINE} thickness={0.5} />
              <Edge3D from={[-FW / 2, y, FD / 2]} to={[-FW / 2, y, -FD / 2]} color={TOWER_LINE} thickness={0.5} />

              {/* IDF→spine entry: trunk corner → spine start (corner-to-center turn) */}
              {layers.access && (
                <Edge3D
                  from={[xC, y + 0.5, zC]} to={[xC, y + 0.5, zSpine]}
                  color={`${accessColor}AA`} thickness={accessThickness + 0.2} />
              )}
              {layers.access && (
                <Edge3D
                  from={[xC, y + 0.5, zSpine]} to={[xSpineStart, y + 0.5, zSpine]}
                  color={`${accessColor}AA`} thickness={accessThickness + 0.2} />
              )}

              {/* Center spine across floor */}
              {layers.access && (
                <Edge3D
                  from={[xSpineStart, y + 0.5, zSpine]} to={[xSpineEnd, y + 0.5, zSpine]}
                  color={`${accessColor}DD`} thickness={accessThickness + 0.3}
                  dashed={accessDashed} />
              )}

              {/* Floor label */}
              {layers.labels && (
                <FloorLabel x={-FW / 2 - 22} y={y + 4} z={FD / 2 + 4}
                  text={String(floor).padStart(2, "0")} color="var(--fg-2)"
                  sceneYaw={yaw} scenePitch={pitch} />
              )}

              {/* Drops + access nodes (in-unit) OR hallway APs */}
              {layers.access && accessMode === "inUnit" && unitSlots.map((slot) => (
                apXs.map((ux, i) => {
                  const apId = `${String(floor).padStart(2, "0")}-${slot.side}${i + 1}`;
                  return (
                    <React.Fragment key={`${slot.side}${i}`}>
                      <Edge3D
                        from={[ux, y + 0.5, zSpine]}
                        to={[ux, y + 0.5, slot.z]}
                        color={`${accessColor}88`} thickness={accessThickness}
                        dashed={accessDashed} />
                      {renderAccess && renderAccess({
                        key: apId,
                        x: ux, y: y + 1, z: slot.z,
                        apId, floorId: floor, side: slot.side,
                        sceneYaw: yaw, scenePitch: pitch,
                        selected, setSelected,
                      })}
                    </React.Fragment>
                  );
                })
              ))}
              {layers.access && accessMode === "hallway" && (() => {
                // 3 APs evenly spaced along the center spine
                const N = 3;
                return Array.from({ length: N }).map((_, i) => {
                  const t = (i + 0.5) / N;
                  const ux = xSpineStart + (xSpineEnd - xSpineStart) * t;
                  const apId = `${String(floor).padStart(2, "0")}-AP${i + 1}`;
                  return renderAccess && renderAccess({
                    key: apId,
                    x: ux, y: y + 1, z: zSpine,
                    apId, floorId: floor, side: "H",
                    sceneYaw: yaw, scenePitch: pitch,
                    selected, setSelected,
                  });
                });
              })()}
            </React.Fragment>
          );
        })}

        {/* === TRUNK (riser) — runs through floors; MDF amber === */}
        <Edge3D
          from={[xC, yTrunkBot, zC]} to={[xC, yTrunkTop, zC]}
          color={MDF_COLOR} thickness={2} animated />

        {/* === IDFs as taps on the trunk — lime === */}
        {layers.idf && idfPlan.map((p) => {
          const yIDF = yForFloor(p.floor);
          const id = `idf-${p.floor}`;
          const sortedServes = p.serves.slice().sort((a, b) => a - b);
          return (
            <Node3D key={id} x={xC} y={yIDF + 2} z={zC}
              size={11} color={IDF_COLOR}
              label={layers.labels ? `IDF · F${p.floor}` : null}
              sublabel={layers.labels ? `serves ${sortedServes[0]}–${sortedServes[sortedServes.length - 1]}` : null}
              sceneYaw={yaw} scenePitch={pitch}
              selected={selected?.id === id}
              onClick={() => setSelected({
                id, kind: "IDF",
                title: `IDF · Floor ${p.floor}`,
                subtitle: `Serves floors ${sortedServes.join(", ")} · ${accessLabel}`,
                // Stats hidden for now (DAWN-1490).
                stats: statsForIDF ? statsForIDF(p) : [],
                status: "online", uptime: "99.96%",
              })}
            />
          );
        })}

        {/* === MDF — basement floor OR rooftop bulkhead, depending on placement === */}
        {!isRoof && (
          <>
            <Place3D x={0} y={yMDF + GAP / 2} z={0}>
              <FloorPlane w={FW} d={FD} color="rgba(232,224,240,0.02)" stroke={TOWER_DIM} dashed />
            </Place3D>
            <Edge3D from={[-FW / 2, yMDF + GAP / 2, -FD / 2]} to={[FW / 2, yMDF + GAP / 2, -FD / 2]} color={TOWER_DIM} thickness={0.5} />
            <Edge3D from={[FW / 2, yMDF + GAP / 2, -FD / 2]} to={[FW / 2, yMDF + GAP / 2, FD / 2]} color={TOWER_DIM} thickness={0.5} />
            <Edge3D from={[FW / 2, yMDF + GAP / 2, FD / 2]} to={[-FW / 2, yMDF + GAP / 2, FD / 2]} color={TOWER_DIM} thickness={0.5} />
            <Edge3D from={[-FW / 2, yMDF + GAP / 2, FD / 2]} to={[-FW / 2, yMDF + GAP / 2, -FD / 2]} color={TOWER_DIM} thickness={0.5} />
            {layers.labels && (
              <FloorLabel x={-FW / 2 - 22} y={yMDF + 4} z={FD / 2 + 4}
                text="MDF" color="var(--fg-2)"
                sceneYaw={yaw} scenePitch={pitch} />
            )}
          </>
        )}

        {isRoof && (() => {
          // Rooftop bulkhead — centered machine-room box on the roof.
          const BW = 150, BD = 110, BH = GAP * 1.6;
          const yBulkBot = yTop + GAP / 2;        // sits on the roof
          const yBulkTop = yBulkBot + BH;
          const cs = [[-BW / 2, -BD / 2], [BW / 2, -BD / 2], [BW / 2, BD / 2], [-BW / 2, BD / 2]];
          return (
            <Place3D x={xMDF} y={0} z={zMDF}>
              {/* Bulkhead floor (the roof slab patch) */}
              <Place3D x={0} y={yBulkBot} z={0}>
                <FloorPlane w={BW} d={BD} color="rgba(232,224,240,0.04)" stroke={TOWER_DIM} />
              </Place3D>
              {/* Bulkhead ceiling */}
              <Place3D x={0} y={yBulkTop} z={0}>
                <FloorPlane w={BW} d={BD} color="rgba(232,224,240,0.06)" stroke={TOWER_LINE} />
              </Place3D>
              {/* Vertical corner posts */}
              {cs.map(([cx, cz], ci) => (
                <Edge3D key={`bk-c-${ci}`}
                  from={[cx, yBulkBot, cz]} to={[cx, yBulkTop, cz]}
                  color={TOWER_LINE} thickness={1} />
              ))}
              {/* Bottom + top edges */}
              {cs.map(([cx, cz], ci) => {
                const [nx, nz] = cs[(ci + 1) % 4];
                return (
                  <React.Fragment key={`bk-h-${ci}`}>
                    <Edge3D from={[cx, yBulkBot, cz]} to={[nx, yBulkBot, nz]} color={TOWER_LINE} thickness={0.5} />
                    <Edge3D from={[cx, yBulkTop, cz]} to={[nx, yBulkTop, nz]} color={TOWER_LINE} thickness={0.5} />
                  </React.Fragment>
                );
              })}
              {/* Wall planes — translucent, for solidity */}
              <Place3D x={0} y={yBulkBot + BH / 2} z={-BD / 2}>
                <WallPlane w={BW} h={BH} color="rgba(232,224,240,0.04)" stroke="transparent" />
              </Place3D>
              <Place3D x={0} y={yBulkBot + BH / 2} z={BD / 2}>
                <WallPlane w={BW} h={BH} color="rgba(232,224,240,0.025)" stroke="transparent" />
              </Place3D>
              {layers.labels && (
                <FloorLabel
                  x={-BW / 2 - 14} y={yBulkBot + BH / 2} z={BD / 2 + 4}
                  text="MDF · BULKHEAD" color="var(--fg-2)"
                  sceneYaw={yaw} scenePitch={pitch} />
              )}
            </Place3D>
          );
        })()}

        {/* === MDF & POE nodes + carrier handoff === */}
        {(() => {
          // MDF position depends on placement (basement = trunk corner; roof = center).
          // In roof variant the MDF node sits ON the cable path so the cable
          // visibly enters and exits it; in basement variant it sits on the trunk corner.
          const yMDFnode = isRoof ? yRoofCable : yMDF + 2;
          const mdfSubtitle = isRoof
            ? `Roof bulkhead · feeds ${idfPlan.length} IDFs via 100G riser`
            : `Basement · feeds ${idfPlan.length} IDFs via 100G riser`;
          const poeTitle = poeKind === "fwa"
            ? "Point of Entry · fixed-wireless"
            : "Point of Entry · 100G fiber";
          const poeSubtitle = poeKind === "fwa"
            ? `${poeProvider} 5G mmWave · rooftop antenna`
            : undefined;
          return (
            <>
              {/* Carrier handoff cable: POE → MDF.
                  Roof variant: cable runs FLAT along the roof from the antenna mast base to
                  the bulkhead. The mast itself (drawn below) is the only vertical run. */}
              {/* Carrier handoff cables.
                  Roof variant: both cables run FLAT at yRoofCable (above the
                  slab) so the horizontal→vertical transitions stay visible. */}
              <Edge3D
                from={[xPOE, isRoof ? yRoofCable : yPOE, zPOE]}
                to={[xMDF, isRoof ? yRoofCable : yMDF, zMDF]}
                color={MDF_COLOR} thickness={2} animated />
              {isRoof && (
                <Edge3D from={[xMDF, yRoofCable, zMDF]} to={[xC, yRoofCable, zC]}
                  color={MDF_COLOR} thickness={2} animated />
              )}

              <Node3D x={xMDF} y={yMDFnode} z={zMDF}
                size={16} color={MDF_COLOR}
                label={layers.labels ? "MDF · MPOE" : null}
                sublabel={layers.labels ? "main distribution" : null}
                sceneYaw={yaw} scenePitch={pitch}
                selected={selected?.id === "mdf"}
                onClick={() => setSelected({
                  id: "mdf", kind: "MDF",
                  title: "MDF · Main Point of Entry",
                  subtitle: mdfSubtitle,
                  // Stats hidden for now (DAWN-1490).
                  stats: [],
                  status: "online", uptime: "99.99%",
                })} />

              {/* POE — antenna mast + crossbars when FWA, otherwise just a node */}
              {poeKind === "fwa" && (() => {
                const yMastBot = yPOEBase;          // base of mast on the roof
                const yMastTop = yPOE;              // POE node sits at top
                return (
                  <>
                    <Edge3D from={[xPOE, yMastBot, zPOE]} to={[xPOE, yMastTop - 4, zPOE]}
                      color={TOWER_LINE} thickness={1} />
                    {/* Panel antenna crossbars */}
                    <Edge3D from={[xPOE - 8, yMastTop - 8, zPOE]} to={[xPOE + 8, yMastTop - 8, zPOE]}
                      color={POE_COLOR} thickness={1.2} />
                    <Edge3D from={[xPOE, yMastTop - 8, zPOE - 8]} to={[xPOE, yMastTop - 8, zPOE + 8]}
                      color={POE_COLOR} thickness={1.2} />
                  </>
                );
              })()}

              {/* Tenant rooftop broadcast antennas — small accessory feature.
                  Three short masts on the roof, each branching off the MDF, with
                  faint outward-expanding rings to suggest they're transmitting.
                  Kept small / low-opacity so it reads as background detail. */}
              {showBcast && layers.bcast && (
                <>
                  {broadcastSites.map((s, i) => {
                    const yTip = yRoof + s.h;
                    const isSel = selected?.id === s.id;
                    return (
                      <React.Fragment key={`bcast-${i}`}>
                        {/* Thin feed cable from MDF over to the antenna base */}
                        <Edge3D from={[xMDF, yRoofCable, zMDF]} to={[s.x, yRoofCable, s.z]}
                          color={BCAST_COLOR} thickness={isSel ? 1.4 : 0.7} dashed />
                        {/* Mast — thickens + brightens when selected */}
                        <Edge3D from={[s.x, yRoof, s.z]} to={[s.x, yTip, s.z]}
                          color={isSel ? "#FFFFFF" : BCAST_COLOR} thickness={isSel ? 2.4 : 1} />
                        {/* Tip dot — larger w/ selected ring when active */}
                        <Node3D x={s.x} y={yTip} z={s.z}
                          size={isSel ? 9 : 5} color={isSel ? "#FFFFFF" : BCAST_COLOR}
                          showLabel={false} selected={isSel}
                          onClick={() => setSelected({ key: "bcast", id: s.id })}
                          sceneYaw={yaw} scenePitch={pitch} />
                        {/* Outward broadcast waves — centered on the tip dot */}
                        <AntennaWaves x={s.x} y={yTip} z={s.z}
                          color={isSel ? "#FFFFFF" : BCAST_COLOR} sceneYaw={yaw} scenePitch={pitch}
                          direction="out" baseSize={isSel ? 22 : 16} count={3} />
                      </React.Fragment>
                    );
                  })}
                </>
              )}

              {/* Receiving ripple on the FWA carrier antenna — mirrors the
                  broadcast animation in reverse to show signal coming IN.
                  Centered on the POE node (yPOE + 2 to match Node3D below). */}
              {poeKind === "fwa" && (
                <AntennaWaves x={xPOE} y={yPOE + 2} z={zPOE}
                  color={POE_COLOR} sceneYaw={yaw} scenePitch={pitch}
                  direction="in" baseSize={22} count={3} />
              )}

              <Node3D x={xPOE} y={yPOE + 2} z={zPOE}
                size={13} color={POE_COLOR}
                label={layers.labels ? (poeKind === "fwa" ? "POE · FWA" : "POE · 100G") : null}
                sublabel={layers.labels ? (poeKind === "fwa" ? `${poeProvider} 5G` : poeProvider) : null}
                sceneYaw={yaw} scenePitch={pitch}
                selected={selected?.id === "poe"}
                onClick={() => setSelected({
                  id: "poe", kind: "POE",
                  title: poeTitle,
                  subtitle: poeSubtitle,
                  // Stats hidden for now (DAWN-1490).
                  stats: [],
                  status: "online", uptime: "99.99%",
                })} />
            </>
          );
        })()}
      </Scene3D>
  );

  const handleFocusDevice = (d: any, cat: any) => {
    setSelected({
      id: d.id, kind: cat.label.toUpperCase(),
      title: d.label, subtitle: cat.label,
      stats: [], status: "online", uptime: "99.99%",
    });
    // Desktop pans the device LEFT of center to clear the right panel
    // (~344px); compact stacks the panel below, so keep the node centered.
    focusOn(d.x, d.y, d.z, { zoom: compact ? 1.5 : 1.8, offsetX: compact ? 0 : -180 });
  };

  // ── Compact (mobile): 3D scene stacked over an in-flow detail dock,
  // dropping the desktop floating chrome (orbit readout, drag hints, side
  // description) that overflows a phone-width frame. ──
  if (compact) {
    return (
      <div className="av-artboard" style={{
        background: "var(--bg-2)", position: "relative", height: "100%",
        display: "flex", flexDirection: "column", overflow: "hidden",
      }}>
        <div style={{ position: "relative", flex: "1 1 56%", minHeight: 0, overflow: "hidden" }}>
          <div className="av-grid-bg" style={{ opacity: 0.14 }} />
          <PanelChrome accent={accent} project={project} onBack={onBack} compact />
          {sceneEl}
          <LayerBar layers={layers} setLayers={setLayers} accent={accent} compact />
        </div>
        <RightPanel
          catalog={deviceCatalog}
          accessLabel={accessLabel}
          accent={accent}
          selected={selected}
          setSelected={setSelected}
          onFocusDevice={handleFocusDevice}
          floorCount={TOTAL}
          compact />
      </div>
    );
  }

  return (
    <div className="av-artboard" style={{ background: "var(--bg-2)" }}>
      <div className="av-grid-bg" style={{ opacity: 0.14 }} />
      <PanelChrome accent={accent} project={project} onBack={onBack} />

      {sceneEl}

      <div style={{
        position: "absolute", top: 100, left: 24, zIndex: 3, maxWidth: 320,
        padding: "12px 14px", background: "rgba(10,8,20,0.7)",
        backdropFilter: "blur(8px)", WebkitBackdropFilter: "blur(8px)",
        border: "1px solid var(--line)", borderRadius: 8,
        fontFamily: "var(--font-sans)", fontSize: 12, lineHeight: 1.5,
        color: "var(--fg-2)",
      }}>
        Signal comes in from the {isRoof ? "roof via wireless" : "basement via fiber"}, to serve users via the <span style={{ color: accessColor, fontWeight: 500 }}>{accessLabel}</span> access system.
      </div>

      <RightPanel
        catalog={deviceCatalog}
        accessLabel={accessLabel}
        accent={accent}
        selected={selected}
        setSelected={setSelected}
        onFocusDevice={handleFocusDevice} />
      <LayerBar layers={layers} setLayers={setLayers} accent={accent} />
      <ControlsHint />
      <OrbitControls yaw={yaw} pitch={pitch} zoom={zoom} accent={accent}
        autoOn={autoOn}
        onAutoToggle={() => (autoOn ? setAutoOn(false) : enableAuto())}
        onReset={() => { reset(); setAutoOn(autoOrbit); }} />
    </div>
  );
}
