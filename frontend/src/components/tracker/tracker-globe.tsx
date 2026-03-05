"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import * as THREE from "three";
import type { Submarket } from "@/lib/submarkets";

// ---------- TYPES ----------
export interface Marker2D {
  id: string;
  name: string;
  score: number;
  x: number;
  y: number;
  trend: "up" | "stable" | "down";
  sector: string;
  vacancy: number;
}

// ---------- HELPERS ----------
function latLngToVector3(lat: number, lng: number, radius: number): THREE.Vector3 {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lng + 180) * (Math.PI / 180);
  return new THREE.Vector3(
    -(radius * Math.sin(phi) * Math.cos(theta)),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta)
  );
}

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

function getScoreColor(score: number): string {
  if (score >= 85) return "#00ff88";
  if (score >= 70) return "#00ccff";
  if (score >= 55) return "#ffaa00";
  return "#ff4466";
}

// ---------- PROPS ----------
interface TrackerGlobeProps {
  submarkets: Submarket[];
  zoomed: boolean;
  selectedSubmarket: string | null;
  onZoomIn: () => void;
  onHoverSubmarket: (id: string | null) => void;
  onSelectSubmarket: (id: string | null) => void;
  markers2D: Marker2D[];
  onMarkers2DChange: (markers: Marker2D[]) => void;
}

// ---------- COMPONENT ----------
export default function TrackerGlobe({
  submarkets,
  zoomed,
  selectedSubmarket,
  onZoomIn,
  onHoverSubmarket,
  onSelectSubmarket,
  markers2D,
  onMarkers2DChange,
}: TrackerGlobeProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<Record<string, unknown>>({});
  const phaseRef = useRef<"globe" | "zooming" | "midwest">("globe");
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const animRef = useRef({ progress: 0, active: false });
  const lastProjectionRef = useRef(0);

  // Drag-to-rotate state
  const rotRef = useRef({ y: 0, x: 0 });
  const dragRef = useRef({
    active: false, potential: false,
    startX: 0, startY: 0, startRotY: 0, startRotX: 0,
  });
  const zoomStartRotRef = useRef({ y: 0, x: 0 });

  // Selection & pan state
  const selectedRef = useRef<string | null>(null);
  const panTargetRef = useRef<THREE.Vector3 | null>(null);
  const currentLookAtRef = useRef<THREE.Vector3 | null>(null);
  const touchTimeoutRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const GLOBE_POS = useRef(new THREE.Vector3(0, 0, 3.2)).current;
  const MIDWEST_CENTER = useRef(latLngToVector3(41.0, -87.5, 1.0)).current;
  const MIDWEST_POS = useRef(
    latLngToVector3(41.0, -87.5, 1.0).normalize().multiplyScalar(1.65)
  ).current;

  // Lazy-init vector refs
  if (!panTargetRef.current) panTargetRef.current = MIDWEST_CENTER.clone();
  if (!currentLookAtRef.current) currentLookAtRef.current = new THREE.Vector3(0, 0, 0);

  // Sync selectedSubmarket prop → ref + pan target
  useEffect(() => {
    selectedRef.current = selectedSubmarket;
    if (phaseRef.current !== "midwest") return;
    if (!selectedSubmarket) {
      panTargetRef.current!.copy(MIDWEST_CENTER);
      return;
    }
    // On mobile, pan camera toward selected submarket
    if (typeof window !== "undefined" && window.innerWidth >= 768) return;
    const sub = submarkets.find((s) => s.id === selectedSubmarket);
    if (!sub) return;
    const targetPos = latLngToVector3(sub.lat, sub.lng, 1.0);
    panTargetRef.current!.copy(MIDWEST_CENTER).lerp(targetPos, 0.4);
  }, [selectedSubmarket, submarkets, MIDWEST_CENTER]);

  const initScene = useCallback(() => {
    const container = mountRef.current;
    if (!container) return;
    const w = container.clientWidth;
    const h = container.clientHeight;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 1);
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x000510, 0.15);

    const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 100);
    camera.position.copy(GLOBE_POS);
    camera.lookAt(0, 0, 0);

    // Lights
    scene.add(new THREE.AmbientLight(0x334466, 0.6));
    const sun = new THREE.DirectionalLight(0xffffff, 1.2);
    sun.position.set(5, 3, 5);
    scene.add(sun);
    const rim = new THREE.PointLight(0x0066ff, 1.5, 10);
    rim.position.set(-3, 2, -3);
    scene.add(rim);

    // Globe
    const globeGeo = new THREE.SphereGeometry(1, 96, 96);
    const globeMat = new THREE.MeshPhongMaterial({
      color: 0x0a1628, emissive: 0x020810, specular: 0x1a3a5c,
      shininess: 30, transparent: true, opacity: 0.95,
    });
    const globe = new THREE.Mesh(globeGeo, globeMat);
    scene.add(globe);

    // Atmosphere
    const atmosGeo = new THREE.SphereGeometry(1.02, 64, 64);
    const atmosMat = new THREE.MeshBasicMaterial({
      color: 0x0044aa, transparent: true, opacity: 0.08, side: THREE.BackSide,
    });
    scene.add(new THREE.Mesh(atmosGeo, atmosMat));

    // Grid lines
    const gridGroup = new THREE.Group();
    const gridMat = new THREE.LineBasicMaterial({ color: 0x112244, transparent: true, opacity: 0.3 });
    for (let lat = -80; lat <= 80; lat += 20) {
      const pts: THREE.Vector3[] = [];
      for (let lng = 0; lng <= 360; lng += 2) pts.push(latLngToVector3(lat, lng - 180, 1.005));
      gridGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), gridMat));
    }
    for (let lng = -180; lng < 180; lng += 30) {
      const pts: THREE.Vector3[] = [];
      for (let lat = -90; lat <= 90; lat += 2) pts.push(latLngToVector3(lat, lng, 1.005));
      gridGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), gridMat));
    }
    scene.add(gridGroup);

    // Continent outlines
    const continentGroup = new THREE.Group();
    const continentMat = new THREE.LineBasicMaterial({ color: 0x1a4a7a, transparent: true, opacity: 0.5 });
    const naCoords: [number, number][] = [
      [49,-125],[50,-120],[53,-122],[58,-136],[60,-141],[64,-142],[67,-164],
      [71,-157],[70,-142],[68,-136],[62,-132],[55,-130],[54,-128],[50,-125],
      [48,-123],[46,-124],[43,-124],[40,-124],[35,-121],[33,-118],[32,-117],
      [30,-114],[31,-110],[31,-105],[29,-103],[28,-97],[26,-97],[25,-97],
      [26,-82],[25,-80],[27,-80],[30,-81],[30,-85],[29,-89],[30,-89],
      [30,-88],[35,-75],[38,-75],[39,-74],[41,-72],[42,-70],[43,-70],
      [44,-67],[45,-67],[47,-68],[47,-65],[45,-61],[46,-60],[47,-59],
      [49,-64],[49,-67],[48,-69],[47,-70],[48,-79],[44,-79],[43,-82],
      [46,-84],[48,-88],[48,-89],[49,-95],[49,-104],[49,-115],[49,-125],
    ];
    continentGroup.add(new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(naCoords.map(([la, ln]) => latLngToVector3(la, ln, 1.006))),
      continentMat
    ));
    const lakeMat = new THREE.LineBasicMaterial({ color: 0x0a2a4a, transparent: true, opacity: 0.4 });
    const lmCoords: [number, number][] = [[46,-86.5],[45,-87],[44,-87.5],[43,-87.5],[42,-87],[41.5,-87],[42,-86.5],[43,-86],[44,-85.5],[45,-85.5],[46,-85.5],[46,-86.5]];
    continentGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(lmCoords.map(([la, ln]) => latLngToVector3(la, ln, 1.006))), lakeMat));
    const leCoords: [number, number][] = [[42.5,-83.5],[42,-81],[42,-79.5],[42.5,-79],[42.8,-80],[42.5,-81.5],[42.5,-83.5]];
    continentGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(leCoords.map(([la, ln]) => latLngToVector3(la, ln, 1.006))), lakeMat));
    scene.add(continentGroup);

    // Midwest highlight outline
    const mwCoords: [number, number][] = [[49,-97],[49,-80],[45,-80],[43,-82],[41,-80],[37,-80],[37,-85],[36,-90],[36,-95],[37,-97],[41,-97],[45,-97],[49,-97]];
    const mwMat = new THREE.LineBasicMaterial({ color: 0x00aaff, transparent: true, opacity: 0.5 });
    const midwestOutline = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(mwCoords.map(([la, ln]) => latLngToVector3(la, ln, 1.008))),
      mwMat
    );
    scene.add(midwestOutline);

    // Submarket markers — tag all meshes with submarketId
    const markerGroup = new THREE.Group();
    const markerMeshes: THREE.Mesh[] = [];
    submarkets.forEach((sub) => {
      const pos = latLngToVector3(sub.lat, sub.lng, 1.012);
      const col = new THREE.Color(getScoreColor(sub.score));

      const ringGeo = new THREE.RingGeometry(0.008, 0.012, 32);
      const ringMat = new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.9, side: THREE.DoubleSide, depthTest: false });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.position.copy(pos); ring.lookAt(pos.clone().multiplyScalar(2));
      ring.userData = { submarket: sub, submarketId: sub.id, baseOpacity: 0.9 };
      markerGroup.add(ring); markerMeshes.push(ring);

      const dotGeo = new THREE.CircleGeometry(0.006, 32);
      const dotMat = new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.7, side: THREE.DoubleSide, depthTest: false });
      const dot = new THREE.Mesh(dotGeo, dotMat);
      dot.position.copy(pos); dot.lookAt(pos.clone().multiplyScalar(2));
      dot.userData = { submarketId: sub.id, baseOpacity: 0.7 };
      markerGroup.add(dot);

      const pulseGeo = new THREE.RingGeometry(0.01, 0.013, 32);
      const pulseMat = new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.0, side: THREE.DoubleSide, depthTest: false });
      const pulse = new THREE.Mesh(pulseGeo, pulseMat);
      pulse.position.copy(pos); pulse.lookAt(pos.clone().multiplyScalar(2));
      pulse.userData = { isPulse: true, phase: Math.random() * Math.PI * 2, submarketId: sub.id };
      markerGroup.add(pulse);
    });
    scene.add(markerGroup);

    // Stars
    const starsGeo = new THREE.BufferGeometry();
    const starVerts: number[] = [];
    for (let i = 0; i < 3000; i++) {
      starVerts.push((Math.random() - 0.5) * 50, (Math.random() - 0.5) * 50, (Math.random() - 0.5) * 50);
    }
    starsGeo.setAttribute("position", new THREE.Float32BufferAttribute(starVerts, 3));
    const starsMat = new THREE.PointsMaterial({ color: 0x555577, size: 0.05, transparent: true, opacity: 0.6 });
    scene.add(new THREE.Points(starsGeo, starsMat));

    sceneRef.current = {
      renderer, scene, camera, globe,
      markerGroup, markerMeshes,
      midwestOutline, gridGroup, continentGroup,
    };

    const onResize = () => {
      const nw = container.clientWidth;
      const nh = container.clientHeight;
      camera.aspect = nw / nh;
      camera.updateProjectionMatrix();
      renderer.setSize(nw, nh);
    };
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      container.removeChild(renderer.domElement);
      renderer.dispose();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [submarkets]);

  // Handle zoomed prop → trigger zoom animation or reset
  useEffect(() => {
    if (zoomed && phaseRef.current === "globe") {
      phaseRef.current = "zooming";
      zoomStartRotRef.current = { ...rotRef.current };
      animRef.current = { progress: 0, active: true };
    } else if (!zoomed && phaseRef.current !== "globe") {
      const { camera, globe, markerGroup, midwestOutline, gridGroup, continentGroup } =
        sceneRef.current as Record<string, THREE.Object3D>;
      if (camera) {
        (camera as unknown as THREE.PerspectiveCamera).position.copy(GLOBE_POS);
        (camera as unknown as THREE.PerspectiveCamera).lookAt(0, 0, 0);
        [globe, markerGroup, midwestOutline, gridGroup, continentGroup].forEach((obj) => {
          if (obj) { obj.rotation.y = 0; obj.rotation.x = 0; }
        });
        rotRef.current = { y: 0, x: 0 };
        currentLookAtRef.current!.set(0, 0, 0);
        panTargetRef.current!.copy(MIDWEST_CENTER);
        phaseRef.current = "globe";
        onMarkers2DChange([]);
      }
    }
  }, [zoomed, GLOBE_POS, MIDWEST_CENTER, onMarkers2DChange]);

  // Project 3D → 2D
  const updateMarkers2D = useCallback(() => {
    const { camera, renderer, markerMeshes, markerGroup } =
      sceneRef.current as {
        camera: THREE.PerspectiveCamera;
        renderer: THREE.WebGLRenderer;
        markerMeshes: THREE.Mesh[];
        markerGroup: THREE.Group;
      };
    if (!camera || !renderer || !markerMeshes) return;
    const w = renderer.domElement.clientWidth;
    const h = renderer.domElement.clientHeight;
    const projected: Marker2D[] = [];
    markerMeshes.forEach((mesh) => {
      const sub = mesh.userData.submarket as Submarket;
      const pos = mesh.position.clone();
      pos.applyMatrix4(markerGroup.matrixWorld);
      pos.project(camera);
      if (pos.z < 1) {
        projected.push({
          id: sub.id, name: sub.name, score: sub.score,
          x: (pos.x * 0.5 + 0.5) * w,
          y: (-pos.y * 0.5 + 0.5) * h,
          trend: sub.trend, sector: sub.sector, vacancy: sub.vacancy,
        });
      }
    });
    onMarkers2DChange(projected);
  }, [onMarkers2DChange]);

  // Animation loop
  useEffect(() => {
    const cleanup = initScene();
    let frameId: number;
    let time = 0;

    const animate = () => {
      frameId = requestAnimationFrame(animate);
      time += 0.016;
      const { renderer, scene, camera, globe, markerGroup, midwestOutline, gridGroup, continentGroup } =
        sceneRef.current as Record<string, unknown>;
      if (!renderer) return;
      const r = renderer as THREE.WebGLRenderer;
      const s = scene as THREE.Scene;
      const cam = camera as THREE.PerspectiveCamera;
      const rotatables = [globe, markerGroup, midwestOutline, gridGroup, continentGroup];

      // Globe phase: auto-rotate when not dragging
      if (phaseRef.current === "globe") {
        if (!dragRef.current.active) {
          rotRef.current.y += 0.001;
        }
        rotatables.forEach((obj) => {
          if (obj) {
            (obj as THREE.Object3D).rotation.y = rotRef.current.y;
            (obj as THREE.Object3D).rotation.x = rotRef.current.x;
          }
        });
      }

      // Zoom animation — lerp camera AND rotation back to 0
      if (animRef.current.active) {
        animRef.current.progress += 0.006;
        const t = Math.min(animRef.current.progress, 1);
        const et = easeInOutCubic(t);

        cam.position.lerpVectors(GLOBE_POS, MIDWEST_POS, et);
        const lookTarget = new THREE.Vector3(0, 0, 0).lerp(MIDWEST_CENTER, et);
        cam.lookAt(lookTarget);
        currentLookAtRef.current!.copy(lookTarget);

        // Smoothly unwind any rotation so Midwest lands consistently
        const rotY = zoomStartRotRef.current.y * (1 - et);
        const rotX = zoomStartRotRef.current.x * (1 - et);
        rotatables.forEach((obj) => {
          if (obj) {
            (obj as THREE.Object3D).rotation.y = rotY;
            (obj as THREE.Object3D).rotation.x = rotX;
          }
        });

        if (t >= 1) {
          animRef.current.active = false;
          phaseRef.current = "midwest";
          // Ensure rotation is exactly 0
          rotatables.forEach((obj) => {
            if (obj) { (obj as THREE.Object3D).rotation.y = 0; (obj as THREE.Object3D).rotation.x = 0; }
          });
        }
      }

      // Midwest phase: smooth camera panning toward pan target
      if (phaseRef.current === "midwest" && !animRef.current.active) {
        currentLookAtRef.current!.lerp(panTargetRef.current!, 0.05);
        cam.lookAt(currentLookAtRef.current!);
      }

      // Marker dimming + pulse animation
      if (markerGroup) {
        const sel = selectedRef.current;
        (markerGroup as THREE.Group).children.forEach((child) => {
          const mat = (child as THREE.Mesh).material as THREE.MeshBasicMaterial;
          const id = child.userData.submarketId as string | undefined;

          // Push selected submarket to top render layer
          child.renderOrder = sel && id === sel ? 10 : 1;

          if (child.userData.isPulse) {
            const p = (time * 1.5 + child.userData.phase) % (Math.PI * 2);
            const scale = 1 + Math.sin(p) * 0.8;
            child.scale.set(scale, scale, scale);
            if (sel && id !== sel) {
              mat.opacity = 0;
            } else if (sel && id === sel) {
              mat.opacity = Math.max(0, 0.6 * (1 - Math.sin(p) * 0.5));
            } else {
              mat.opacity = Math.max(0, 0.4 * (1 - Math.sin(p) * 0.5));
            }
          } else {
            const baseOpacity = (child.userData.baseOpacity as number) ?? 0.9;
            if (sel) {
              mat.opacity = id === sel ? Math.min(1, baseOpacity * 1.2) : baseOpacity * 0.15;
            } else {
              mat.opacity = baseOpacity;
            }
          }
        });
      }

      r.render(s, cam);

      // Throttled 2D projection (only in midwest phase)
      if (phaseRef.current === "midwest") {
        const now = Date.now();
        if (now - lastProjectionRef.current > 100) {
          lastProjectionRef.current = now;
          updateMarkers2D();
        }
      }
    };

    animate();
    return () => {
      cancelAnimationFrame(frameId);
      if (cleanup) cleanup();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initScene, updateMarkers2D]);

  // ---------- POINTER EVENTS ----------

  const handlePointerDown = (e: React.PointerEvent) => {
    if (phaseRef.current === "globe") {
      dragRef.current = {
        active: false, potential: true,
        startX: e.clientX, startY: e.clientY,
        startRotY: rotRef.current.y, startRotX: rotRef.current.x,
      };
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    } else if (phaseRef.current === "midwest" && e.pointerType === "touch") {
      // Touch marker detection in midwest
      const rect = mountRef.current?.getBoundingClientRect();
      if (!rect) return;
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      let closest: Marker2D | undefined;
      let minDist = 40;
      for (const m of markers2D) {
        const dist = Math.sqrt((m.x - x) ** 2 + (m.y - y) ** 2);
        if (dist < minDist) { minDist = dist; closest = m; }
      }
      const newId = closest?.id ?? null;
      if (newId !== hoveredId) {
        setHoveredId(newId);
        onHoverSubmarket(newId);
      }
      if (touchTimeoutRef.current) clearTimeout(touchTimeoutRef.current);
    }
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (phaseRef.current === "globe" && dragRef.current.potential) {
      const dx = e.clientX - dragRef.current.startX;
      const dy = e.clientY - dragRef.current.startY;
      if (!dragRef.current.active && (Math.abs(dx) > 3 || Math.abs(dy) > 3)) {
        dragRef.current.active = true;
      }
      if (dragRef.current.active) {
        rotRef.current.y = dragRef.current.startRotY + dx * 0.005;
        rotRef.current.x = Math.max(-0.5, Math.min(0.5, dragRef.current.startRotX + dy * 0.005));
      }
    } else if (phaseRef.current === "midwest" && e.pointerType === "mouse") {
      // Mouse hover detection in midwest
      const rect = mountRef.current?.getBoundingClientRect();
      if (!rect) return;
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      let closest: Marker2D | undefined;
      let minDist = 40;
      for (const m of markers2D) {
        const dist = Math.sqrt((m.x - x) ** 2 + (m.y - y) ** 2);
        if (dist < minDist) { minDist = dist; closest = m; }
      }
      const newId = closest?.id ?? null;
      if (newId !== hoveredId) {
        setHoveredId(newId);
        onHoverSubmarket(newId);
      }
    }
  };

  const handlePointerUp = (e: React.PointerEvent) => {
    if (phaseRef.current === "globe" && dragRef.current.potential) {
      const wasDrag = dragRef.current.active;
      dragRef.current = { active: false, potential: false, startX: 0, startY: 0, startRotY: 0, startRotX: 0 };
      if (!wasDrag) {
        onZoomIn();
      }
    }
    if (phaseRef.current === "midwest") {
      if (e.pointerType === "mouse") {
        // Click to select/deselect on desktop
        const rect = mountRef.current?.getBoundingClientRect();
        if (rect) {
          const x = e.clientX - rect.left;
          const y = e.clientY - rect.top;
          let closest: Marker2D | undefined;
          let minDist = 40;
          for (const m of markers2D) {
            const dist = Math.sqrt((m.x - x) ** 2 + (m.y - y) ** 2);
            if (dist < minDist) { minDist = dist; closest = m; }
          }
          if (closest) {
            onSelectSubmarket(selectedRef.current === closest.id ? null : closest.id);
          } else {
            onSelectSubmarket(null);
          }
        }
      } else if (e.pointerType === "touch") {
        // Tap to select/deselect on mobile — use the hovered marker from pointerDown
        if (hoveredId) {
          onSelectSubmarket(selectedRef.current === hoveredId ? null : hoveredId);
        } else {
          onSelectSubmarket(null);
        }
        touchTimeoutRef.current = setTimeout(() => {
          setHoveredId(null);
          onHoverSubmarket(null);
        }, 2000);
      }
    }
  };

  return (
    <div
      ref={mountRef}
      className="w-full h-full touch-none"
      style={{ cursor: zoomed ? (hoveredId ? "pointer" : "default") : "grab" }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
    />
  );
}
