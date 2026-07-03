'use client';

// Shared 3D primitives — CSS 3D transforms.
// Building space convention:
//   - X right, Y up, Z toward camera
//   - Floors are flat planes laid in XZ plane (rotateX(90deg)) at varying Y
//   - All children of <Scene3D> live in a transform-style: preserve-3d world
//   - Camera is implicit; we rotate the world via yaw (around Y) + pitch (around X)
//   - <Plane3D>, <Edge3D>, <Node3D> are convenience builders
//   - <Node3D> is BILLBOARDED: counter-rotates so it always faces camera

import { useState, useEffect, useRef } from 'react';

// --------- Orbit hook: drag to rotate, wheel to zoom, idle auto-rotate ---------
export function useOrbit({ yaw: y0 = -22, pitch: p0 = 18, zoom: z0 = 1, autoRotate = true, oscillate = null }: { yaw?: number; pitch?: number; zoom?: number; autoRotate?: boolean; oscillate?: { range: number; period: number } | null } = {}) {
  const [yaw, setYaw] = useState(y0);
  const [pitch, setPitch] = useState(p0);
  const [zoom, setZoom] = useState(z0);
  const [panX, setPanX] = useState(0);
  const [panY, setPanY] = useState(0);
  const [interacting, setInteracting] = useState(false);
  const [autoOn, setAutoOn] = useState(autoRotate);
  const drag = useRef<any>(null);
  const idleTimer = useRef<any>(null);
  const rafRef = useRef<any>(null);
  const lastT = useRef(performance.now());
  const phaseRef = useRef(0);

  // Auto-rotate when enabled AND idle. User drag turns autoOn off; only
  // explicit toggle re-enables it. When re-enabled, snap phase to current yaw
  // so we don't jump.
  useEffect(() => {
    if (!autoOn) return;
    let cancelled = false;
    const tick = (t: number) => {
      if (cancelled) return;
      const dt = Math.min(64, t - lastT.current);
      lastT.current = t;
      if (!interacting) {
        if (oscillate) {
          phaseRef.current += dt;
          const omega = (2 * Math.PI) / (oscillate.period * 1000);
          const target = y0 + oscillate.range * Math.sin(phaseRef.current * omega);
          setYaw(y => y + (target - y) * 0.04);
        } else {
          setYaw(y => y + dt * 0.005);
        }
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => { cancelled = true; cancelAnimationFrame(rafRef.current); };
  }, [interacting, autoOn, oscillate, y0]);

  const onPointerDown = (e: any) => {
    // Right-click (or middle-click, or shift+left) starts a PAN drag.
    // Plain left-click starts an ORBIT drag.
    const isPan = e.button === 2 || e.button === 1 || e.shiftKey;
    drag.current = isPan
      ? { mode: "pan", x: e.clientX, y: e.clientY, panX, panY }
      : { mode: "orbit", x: e.clientX, y: e.clientY, yaw, pitch };
    setInteracting(true);
    setAutoOn(false);
    if (idleTimer.current) clearTimeout(idleTimer.current);
    e.target.setPointerCapture?.(e.pointerId);
  };
  const onPointerMove = (e: any) => {
    if (!drag.current) return;
    const dx = e.clientX - drag.current.x;
    const dy = e.clientY - drag.current.y;
    if (drag.current.mode === "pan") {
      // Pan in screen space; divide by zoom so feel stays constant when zoomed in
      setPanX(drag.current.panX + dx / zoom);
      setPanY(drag.current.panY + dy / zoom);
    } else {
      setYaw(drag.current.yaw + dx * 0.4);
      setPitch(Math.max(-5, Math.min(85, drag.current.pitch - dy * 0.25)));
    }
  };
  const endDrag = (e: any) => {
    drag.current = null;
    e.target?.releasePointerCapture?.(e.pointerId);
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(() => setInteracting(false), 1600);
  };
  const onWheel = (e: any) => {
    e.preventDefault();
    // Cursor-anchored zoom: keep the world point under the cursor at the
    // same screen position across zoom changes. After focusOn brings a
    // node into view, wheel-zooming keeps that node visually pinned (as
    // long as the cursor is over it), no follow-up pan needed.
    const target = e.currentTarget || e.target;
    const rect = target && typeof target.getBoundingClientRect === "function"
      ? target.getBoundingClientRect() : null;
    const cx = rect ? e.clientX - rect.left - rect.width / 2 : 0;
    const cy = rect ? e.clientY - rect.top - rect.height / 2 : 0;
    setZoom(z => {
      const nz = Math.max(0.5, Math.min(2.4, z * (1 - e.deltaY * 0.001)));
      const ratio = nz / z;
      setPanX(px => cx + (px - cx) * ratio);
      setPanY(py => cy + (py - cy) * ratio);
      return nz;
    });
  };
  const onContextMenu = (e: any) => { e.preventDefault(); };
  const reset = (next?: { yaw?: number; pitch?: number; zoom?: number }) => {
    setYaw(next?.yaw ?? y0);
    setPitch(next?.pitch ?? p0);
    setZoom(next?.zoom ?? z0);
    setPanX(0); setPanY(0);
    phaseRef.current = 0;
  };

  // Pan + zoom to bring a world-space (x,y,z) point to the screen center,
  // optionally offset (in screen pixels) so it lands left/right/up/down of
  // dead-center — useful for leaving room for a side panel.
  const focusOn = (wx: number, wy: number, wz: number, opts: { zoom?: number; offsetX?: number; offsetY?: number; perspective?: number } = {}) => {
    const targetZoom = opts.zoom ?? 1.7;
    const offsetX = opts.offsetX ?? 0;
    const offsetY = opts.offsetY ?? 0;
    const P = opts.perspective ?? 2200;
    const yawRad = (yaw * Math.PI) / 180;
    const pitchRad = (pitch * Math.PI) / 180;
    // rotateY(yaw) on (wx, -wy, wz)
    const Xrot = wx * Math.cos(yawRad) + wz * Math.sin(yawRad);
    const Zy   = -wx * Math.sin(yawRad) + wz * Math.cos(yawRad);
    // rotateX(-pitch) on (Xrot, -wy, Zy):
    //   y' = (-wy)*cos(pitch) + Zy*sin(pitch)
    //   z' = wy*sin(pitch)    + Zy*cos(pitch)
    const Yrot = -wy * Math.cos(pitchRad) + Zy * Math.sin(pitchRad);
    const Zrot =  wy * Math.sin(pitchRad) + Zy * Math.cos(pitchRad);
    // CSS perspective foreshortening factor at this depth:
    const zScaled = Zrot * targetZoom;
    const k = (P - zScaled) / P;
    setPanX(offsetX * k - Xrot * targetZoom);
    setPanY(offsetY * k - Yrot * targetZoom);
    setZoom(targetZoom);
    setAutoOn(false);
  };
  const enableAuto = () => {
    // Re-sync phase so resumed oscillation starts at the current yaw position
    if (oscillate) {
      const off = (yaw - y0) / oscillate.range;
      const clamped = Math.max(-1, Math.min(1, off));
      const omega = (2 * Math.PI) / (oscillate.period * 1000);
      phaseRef.current = Math.asin(clamped) / omega;
    }
    setAutoOn(true);
  };
  return {
    yaw, pitch, zoom, panX, panY,
    setYaw, setPitch, setZoom, reset, focusOn,
    autoOn, setAutoOn, enableAuto,
    bind: { onPointerDown, onPointerMove, onPointerUp: endDrag, onPointerCancel: endDrag, onWheel, onContextMenu },
  };
}
