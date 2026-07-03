'use client';

// Shared 3D primitives — CSS 3D transforms.
// Building space convention:
//   - X right, Y up, Z toward camera
//   - Floors are flat planes laid in XZ plane (rotateX(90deg)) at varying Y
//   - All children of <Scene3D> live in a transform-style: preserve-3d world
//   - Camera is implicit; we rotate the world via yaw (around Y) + pitch (around X)
//   - <Plane3D>, <Edge3D>, <Node3D> are convenience builders
//   - <Node3D> is BILLBOARDED: counter-rotates so it always faces camera

import * as React from 'react';
import { useEffect, useRef } from 'react';

// --------- Scene3D: world wrapper ---------
export function Scene3D({ yaw, pitch, zoom = 1, panX = 0, panY = 0, perspective = 2200, bind, children, style }: { yaw: number; pitch: number; zoom?: number; panX?: number; panY?: number; perspective?: number; bind?: any; children?: React.ReactNode; style?: React.CSSProperties }) {
  const sceneRef = useRef<HTMLDivElement | null>(null);
  // React's onWheel is passive — preventDefault() is ignored, so wheel events
  // bubble up and scroll the page. Attach a non-passive native listener so the
  // visualizer can swallow the wheel cleanly.
  useEffect(() => {
    const el = sceneRef.current;
    if (!el || !bind?.onWheel) return;
    const handler = (e: WheelEvent) => { e.preventDefault(); bind.onWheel(e); };
    el.addEventListener("wheel", handler, { passive: false });
    return () => el.removeEventListener("wheel", handler);
  }, [bind?.onWheel]);
  // Click-routing fallback: when the user clicks anywhere in the scene, find
  // EVERY Node3D wrapper rendered under that screen point (regardless of
  // depth) and trigger whichever one's visual center is closest to the click.
  // This makes nodes clickable even when occluded by floors/walls/other
  // node hit-areas. Without this, the browser's natural hit-test picks the
  // topmost element with pointer-events:auto — which is sometimes a closer,
  // unrelated node's giant hit area instead of the IDF you were aiming at.
  const handleSceneClick = (e: any) => {
    const startEl = e.target;
    if (startEl && startEl.closest && startEl.closest("[data-node3d='1']")) {
      // The native click already landed on a node — let it fire normally.
      return;
    }
    const stack = (typeof document.elementsFromPoint === "function")
      ? document.elementsFromPoint(e.clientX, e.clientY) : [];
    const candidates = stack
      .map((el: any) => el.closest && el.closest("[data-node3d='1']"))
      .filter((el: any, i: number, arr: any[]) => el && arr.indexOf(el) === i);
    if (!candidates.length) return;
    // Pick the candidate whose visual center is closest to the click point —
    // i.e. the node the user was actually aiming at.
    let best: any = null, bestD = Infinity;
    for (const el of candidates) {
      const r = el.getBoundingClientRect();
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      const d = (cx - e.clientX) ** 2 + (cy - e.clientY) ** 2;
      if (d < bestD) { bestD = d; best = el; }
    }
    if (best && typeof best.__node3dClick === "function") {
      e.stopPropagation();
      best.__node3dClick();
    }
  };
  // Strip onWheel from the spread so React doesn't double-bind.
  const { onWheel: _omitted, ...bindNoWheel } = bind || {};
  return (
    <div {...bindNoWheel}
      ref={sceneRef}
      onClick={handleSceneClick}
      style={{
        position: "absolute", inset: 0,
        perspective: `${perspective}px`,
        perspectiveOrigin: "50% 50%",
        touchAction: "none",
        cursor: "grab",
        ...style,
      }}
    >
      <div style={{
        position: "absolute", inset: 0,
        transformStyle: "preserve-3d",
        transform: `translate(${panX}px, ${panY}px) translateZ(0) scale(${zoom}) rotateX(${-pitch}deg) rotateY(${yaw}deg)`,
        transition: "transform 60ms linear",
      }}>
        {children}
      </div>
    </div>
  );
}

// Position children inside the world. (x,y,z) in scene units (px-ish).
export function Place3D({ x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0, children, style }: { x?: number; y?: number; z?: number; rx?: number; ry?: number; rz?: number; children?: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{
      position: "absolute", left: "50%", top: "50%",
      transformStyle: "preserve-3d",
      transform: `translate3d(${x}px, ${-y}px, ${z}px) rotateX(${rx}deg) rotateY(${ry}deg) rotateZ(${rz}deg)`,
      ...style,
    }}>
      {children}
    </div>
  );
}

// Flat plane in XZ (a floor slab). w along X, d along Z.
export function FloorPlane({ w, d, color = "rgba(157,234,255,0.06)", stroke = "rgba(157,234,255,0.4)", grid = false, gridStep = 40, dashed = false, children, style }: { w: number; d: number; color?: string; stroke?: string; grid?: boolean; gridStep?: number; dashed?: boolean; children?: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{
      position: "absolute",
      width: w, height: d,
      left: -w / 2, top: -d / 2,
      transformStyle: "preserve-3d",
      transform: "rotateX(90deg)",
      background: color,
      border: dashed ? `1px dashed ${stroke}` : `1px solid ${stroke}`,
      backgroundImage: grid
        ? `linear-gradient(${stroke}33 1px, transparent 1px), linear-gradient(90deg, ${stroke}33 1px, transparent 1px)`
        : undefined,
      backgroundSize: grid ? `${gridStep}px ${gridStep}px` : undefined,
      pointerEvents: "none",
      ...style,
    }}>
      {children}
    </div>
  );
}

// Vertical wall plane — w along X, h along Y. Place at z = depth.
export function WallPlane({ w, h, color = "rgba(157,234,255,0.05)", stroke = "rgba(157,234,255,0.3)", style, children }: { w: number; h: number; color?: string; stroke?: string; style?: React.CSSProperties; children?: React.ReactNode }) {
  return (
    <div style={{
      position: "absolute",
      width: w, height: h,
      left: -w / 2, top: -h / 2,
      transformStyle: "preserve-3d",
      background: color,
      border: `1px solid ${stroke}`,
      pointerEvents: "none",
      ...style,
    }}>{children}</div>
  );
}

// Axis-aligned thin line in 3D between two points (visual edge).
// Implemented as a thin div rotated/scaled to span the segment.
export function Edge3D({ from = [0, 0, 0], to = [0, 0, 0], color = "rgba(157,234,255,0.5)", thickness = 1, dashed = false, animated = false }: { from?: [number, number, number]; to?: [number, number, number]; color?: string; thickness?: number; dashed?: boolean; animated?: boolean }) {
  const [x1, y1, z1] = from; const [x2, y2, z2] = to;
  const dx = x2 - x1, dy = y2 - y1, dz = z2 - z1;
  const len = Math.sqrt(dx * dx + dy * dy + dz * dz);
  if (len < 0.001) return null;
  // We can't easily make a single 3D line in CSS; simulate with a thin box rotated to point along the direction.
  // Compute rotation: align +X axis to (dx,dy,dz).
  const yawA = Math.atan2(dz, dx) * 180 / Math.PI;
  const horiz = Math.sqrt(dx * dx + dz * dz);
  const pitchA = -Math.atan2(dy, horiz) * 180 / Math.PI;
  return (
    <div style={{
      position: "absolute", left: "50%", top: "50%",
      transformStyle: "preserve-3d",
      transform: `translate3d(${x1}px, ${-y1}px, ${z1}px) rotateY(${-yawA}deg) rotateZ(${pitchA}deg)`,
      width: 0, height: 0,
      pointerEvents: "none",
    }}>
      <div style={{
        position: "absolute",
        width: len, height: thickness,
        background: dashed ? `repeating-linear-gradient(90deg, ${color} 0 4px, transparent 4px 8px)` : color,
        opacity: 0.9,
        transformOrigin: "0 50%",
        boxShadow: `0 0 6px ${color}`,
        animation: animated ? "edge-flow 1s linear infinite" : undefined,
        pointerEvents: "none",
      }} />
    </div>
  );
}

// Glow billboard node — counter-rotates against parent yaw/pitch so it
// always faces camera. Pass scene yaw/pitch in via props.
export function Node3D({ x = 0, y = 0, z = 0, size = 14, color = "#F3A24A", label, sublabel, selected, onClick, sceneYaw = 0, scenePitch = 0, showLabel = true, kind = "node" }: { x?: number; y?: number; z?: number; size?: number; color?: string; label?: any; sublabel?: any; selected?: boolean; onClick?: () => void; sceneYaw?: number; scenePitch?: number; showLabel?: boolean; kind?: string }) {
  // Billboard: apply inverse rotation
  const billboard = `rotateY(${-sceneYaw}deg) rotateX(${scenePitch}deg)`;
  // Hit area: large enough to be easy to click, but bounded so it doesn't
  // sprawl across neighbors. Crucially, ONLY this wrapper accepts pointer
  // events — every visual child (halo, core, ring, label) is pointer-transparent
  // so neighboring nodes' giant halos can't steal clicks at unfortunate angles.
  // If no onClick is passed, the node is purely decorative — no hit area, no
  // cursor change, no event handlers. (Used for access layer dots: they are
  // visual circles only; selection happens at the layer level via the panel.)
  const interactive = typeof onClick === "function";
  const hit = Math.max(size * 4.0, 56);
  const centerChild: React.CSSProperties = { position: "absolute", left: "50%", top: "50%", pointerEvents: "none" };
  return (
    <Place3D x={x} y={y} z={z}>
      <div
        ref={(el: any) => {
          if (!el) return;
          // Stash the click handler on the DOM node so Scene3D's
          // click-through fallback can invoke us when occluded.
          el.__node3dClick = interactive ? onClick : null;
        }}
        data-node3d={interactive ? "1" : undefined}
        onClick={interactive ? (e) => { e.stopPropagation(); onClick!(); } : undefined}
        onPointerDown={interactive ? (e) => e.stopPropagation() : undefined}
        style={{
          transform: `translate(-50%, -50%) ${billboard}`,
          transformStyle: "preserve-3d",
          cursor: interactive ? "pointer" : "default",
          position: "relative",
          width: interactive ? hit : 0,
          height: interactive ? hit : 0,
          pointerEvents: interactive ? "auto" : "none",
        }}
      >
        {/* outer halo */}
        <div style={{
          ...centerChild,
          width: size * 3.2, height: size * 3.2,
          marginLeft: -size * 1.6, marginTop: -size * 1.6,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${color}55 0%, ${color}00 70%)`,
          opacity: selected ? 0.9 : 0.55,
          animation: "node-pulse 2s ease-in-out infinite",
        }} />
        {/* core */}
        <div style={{
          ...centerChild,
          width: size, height: size,
          marginLeft: -size / 2, marginTop: -size / 2,
          borderRadius: "50%",
          background: color,
          boxShadow: `0 0 ${size}px ${color}, 0 0 ${size * 2}px ${color}88`,
          border: selected ? "1.5px solid #fff" : "1px solid rgba(255,255,255,0.5)",
        }} />
        {/* selected ring */}
        {selected && (
          <div style={{
            ...centerChild,
            width: size * 2.2, height: size * 2.2,
            marginLeft: -size * 1.1, marginTop: -size * 1.1,
            borderRadius: "50%",
            border: `1px solid ${color}`,
            animation: "node-ring 1.6s ease-out infinite",
          }} />
        )}
        {showLabel && label && (
          <div style={{
            ...centerChild,
            marginLeft: size * 1.1, marginTop: -size * 0.5,
            whiteSpace: "nowrap",
            fontFamily: "var(--font-mono)",
            fontSize: 9, letterSpacing: "0.12em",
            color: "var(--fg-2)",
          }}>
            {label}
            {sublabel && <div style={{ fontSize: 8, color: "var(--fg-3)", marginTop: 2 }}>{sublabel}</div>}
          </div>
        )}
      </div>
    </Place3D>
  );
}

// Floor label — a small billboarded text marker at floor edge.
export function FloorLabel({ x, y, z, text, color = "var(--fg-3)", sceneYaw = 0, scenePitch = 0 }: { x: number; y: number; z: number; text: string; color?: string; sceneYaw?: number; scenePitch?: number }) {
  return (
    <Place3D x={x} y={y} z={z}>
      <div style={{
        transform: `rotateY(${-sceneYaw}deg) rotateX(${scenePitch}deg)`,
        whiteSpace: "nowrap",
        fontFamily: "var(--font-mono)",
        fontSize: 9, letterSpacing: "0.16em",
        color, opacity: 0.85,
        pointerEvents: "none",
      }}>{text}</div>
    </Place3D>
  );
}

// Small billboarded ripple sprite for antennas — outward-expanding rings for
// transmitting, contracting rings for receiving. Kept low-opacity / small so
// it reads as a detail, not a hero element.
export function AntennaWaves({ x, y, z, color = "#E48DD0", sceneYaw = 0, scenePitch = 0, direction = "out", baseSize = 14, count = 3 }: { x: number; y: number; z: number; color?: string; sceneYaw?: number; scenePitch?: number; direction?: "in" | "out"; baseSize?: number; count?: number }) {
  const billboard = `rotateY(${-sceneYaw}deg) rotateX(${scenePitch}deg)`;
  const anim = direction === "in" ? "wave-in" : "wave-out";
  return (
    <Place3D x={x} y={y} z={z}>
      <div style={{ transform: billboard, position: "relative", width: 0, height: 0, pointerEvents: "none" }}>
        {Array.from({ length: count }).map((_, i) => (
          <div key={i} style={{
            position: "absolute",
            left: -baseSize / 2, top: -baseSize / 2,
            width: baseSize, height: baseSize, borderRadius: "50%",
            border: `1px solid ${color}`,
            boxShadow: `0 0 6px ${color}55`,
            opacity: 0,
            animation: `${anim} 2.4s ease-out ${i * 0.8}s infinite`,
          }} />
        ))}
      </div>
    </Place3D>
  );
}
