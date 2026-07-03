'use client';

// Shared primitives for Asset Visualizer concepts.
// - PanelChrome: simulates the reserves project-detail panel + visualize trigger
// - useSpin: drag-to-rotate the building (yaw only, capped tilt)
// - InfoPanel: right-side detail panel that appears when a node is selected

import * as React from 'react';

// Mock project header — simulates the reserves panel context.
// Includes the "Visualize this asset →" trigger as a pill button.
export function PanelChrome({ project = {}, accent = "var(--dawn-amber)", onBack, compact }: { project?: any; accent?: string; onBack?: () => void; compact?: boolean }) {
  const p = {
    name: "Drexel Plaza · 1421 Walnut",
    city: "Philadelphia, PA",
    chain: "DAWN-Activated Property",
    status: "live",
    ...project,
  };
  return (
    <div style={{
      position: "absolute", top: 0, left: 0, right: 0,
      padding: compact ? "12px 14px" : "20px 28px",
      background: "linear-gradient(180deg, rgba(11,8,20,0.92), rgba(11,8,20,0.0))",
      display: "flex", alignItems: "flex-start", gap: compact ? 12 : 18,
      zIndex: 5, pointerEvents: "none",
    }}>
      <div style={{ pointerEvents: "auto" }}>
        <button onClick={onBack} aria-label="Close visualizer" style={{
          width: compact ? 28 : 32, height: compact ? 28 : 32, borderRadius: 8, padding: 0,
          background: "rgba(255,255,255,0.04)",
          border: "1px solid var(--line)",
          color: "var(--fg-2)", cursor: "pointer",
          display: "inline-flex", alignItems: "center", justifyContent: "center",
          fontFamily: "var(--font-mono)", fontSize: compact ? 14 : 16, lineHeight: 1,
        }}>×</button>
      </div>
      <div style={{ flex: 1, minWidth: 0, pointerEvents: "auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span style={{
            width: 6, height: 6, borderRadius: 3, flexShrink: 0,
            background: "var(--pos)", boxShadow: "0 0 8px var(--pos)",
          }} />
          <span className="mono" style={{
            fontSize: compact ? 9 : 10, letterSpacing: "0.16em", color: "var(--fg-3)",
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}>
            LIVE · {p.city.toUpperCase()}{compact ? "" : ` · ${p.chain.toUpperCase()}`}
          </span>
        </div>
        <div style={{
          fontFamily: "var(--font-display)", fontWeight: 500,
          fontSize: compact ? 17 : 26, letterSpacing: "-0.02em", lineHeight: 1.1,
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: compact ? "nowrap" : "normal",
        }}>{p.name}</div>
      </div>
    </div>
  );
}

// Subtle controls hint — shows mouse interactions for the 3D scene.
// Placed at left-middle of the visualizer so it doesn't clash with
// the top header or bottom layer bar.
export function ControlsHint() {
  return (
    <div style={{
      position: "absolute", left: 24, top: 188,
      zIndex: 4, pointerEvents: "none", maxWidth: 320,
      fontFamily: "var(--font-sans)", fontSize: 12, lineHeight: 1.5,
      color: "var(--fg-2)",
      display: "flex", flexDirection: "column", gap: 3,
      padding: "12px 14px",
      background: "rgba(10,8,20,0.7)",
      backdropFilter: "blur(8px)", WebkitBackdropFilter: "blur(8px)",
      border: "1px solid var(--line)", borderRadius: 8,
    }}>
      <div><span style={{ color: "var(--fg)", fontWeight: 500 }}>Click a node</span> <span style={{ color: "var(--fg-3)" }}>to see details</span></div>
      <div><span style={{ color: "var(--fg)", fontWeight: 500 }}>Mouse wheel</span> <span style={{ color: "var(--fg-3)" }}>to zoom</span></div>
      <div><span style={{ color: "var(--fg)", fontWeight: 500 }}>Left click</span> <span style={{ color: "var(--fg-3)" }}>to orbit</span></div>
      <div><span style={{ color: "var(--fg)", fontWeight: 500 }}>Right click</span> <span style={{ color: "var(--fg-3)" }}>to pan</span></div>
    </div>
  );
}

// Bottom-left layer toggle bar. Layers: signal, idf, access, labels, throughput.
export function LayerBar({ layers, setLayers, accent = "var(--dawn-amber)", compact }: { layers: any; setLayers: (l: any) => void; accent?: string; compact?: boolean }) {
  const items = [
    { id: "idf", label: "IDF" },
    { id: "access", label: "Access" },
    { id: "bcast", label: compact ? "Wireless" : "Wireless Distribution" },
    { id: "labels", label: "Labels" },
  ];
  return (
    <div style={{
      position: "absolute", bottom: compact ? 8 : 24,
      left: compact ? 8 : 24, ...(compact ? { right: 8, justifyContent: "center", flexWrap: "wrap" } : {}),
      zIndex: 4,
      display: "flex", gap: 4, padding: 4,
      background: "rgba(11,8,20,0.7)",
      backdropFilter: "blur(10px)",
      WebkitBackdropFilter: "blur(10px)",
      border: "1px solid var(--line)",
      borderRadius: 10,
    }}>
      {items.map(it => (
        <button key={it.id} onClick={() => setLayers((l: any) => ({ ...l, [it.id]: !l[it.id] }))} style={{
          padding: compact ? "6px 9px" : "8px 12px", fontSize: compact ? 10 : 11,
          fontFamily: "var(--font-mono)", letterSpacing: "0.08em", textTransform: "uppercase",
          background: layers[it.id] ? `${accent}1A` : "transparent",
          color: layers[it.id] ? accent : "var(--fg-3)",
          border: layers[it.id] ? `1px solid ${accent}55` : "1px solid transparent",
          borderRadius: 6, cursor: "pointer", whiteSpace: "nowrap",
        }}>{it.label}</button>
      ))}
    </div>
  );
}

// Side detail panel — shows when a node is selected.
export function NodeDetail({ node, onClose, accent = "var(--dawn-amber)" }: { node: any; onClose: () => void; accent?: string }) {
  if (!node) return null;
  return (
    <div style={{
      position: "absolute", top: 120, right: 24, width: 308, zIndex: 6,
      background: "linear-gradient(180deg, rgba(24,18,38,0.96), rgba(17,13,29,0.96))",
      backdropFilter: "blur(14px)",
      WebkitBackdropFilter: "blur(14px)",
      border: "1px solid var(--line-strong)",
      borderRadius: 14,
      padding: 20,
      animation: "fadeUp 320ms cubic-bezier(.2,.7,.2,1) both",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <span className="mono" style={{ fontSize: 10, letterSpacing: "0.16em", color: accent }}>
          {(node.kind || "NODE").toUpperCase()} · {node.id}
        </span>
        <button onClick={onClose} style={{
          width: 22, height: 22, borderRadius: 6,
          background: "rgba(255,255,255,0.04)", border: "1px solid var(--line)",
          color: "var(--fg-3)", cursor: "pointer", padding: 0,
          display: "inline-flex", alignItems: "center", justifyContent: "center",
        }}>×</button>
      </div>
      <div style={{
        fontFamily: "var(--font-display)", fontSize: 20, fontWeight: 500,
        letterSpacing: "-0.015em", marginBottom: 6,
      }}>{node.title}</div>
      {node.subtitle && (
        <div style={{ fontSize: 12, color: "var(--fg-3)", marginBottom: 16 }}>{node.subtitle}</div>
      )}

      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0,
        borderTop: "1px solid var(--line)",
      }}>
        {(node.stats || []).map((s: any, i: number) => (
          <div key={i} style={{
            padding: "12px 0",
            borderBottom: "1px solid var(--line)",
            borderRight: i % 2 === 0 ? "1px solid var(--line)" : "none",
            paddingRight: i % 2 === 0 ? 12 : 0,
            paddingLeft: i % 2 === 1 ? 12 : 0,
          }}>
            <div className="kicker" style={{ marginBottom: 6 }}>{s.label}</div>
            <div className="mono tabular" style={{
              fontSize: 16, color: s.color || "var(--fg)",
              letterSpacing: "-0.01em", fontWeight: 500,
            }}>{s.value}</div>
          </div>
        ))}
      </div>

      {node.status && (
        <div style={{
          marginTop: 14, padding: "10px 12px",
          background: node.status === "online" ? "var(--pos-bg)" : node.status === "degraded" ? "rgba(243,162,74,0.10)" : "var(--neg-bg)",
          border: `1px solid ${node.status === "online" ? "var(--pos-line)" : node.status === "degraded" ? "rgba(243,162,74,0.28)" : "var(--neg-line)"}`,
          borderRadius: 8,
          display: "flex", alignItems: "center", gap: 10,
          fontSize: 12,
        }}>
          <span style={{
            width: 6, height: 6, borderRadius: 3,
            background: node.status === "online" ? "var(--pos)" : node.status === "degraded" ? "var(--dawn-amber)" : "var(--neg)",
            boxShadow: `0 0 8px currentColor`,
            color: node.status === "online" ? "var(--pos)" : node.status === "degraded" ? "var(--dawn-amber)" : "var(--neg)",
          }} />
          <span style={{ color: node.status === "online" ? "var(--pos)" : node.status === "degraded" ? "var(--dawn-amber)" : "var(--neg)" }}>
            {node.status === "online" ? "Operational" : node.status === "degraded" ? "Degraded" : "Offline"}
          </span>
          <span style={{ flex: 1 }} />
          <span className="mono" style={{ fontSize: 10, letterSpacing: "0.12em", color: "var(--fg-3)" }}>
            UPTIME <span className="tabular" style={{ color: "var(--fg-2)" }}>{node.uptime || "99.94%"}</span>
          </span>
        </div>
      )}
    </div>
  );
}

// Glow node — clickable disc that pulses.
export function GlowNode({ x, y, size = 14, color, label, sublabel, selected, onClick, kind = "node", showLabel = true }: { x: number; y: number; size?: number; color?: string; label?: any; sublabel?: any; selected?: boolean; onClick?: () => void; kind?: string; showLabel?: boolean }) {
  const c = color || "var(--dawn-amber)";
  return (
    <g style={{ cursor: "pointer" }} onClick={onClick}>
      {/* outer ring (pulse on selected) */}
      <circle cx={x} cy={y} r={size * 1.6} fill={c} opacity={selected ? 0.22 : 0.10}>
        {selected && <animate attributeName="r" values={`${size * 1.4};${size * 2.2};${size * 1.4}`} dur="1.6s" repeatCount="indefinite" />}
        {selected && <animate attributeName="opacity" values="0.4;0;0.4" dur="1.6s" repeatCount="indefinite" />}
      </circle>
      <circle cx={x} cy={y} r={size * 1.0} fill={c} opacity="0.18" />
      <circle cx={x} cy={y} r={size * 0.55} fill={c} stroke="#fff" strokeWidth={selected ? 1.4 : 0.8} strokeOpacity={selected ? 0.9 : 0.4} />
      {showLabel && label && (
        <g transform={`translate(${x + size * 1.4}, ${y - size * 0.4})`}>
          <text fontFamily="JetBrains Mono, monospace" fontSize="9" letterSpacing="1.2" fill="var(--fg-2)">{label}</text>
          {sublabel && <text y="11" fontFamily="JetBrains Mono, monospace" fontSize="8" letterSpacing="0.8" fill="var(--fg-3)">{sublabel}</text>}
        </g>
      )}
    </g>
  );
}

// OrbitControls — readout + reset, replaces old SpinControls for 3D scenes.
export function OrbitControls({ yaw, pitch, zoom, onReset, autoOn, onAutoToggle, accent = "var(--dawn-amber)" }: { yaw: number; pitch: number; zoom: number; onReset: () => void; autoOn?: boolean; onAutoToggle?: () => void; accent?: string }) {
  const btnStyle = (active: boolean): React.CSSProperties => ({
    padding: "8px 12px", fontSize: 11,
    fontFamily: "var(--font-mono)", letterSpacing: "0.12em", textTransform: "uppercase",
    background: active ? `${accent}22` : "rgba(11,8,20,0.7)",
    backdropFilter: "blur(10px)", WebkitBackdropFilter: "blur(10px)",
    border: `1px solid ${active ? accent : "var(--line)"}`,
    color: active ? accent : "var(--fg-2)", borderRadius: 8, cursor: "pointer",
  });
  return (
    <div style={{
      // v5 puts OrbitControls at right:24, but our RightPanel (width:380,
      // right:24, bottom:24) extends down to bottom:24 and would cover the
      // controls. Shift left so they sit just outside the RightPanel's left
      // edge: 24 + 380 (panel width) + 8 (gap) = 412.
      position: "absolute", bottom: 24, right: 412, zIndex: 4,
      display: "flex", gap: 8, alignItems: "center",
    }}>
      <span className="mono" style={{
        fontSize: 10, letterSpacing: "0.14em", color: "var(--fg-3)",
        padding: "8px 12px", background: "rgba(11,8,20,0.7)",
        backdropFilter: "blur(10px)", WebkitBackdropFilter: "blur(10px)",
        border: "1px solid var(--line)", borderRadius: 8,
      }}>
        YAW <span className="tabular" style={{ color: "var(--fg-2)" }}>{Math.round(((yaw % 360) + 360) % 360)}°</span> &nbsp;
        PITCH <span className="tabular" style={{ color: "var(--fg-2)" }}>{Math.round(pitch)}°</span> &nbsp;
        ZOOM <span className="tabular" style={{ color: "var(--fg-2)" }}>{zoom.toFixed(2)}×</span>
      </span>
      {onAutoToggle && (
        <button onClick={onAutoToggle} style={btnStyle(!!autoOn)}>
          {autoOn ? "▪ Auto-pan on" : "▸ Auto-pan"}
        </button>
      )}
      <button onClick={onReset} style={btnStyle(false)}>Reset view</button>
    </div>
  );
}

// v5 signal-description block (AVAccessConcepts.jsx 863–872) — verbatim.
export function SignalDescription({ isRoof, accessLabel, accessColor }: { isRoof: boolean; accessLabel: string; accessColor: string }) {
  return (
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
  );
}
