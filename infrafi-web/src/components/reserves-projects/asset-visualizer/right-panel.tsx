'use client';

import { useState } from 'react';

// Unified right-side overlay: top 60% logic tree, bottom 40% detail pane.
// Categories expand inline to show their devices (except Access Devices, which
// is treated as a single selectable layer). Clicking a device focuses the
// camera and populates the detail pane below.
export function RightPanel({ catalog, accessLabel, selected, setSelected, onFocusDevice, accent, floorCount = 14, compact }: { catalog: any; accessLabel?: string; selected: any; setSelected: (s: any) => void; onFocusDevice: (d: any, cat: any) => void; accent?: string; floorCount?: number; compact?: boolean }) {
  const [open, setOpen] = useState<string | null>(null);
  const W = 380;

  // IDF and Distribution Antennas are shown in the logical diagram but are not
  // interactive — no expand, no selection (DAWN-1490).
  const NON_CLICKABLE = new Set(["idf", "bcast"]);

  const layout: any = {
    poe:   { col: "center", row: 0 },
    mdf:   { col: "center", row: 1 },
    idf:   { col: "left",   row: 2 },
    bcast: { col: "right",  row: 2 },
    access:{ col: "left",   row: 3 },
  };
  const NODE_W = 150;
  const colX: any = { left: 12 + NODE_W / 2, center: W / 2, right: W - 12 - NODE_W / 2 };
  const ROW_H = 48;
  // Cloud icon sits above the POE row to represent "the internet" — uplink
  // upstream of the building's point of entry. We push every node down by
  // CLOUD_OFFSET to make room.
  const CLOUD_OFFSET = 56;
  const CLOUD_Y = 26;
  const order = catalog.map((c: any) => c.key);
  const pos: any = {};
  for (const k of order) {
    const L = layout[k] || { col: "center", row: order.indexOf(k) };
    pos[k] = { x: colX[L.col], y: 24 + L.row * ROW_H + CLOUD_OFFSET };
  }
  const treeH = 24 + (Math.max(...order.map((k: any) => (layout[k]?.row ?? 0))) + 1) * ROW_H + 4 + CLOUD_OFFSET;

  const edges = [
    ["poe", "mdf"],
    ["mdf", "idf"],
    ["mdf", "bcast"],
    ["idf", "access"],
  ].filter(([a, b]) => catalog.find((c: any) => c.key === a) && catalog.find((c: any) => c.key === b));

  const handleCategoryClick = (cat: any) => {
    if (cat.key === "access") {
      // Access is a layer-level selection — no per-device list. Direct select.
      setSelected({
        id: "access-layer",
        kind: "ACCESS LAYER",
        title: `Access Layer · ${accessLabel || cat.label}`,
        subtitle: `${cat.devices.length} access devices across ${floorCount} floors`,
        stats: [
          { label: "Devices", value: String(cat.devices.length) },
          { label: "Floors", value: String(floorCount) },
          { label: "Type", value: accessLabel || "Access" },
          { label: "Mode", value: "in-unit / hallway" },
        ],
        status: "online", uptime: "99.96%",
      });
      setOpen(null);
    } else {
      setOpen(open === cat.key ? null : cat.key);
    }
  };

  // ── Compact (mobile): in-flow dock below the 3D scene. Category chips on
  // top, then the selected-node detail (or the chosen layer's device list). ──
  if (compact) {
    const openCat = open ? catalog.find((c: any) => c.key === open) : null;
    return (
      <div style={{
        position: "relative", width: "100%", flex: "1 1 44%", minHeight: 150,
        borderTop: "1px solid var(--line)", background: "rgba(10,8,20,0.6)",
        display: "flex", flexDirection: "column",
        fontFamily: "var(--font-mono)", color: "var(--fg-2)", overflow: "hidden",
      }}>
        {/* Category chips */}
        <div style={{ display: "flex", gap: 6, padding: "10px 10px 8px", overflowX: "auto", borderBottom: "1px solid var(--line)", flex: "none" }}>
          {catalog.map((cat: any) => {
            const isAccess = cat.key === "access";
            const inert = NON_CLICKABLE.has(cat.key);
            const active = (open === cat.key && !isAccess) || (isAccess && selected?.id === "access-layer");
            return (
              <button key={cat.key}
                onClick={inert ? undefined : () => { setSelected(null); handleCategoryClick(cat); }}
                disabled={inert}
                style={{
                  display: "inline-flex", alignItems: "center", gap: 6, flexShrink: 0,
                  padding: "6px 10px", borderRadius: 999,
                  background: active ? `${cat.color}22` : "rgba(255,255,255,0.02)",
                  border: `1px solid ${active ? cat.color : "var(--line)"}`,
                  color: active ? cat.color : "var(--fg-2)",
                  fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.06em",
                  cursor: inert ? "default" : "pointer", whiteSpace: "nowrap",
                }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: cat.color, boxShadow: `0 0 6px ${cat.color}`, flex: "none" }} />
                {cat.short || cat.label}
                <span style={{ color: "var(--fg-3)", fontSize: 9 }}>{cat.devices.length}</span>
              </button>
            );
          })}
        </div>

        {/* Body: selected detail → device list → hint */}
        <div style={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
          {selected ? (
            <div style={{ padding: "12px 14px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10, marginBottom: 8 }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 9, letterSpacing: "0.16em", color: accent, marginBottom: 4 }}>{(selected.kind || "NODE").toUpperCase()}</div>
                  <div style={{ fontFamily: "var(--font-display)", fontSize: 16, fontWeight: 500, letterSpacing: "-0.015em" }}>{selected.title}</div>
                  {selected.subtitle && <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 2 }}>{selected.subtitle}</div>}
                </div>
                <button onClick={() => setSelected(null)} style={{ width: 24, height: 24, flexShrink: 0, borderRadius: 6, background: "rgba(255,255,255,0.04)", border: "1px solid var(--line)", color: "var(--fg-3)", cursor: "pointer", fontFamily: "var(--font-mono)", fontSize: 14, lineHeight: 1 }}>×</button>
              </div>
              {selected.stats && selected.stats.length > 0 && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0, borderTop: "1px solid var(--line)", marginTop: 4 }}>
                  {selected.stats.map((s: any, i: number) => (
                    <div key={i} style={{ padding: "10px 0", borderBottom: "1px solid var(--line)", borderRight: i % 2 === 0 ? "1px solid var(--line)" : "none", paddingRight: i % 2 === 0 ? 10 : 0, paddingLeft: i % 2 === 1 ? 10 : 0 }}>
                      <div style={{ fontSize: 8, letterSpacing: "0.14em", color: "var(--fg-3)", textTransform: "uppercase", marginBottom: 4 }}>{s.label}</div>
                      <div style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: s.color || "var(--fg)", letterSpacing: "-0.01em", fontWeight: 500 }}>{s.value}</div>
                    </div>
                  ))}
                </div>
              )}
              {selected.status && (
                <div style={{ marginTop: 12, padding: "8px 10px", background: selected.status === "online" ? "var(--pos-bg)" : "rgba(243,162,74,0.10)", border: `1px solid ${selected.status === "online" ? "var(--pos-line)" : "rgba(243,162,74,0.28)"}`, borderRadius: 6, display: "flex", alignItems: "center", gap: 8, fontSize: 10 }}>
                  <span style={{ width: 6, height: 6, borderRadius: 3, background: selected.status === "online" ? "var(--pos)" : "var(--dawn-amber)" }} />
                  <span style={{ color: selected.status === "online" ? "var(--pos)" : "var(--dawn-amber)" }}>{selected.status === "online" ? "Operational" : "Degraded"}</span>
                  <span style={{ flex: 1 }} />
                  <span style={{ fontSize: 8, letterSpacing: "0.12em", color: "var(--fg-3)" }}>UPTIME <span style={{ color: "var(--fg-2)" }}>{selected.uptime || "99.94%"}</span></span>
                </div>
              )}
            </div>
          ) : openCat ? (
            <div style={{ padding: "6px 0" }}>
              <div style={{ padding: "6px 14px", fontSize: 9, letterSpacing: "0.1em", color: openCat.color, fontWeight: 500, textTransform: "uppercase" }}>{openCat.devices.length} · {openCat.label}</div>
              {openCat.devices.map((d: any) => (
                <button key={d.id} onClick={() => onFocusDevice(d, openCat)} style={{ display: "flex", alignItems: "center", gap: 8, width: "100%", padding: "8px 14px", background: "transparent", border: "none", fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.05em", color: "var(--fg-2)", cursor: "pointer", textAlign: "left" }}>
                  <span style={{ width: 5, height: 5, borderRadius: "50%", background: openCat.color, opacity: 0.7, flex: "none" }} />
                  <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.label}</span>
                  <span style={{ color: "var(--fg-3)", fontSize: 9 }}>↗</span>
                </button>
              ))}
            </div>
          ) : (
            <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", padding: 16, textAlign: "center" }}>
              <div>
                <div style={{ fontFamily: "var(--font-display)", fontSize: 13, color: "var(--fg-2)", marginBottom: 4 }}>Tap a node in the scene</div>
                <div style={{ fontSize: 10, color: "var(--fg-3)", lineHeight: 1.5 }}>or pick a layer above to inspect</div>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div style={{
      position: "absolute", top: 24, right: 24, bottom: 24, zIndex: 4,
      width: W,
      background: "rgba(10,8,20,0.78)",
      backdropFilter: "blur(10px)", WebkitBackdropFilter: "blur(10px)",
      border: "1px solid var(--line)", borderRadius: 8,
      fontFamily: "var(--font-mono)", color: "var(--fg-2)",
      display: "flex", flexDirection: "column",
      overflow: "hidden",
    }}>
      {/* === Top 60% === LOGIC TREE === */}
      <div style={{
        flex: "0 0 60%", minHeight: 0,
        display: "flex", flexDirection: "column",
        borderBottom: "1px solid var(--line)",
      }}>
        <div style={{
          padding: "14px 16px 10px", fontSize: 13, letterSpacing: "-0.005em",
          color: "var(--fg)", borderBottom: "1px solid var(--line)",
          flex: "none", fontFamily: "var(--font-display)", fontWeight: 500,
        }}>
          Logical diagram <span style={{ color: "var(--fg-3)", fontWeight: 400 }}>· {accessLabel}</span>
        </div>

        <div style={{ overflowY: "auto", overflowX: "hidden", flex: 1 }}>
          {/* Tree diagram */}
          <div style={{ position: "relative", height: treeH, marginTop: 6 }}>
            <svg width={W} height={treeH} style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
              {/* Cloud — represents the internet uplink, drawn above POE */}
              {pos.poe && (() => {
                const cx = pos.poe.x, cy = CLOUD_Y;
                return (
                  <g key="cloud">
                    <path
                      d={`M ${cx - 26} ${cy + 4}
                          a 9 9 0 0 1 8 -8
                          a 11 11 0 0 1 21 -2
                          a 8 8 0 0 1 11 4
                          a 7 7 0 0 1 -3 13
                          l -34 0
                          a 7 7 0 0 1 -3 -7 z`}
                      fill="transparent"
                      stroke="var(--fg)"
                      strokeWidth="1"
                      strokeLinejoin="round" />
                    {/* Connector cloud → POE */}
                    <path d={`M${cx},${cy + 14} L${cx},${pos.poe.y - 8}`}
                      stroke="rgba(232,224,240,0.28)" strokeWidth="1" fill="none"
                      strokeDasharray="2 3" />
                  </g>
                );
              })()}
              {edges.map(([a, b], i) => {
                const A = pos[a], B = pos[b];
                if (!A || !B) return null;
                const midY = (A.y + B.y) / 2;
                const d = `M${A.x},${A.y + 8} L${A.x},${midY} L${B.x},${midY} L${B.x},${B.y - 8}`;
                return <path key={i} d={d} stroke="rgba(232,224,240,0.28)" strokeWidth="1" fill="none" />;
              })}
            </svg>
            {catalog.map((cat: any) => {
              const p = pos[cat.key];
              const expandable = cat.key !== "access";
              const active = open === cat.key && expandable;
              const isAccess = cat.key === "access";
              const inert = NON_CLICKABLE.has(cat.key);
              return (
                <button key={cat.key}
                  onClick={inert ? undefined : () => handleCategoryClick(cat)}
                  disabled={inert}
                  style={{
                    position: "absolute",
                    left: p.x - NODE_W / 2, top: p.y - 13, width: NODE_W, height: 26,
                    display: "flex", alignItems: "center", gap: 6,
                    padding: "0 8px",
                    background: active || (isAccess && selected?.id === "access-layer") ? `${cat.color}22` : "rgba(255,255,255,0.02)",
                    border: `1px solid ${active || (isAccess && selected?.id === "access-layer") ? cat.color : "var(--line)"}`,
                    borderRadius: 4,
                    fontFamily: "var(--font-mono)", fontSize: 9, letterSpacing: "0.06em",
                    color: active || (isAccess && selected?.id === "access-layer") ? cat.color : "var(--fg-2)",
                    cursor: inert ? "default" : "pointer", textAlign: "left",
                  }}>
                  <span style={{
                    width: 7, height: 7, borderRadius: "50%",
                    background: cat.color, boxShadow: `0 0 6px ${cat.color}`,
                    flex: "none",
                  }} />
                  <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {cat.short || cat.label}
                  </span>
                  <span style={{ color: "var(--fg-3)", fontSize: 8 }}>
                    {cat.devices.length}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Expanded device list */}
          {open && (() => {
            const cat = catalog.find((c: any) => c.key === open);
            if (!cat) return null;
            return (
              <div style={{
                borderTop: "1px solid var(--line)",
                padding: "6px 0",
              }}>
                <div style={{
                  padding: "4px 14px 6px", fontSize: 9, letterSpacing: "0.1em",
                  color: cat.color, fontWeight: 500, textTransform: "uppercase",
                }}>
                  {cat.devices.length} · {cat.label}
                </div>
                {cat.devices.map((d: any) => (
                  <button key={d.id}
                    onClick={() => onFocusDevice(d, cat)}
                    style={{
                      display: "flex", alignItems: "center", gap: 8,
                      width: "100%", padding: "6px 14px",
                      background: selected?.id === d.id ? "rgba(255,255,255,0.04)" : "transparent",
                      border: "none", borderLeft: `2px solid ${selected?.id === d.id ? cat.color : "transparent"}`,
                      fontFamily: "var(--font-mono)", fontSize: 9, letterSpacing: "0.05em",
                      color: "var(--fg-2)", cursor: "pointer", textAlign: "left",
                    }}
                    onMouseEnter={e => {
                      if (selected?.id !== d.id) {
                        e.currentTarget.style.background = "rgba(255,255,255,0.04)";
                        e.currentTarget.style.borderLeftColor = cat.color;
                      }
                    }}
                    onMouseLeave={e => {
                      if (selected?.id !== d.id) {
                        e.currentTarget.style.background = "transparent";
                        e.currentTarget.style.borderLeftColor = "transparent";
                      }
                    }}>
                    <span style={{
                      width: 5, height: 5, borderRadius: "50%",
                      background: cat.color, opacity: 0.7, flex: "none",
                    }} />
                    <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {d.label}
                    </span>
                    <span style={{ color: "var(--fg-3)", fontSize: 8 }}>↗</span>
                  </button>
                ))}
              </div>
            );
          })()}
        </div>
      </div>

      {/* === Bottom 40% === DETAIL PANE === */}
      <div style={{
        flex: "1 1 40%", minHeight: 0,
        display: "flex", flexDirection: "column",
      }}>
        {selected ? (
          <>
            <div style={{
              padding: "12px 14px 8px",
              display: "flex", justifyContent: "space-between", alignItems: "center",
              borderBottom: "1px solid var(--line)", flex: "none",
            }}>
              <span style={{ fontSize: 9, letterSpacing: "0.16em", color: accent }}>
                {(() => {
                  const k = (selected.kind || "NODE").toUpperCase();
                  const id = String(selected.id || "");
                  const kLower = k.toLowerCase();
                  // Skip the id suffix when it's just the kind name (e.g. "MDF · mdf"),
                  // or when it starts with the kind name (e.g. "IDF · idf-3").
                  if (!id || id.toLowerCase() === kLower || id.toLowerCase().startsWith(kLower + "-") || id.toLowerCase() === kLower.replace(/\s+/g, "-")) {
                    return k;
                  }
                  return `${k} · ${id}`;
                })()}
              </span>
              <button onClick={() => setSelected(null)} style={{
                width: 22, height: 22, borderRadius: 6,
                background: "rgba(255,255,255,0.04)", border: "1px solid var(--line)",
                color: "var(--fg-3)", cursor: "pointer", padding: 0,
                display: "inline-flex", alignItems: "center", justifyContent: "center",
                fontFamily: "var(--font-mono)", fontSize: 13, lineHeight: 1,
              }}>×</button>
            </div>
            <div style={{ overflowY: "auto", padding: "12px 14px", flex: 1 }}>
              <div style={{
                fontFamily: "var(--font-display)", fontSize: 16, fontWeight: 500,
                letterSpacing: "-0.015em", marginBottom: 4,
              }}>{selected.title}</div>
              {selected.subtitle && (
                <div style={{ fontSize: 11, color: "var(--fg-3)", marginBottom: 12 }}>{selected.subtitle}</div>
              )}
              {selected.stats && selected.stats.length > 0 && (
                <div style={{
                  display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0,
                  borderTop: "1px solid var(--line)",
                }}>
                  {selected.stats.map((s: any, i: number) => (
                    <div key={i} style={{
                      padding: "10px 0",
                      borderBottom: "1px solid var(--line)",
                      borderRight: i % 2 === 0 ? "1px solid var(--line)" : "none",
                      paddingRight: i % 2 === 0 ? 10 : 0,
                      paddingLeft: i % 2 === 1 ? 10 : 0,
                    }}>
                      <div style={{
                        fontSize: 8, letterSpacing: "0.14em",
                        color: "var(--fg-3)", textTransform: "uppercase",
                        marginBottom: 4,
                      }}>{s.label}</div>
                      <div style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 13, color: s.color || "var(--fg)",
                        letterSpacing: "-0.01em", fontWeight: 500,
                      }}>{s.value}</div>
                    </div>
                  ))}
                </div>
              )}
              {selected.status && (
                <div style={{
                  marginTop: 12, padding: "8px 10px",
                  background: selected.status === "online" ? "var(--pos-bg)" : "rgba(243,162,74,0.10)",
                  border: `1px solid ${selected.status === "online" ? "var(--pos-line)" : "rgba(243,162,74,0.28)"}`,
                  borderRadius: 6,
                  display: "flex", alignItems: "center", gap: 8,
                  fontSize: 10,
                }}>
                  <span style={{
                    width: 6, height: 6, borderRadius: 3,
                    background: selected.status === "online" ? "var(--pos)" : "var(--dawn-amber)",
                    boxShadow: `0 0 6px currentColor`,
                    color: selected.status === "online" ? "var(--pos)" : "var(--dawn-amber)",
                  }} />
                  <span style={{ color: selected.status === "online" ? "var(--pos)" : "var(--dawn-amber)" }}>
                    {selected.status === "online" ? "Operational" : "Degraded"}
                  </span>
                  <span style={{ flex: 1 }} />
                  <span style={{ fontSize: 8, letterSpacing: "0.12em", color: "var(--fg-3)" }}>
                    UPTIME <span style={{ color: "var(--fg-2)" }}>{selected.uptime || "99.94%"}</span>
                  </span>
                </div>
              )}
            </div>
          </>
        ) : (
          <div style={{
            flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
            padding: 24, textAlign: "center",
            fontSize: 10, color: "var(--fg-3)", letterSpacing: "0.1em",
          }}>
            <div>
              <div style={{ marginBottom: 8, fontSize: 9, letterSpacing: "0.18em", color: "var(--fg-3)" }}>NO SELECTION</div>
              <div style={{ fontFamily: "var(--font-display)", fontSize: 13, color: "var(--fg-2)", letterSpacing: 0, marginBottom: 6 }}>
                Click a node above to inspect
              </div>
              <div style={{ fontSize: 10, color: "var(--fg-3)", lineHeight: 1.5 }}>
                Or click any device in the 3D scene
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
