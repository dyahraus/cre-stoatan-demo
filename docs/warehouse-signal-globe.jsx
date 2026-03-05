import { useEffect, useRef, useState, useCallback } from "react";
import * as THREE from "three";

// ---------- DATA ----------
const MIDWEST_SUBMARKETS = [
  { id: "chi_cbd", name: "Chicago CBD", lat: 41.8781, lng: -87.6298, score: 87, trend: "up", sector: "Industrial", vacancy: 4.2 },
  { id: "chi_ohare", name: "O'Hare Corridor", lat: 41.9742, lng: -87.9073, score: 92, trend: "up", sector: "Logistics", vacancy: 3.1 },
  { id: "chi_south", name: "South Suburbs", lat: 41.5250, lng: -87.6900, score: 71, trend: "stable", sector: "Distribution", vacancy: 5.8 },
  { id: "chi_i80", name: "I-80 Corridor", lat: 41.5060, lng: -88.1500, score: 95, trend: "up", sector: "Warehouse", vacancy: 2.4 },
  { id: "indy_west", name: "Indianapolis West", lat: 39.7684, lng: -86.3580, score: 78, trend: "up", sector: "Distribution", vacancy: 4.9 },
  { id: "indy_east", name: "Indianapolis East", lat: 39.7800, lng: -85.9500, score: 65, trend: "stable", sector: "Industrial", vacancy: 6.2 },
  { id: "columbus", name: "Columbus Central", lat: 39.9612, lng: -82.9988, score: 83, trend: "up", sector: "E-Commerce", vacancy: 3.7 },
  { id: "detroit_metro", name: "Detroit Metro", lat: 42.3314, lng: -83.0458, score: 59, trend: "down", sector: "Automotive", vacancy: 7.8 },
  { id: "milwaukee", name: "Milwaukee Industrial", lat: 43.0389, lng: -87.9065, score: 74, trend: "stable", sector: "Manufacturing", vacancy: 5.1 },
  { id: "stl_east", name: "St. Louis East", lat: 38.6270, lng: -90.1994, score: 68, trend: "stable", sector: "Distribution", vacancy: 6.0 },
  { id: "minneapolis", name: "Minneapolis Corridor", lat: 44.9778, lng: -93.2650, score: 81, trend: "up", sector: "Logistics", vacancy: 4.0 },
  { id: "kc_industrial", name: "Kansas City Industrial", lat: 39.0997, lng: -94.5786, score: 76, trend: "up", sector: "Intermodal", vacancy: 4.5 },
  { id: "cin_north", name: "Cincinnati North", lat: 39.1620, lng: -84.4569, score: 72, trend: "stable", sector: "Industrial", vacancy: 5.4 },
  { id: "grandrapids", name: "Grand Rapids", lat: 42.9634, lng: -85.6681, score: 63, trend: "down", sector: "Manufacturing", vacancy: 6.8 },
];

const CAMERA_PHASES = {
  GLOBE: "globe",
  ZOOMING: "zooming",
  MIDWEST: "midwest",
};

// ---------- HELPERS ----------
function latLngToVector3(lat, lng, radius) {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lng + 180) * (Math.PI / 180);
  return new THREE.Vector3(
    -(radius * Math.sin(phi) * Math.cos(theta)),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta)
  );
}

function easeInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

function getScoreColor(score) {
  if (score >= 85) return "#00ff88";
  if (score >= 70) return "#00ccff";
  if (score >= 55) return "#ffaa00";
  return "#ff4466";
}

function getTrendArrow(trend) {
  if (trend === "up") return "▲";
  if (trend === "down") return "▼";
  return "●";
}

function getTrendColor(trend) {
  if (trend === "up") return "#00ff88";
  if (trend === "down") return "#ff4466";
  return "#888";
}

// ---------- GLOBE COMPONENT ----------
export default function WarehouseSignalGlobe() {
  const mountRef = useRef(null);
  const sceneRef = useRef({});
  const [phase, setPhase] = useState(CAMERA_PHASES.GLOBE);
  const [hoveredMarker, setHoveredMarker] = useState(null);
  const [selectedMarker, setSelectedMarker] = useState(null);
  const [showPanel, setShowPanel] = useState(false);
  const [markers2D, setMarkers2D] = useState([]);
  const animRef = useRef({ progress: 0, active: false });
  const mouseRef = useRef(new THREE.Vector2());
  const raycasterRef = useRef(new THREE.Raycaster());

  // Camera targets
  const GLOBE_POS = new THREE.Vector3(0, 0, 3.2);
  const MIDWEST_CENTER = latLngToVector3(41.0, -87.5, 1.0);
  const MIDWEST_POS = MIDWEST_CENTER.clone().normalize().multiplyScalar(1.65);

  const initScene = useCallback(() => {
    const container = mountRef.current;
    if (!container) return;
    const w = container.clientWidth;
    const h = container.clientHeight;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 1);
    container.appendChild(renderer.domElement);

    // Scene
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x000510, 0.15);

    // Camera
    const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 100);
    camera.position.copy(GLOBE_POS);
    camera.lookAt(0, 0, 0);

    // Lights
    const ambient = new THREE.AmbientLight(0x334466, 0.6);
    scene.add(ambient);
    const sun = new THREE.DirectionalLight(0xffffff, 1.2);
    sun.position.set(5, 3, 5);
    scene.add(sun);
    const rim = new THREE.PointLight(0x0066ff, 1.5, 10);
    rim.position.set(-3, 2, -3);
    scene.add(rim);

    // Globe
    const globeGeo = new THREE.SphereGeometry(1, 96, 96);
    const globeMat = new THREE.MeshPhongMaterial({
      color: 0x0a1628,
      emissive: 0x020810,
      specular: 0x1a3a5c,
      shininess: 30,
      transparent: true,
      opacity: 0.95,
    });
    const globe = new THREE.Mesh(globeGeo, globeMat);
    scene.add(globe);

    // Atmosphere glow
    const atmosGeo = new THREE.SphereGeometry(1.02, 64, 64);
    const atmosMat = new THREE.MeshBasicMaterial({
      color: 0x0044aa,
      transparent: true,
      opacity: 0.08,
      side: THREE.BackSide,
    });
    scene.add(new THREE.Mesh(atmosGeo, atmosMat));

    // Grid lines (latitude/longitude)
    const gridGroup = new THREE.Group();
    const gridMat = new THREE.LineBasicMaterial({ color: 0x112244, transparent: true, opacity: 0.3 });
    for (let lat = -80; lat <= 80; lat += 20) {
      const pts = [];
      for (let lng = 0; lng <= 360; lng += 2) {
        pts.push(latLngToVector3(lat, lng - 180, 1.005));
      }
      const geo = new THREE.BufferGeometry().setFromPoints(pts);
      gridGroup.add(new THREE.Line(geo, gridMat));
    }
    for (let lng = -180; lng < 180; lng += 30) {
      const pts = [];
      for (let lat = -90; lat <= 90; lat += 2) {
        pts.push(latLngToVector3(lat, lng, 1.005));
      }
      const geo = new THREE.BufferGeometry().setFromPoints(pts);
      gridGroup.add(new THREE.Line(geo, gridMat));
    }
    scene.add(gridGroup);

    // Rough continent outlines — simplified North America & parts of S. America/Europe
    const continentGroup = new THREE.Group();
    const continentMat = new THREE.LineBasicMaterial({ color: 0x1a4a7a, transparent: true, opacity: 0.5 });
    
    // North America outline (simplified)
    const naPoints = [
      [49, -125], [50, -120], [53, -122], [58, -136], [60, -141], [64, -142], [67, -164],
      [71, -157], [70, -142], [68, -136], [62, -132], [55, -130], [54, -128], [50, -125],
      [48, -123], [46, -124], [43, -124], [40, -124], [35, -121], [33, -118], [32, -117],
      [30, -114], [31, -110], [31, -105], [29, -103], [28, -97], [26, -97], [25, -97],
      [26, -82], [25, -80], [27, -80], [30, -81], [30, -85], [29, -89], [30, -89],
      [30, -88], [35, -75], [38, -75], [39, -74], [41, -72], [42, -70], [43, -70],
      [44, -67], [45, -67], [47, -68], [47, -65], [45, -61], [46, -60], [47, -59],
      [49, -64], [49, -67], [48, -69], [47, -70], [48, -79], [44, -79], [43, -82],
      [46, -84], [48, -88], [48, -89], [49, -95], [49, -104], [49, -115], [49, -125],
    ].map(([lat, lng]) => latLngToVector3(lat, lng, 1.006));
    const naGeo = new THREE.BufferGeometry().setFromPoints(naPoints);
    continentGroup.add(new THREE.Line(naGeo, continentMat));

    // Great Lakes (simplified)
    const lakeMat = new THREE.LineBasicMaterial({ color: 0x0a2a4a, transparent: true, opacity: 0.4 });
    const lakeMichigan = [
      [46, -86.5], [45, -87], [44, -87.5], [43, -87.5], [42, -87], [41.5, -87],
      [42, -86.5], [43, -86], [44, -85.5], [45, -85.5], [46, -85.5], [46, -86.5],
    ].map(([lat, lng]) => latLngToVector3(lat, lng, 1.006));
    continentGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(lakeMichigan), lakeMat));

    const lakeErie = [
      [42.5, -83.5], [42, -81], [42, -79.5], [42.5, -79], [42.8, -80], [42.5, -81.5], [42.5, -83.5],
    ].map(([lat, lng]) => latLngToVector3(lat, lng, 1.006));
    continentGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(lakeErie), lakeMat));

    scene.add(continentGroup);

    // Midwest highlight region (subtle glow)
    const midwestBounds = [
      [49, -97], [49, -80], [45, -80], [43, -82], [41, -80], [37, -80],
      [37, -85], [36, -90], [36, -95], [37, -97], [41, -97], [45, -97], [49, -97],
    ].map(([lat, lng]) => latLngToVector3(lat, lng, 1.008));
    const mwGeo = new THREE.BufferGeometry().setFromPoints(midwestBounds);
    const mwMat = new THREE.LineBasicMaterial({ color: 0x00aaff, transparent: true, opacity: 0.5 });
    const midwestOutline = new THREE.Line(mwGeo, mwMat);
    scene.add(midwestOutline);

    // Data markers
    const markerGroup = new THREE.Group();
    const markerMeshes = [];
    MIDWEST_SUBMARKETS.forEach((sub) => {
      const pos = latLngToVector3(sub.lat, sub.lng, 1.012);
      
      // Outer ring
      const ringGeo = new THREE.RingGeometry(0.008, 0.012, 32);
      const ringMat = new THREE.MeshBasicMaterial({
        color: new THREE.Color(getScoreColor(sub.score)),
        transparent: true,
        opacity: 0.9,
        side: THREE.DoubleSide,
      });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.position.copy(pos);
      ring.lookAt(pos.clone().multiplyScalar(2));
      ring.userData = { submarket: sub };
      markerGroup.add(ring);
      markerMeshes.push(ring);

      // Inner dot
      const dotGeo = new THREE.CircleGeometry(0.006, 32);
      const dotMat = new THREE.MeshBasicMaterial({
        color: new THREE.Color(getScoreColor(sub.score)),
        transparent: true,
        opacity: 0.7,
        side: THREE.DoubleSide,
      });
      const dot = new THREE.Mesh(dotGeo, dotMat);
      dot.position.copy(pos);
      dot.lookAt(pos.clone().multiplyScalar(2));
      markerGroup.add(dot);

      // Pulse ring (animated)
      const pulseGeo = new THREE.RingGeometry(0.01, 0.013, 32);
      const pulseMat = new THREE.MeshBasicMaterial({
        color: new THREE.Color(getScoreColor(sub.score)),
        transparent: true,
        opacity: 0.0,
        side: THREE.DoubleSide,
      });
      const pulse = new THREE.Mesh(pulseGeo, pulseMat);
      pulse.position.copy(pos);
      pulse.lookAt(pos.clone().multiplyScalar(2));
      pulse.userData = { isPulse: true, phase: Math.random() * Math.PI * 2 };
      markerGroup.add(pulse);
    });
    scene.add(markerGroup);

    // Stars background
    const starsGeo = new THREE.BufferGeometry();
    const starVerts = [];
    for (let i = 0; i < 3000; i++) {
      starVerts.push(
        (Math.random() - 0.5) * 50,
        (Math.random() - 0.5) * 50,
        (Math.random() - 0.5) * 50
      );
    }
    starsGeo.setAttribute("position", new THREE.Float32BufferAttribute(starVerts, 3));
    const starsMat = new THREE.PointsMaterial({ color: 0x555577, size: 0.05, transparent: true, opacity: 0.6 });
    scene.add(new THREE.Points(starsGeo, starsMat));

    sceneRef.current = { renderer, scene, camera, globe, markerGroup, markerMeshes, gridGroup, continentGroup, midwestOutline };

    // Resize handler
    const onResize = () => {
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      container.removeChild(renderer.domElement);
      renderer.dispose();
    };
  }, []);

  // Project 3D markers to 2D screen coords
  const updateMarkers2D = useCallback(() => {
    const { camera, renderer, markerMeshes } = sceneRef.current;
    if (!camera || !renderer || !markerMeshes) return;
    const w = renderer.domElement.clientWidth;
    const h = renderer.domElement.clientHeight;
    const newMarkers = [];
    markerMeshes.forEach((mesh) => {
      const sub = mesh.userData.submarket;
      const pos = mesh.position.clone();
      pos.project(camera);
      const x = (pos.x * 0.5 + 0.5) * w;
      const y = (-pos.y * 0.5 + 0.5) * h;
      // Only show if in front of camera
      if (pos.z < 1) {
        newMarkers.push({ ...sub, x, y });
      }
    });
    setMarkers2D(newMarkers);
  }, []);

  // Animation loop
  useEffect(() => {
    const cleanup = initScene();
    let frameId;
    let time = 0;
    let slowRotation = 0;

    const animate = () => {
      frameId = requestAnimationFrame(animate);
      time += 0.016;
      const { renderer, scene, camera, globe, markerGroup, midwestOutline } = sceneRef.current;
      if (!renderer) return;

      // Slow globe rotation in globe phase
      if (phase === CAMERA_PHASES.GLOBE) {
        slowRotation += 0.001;
        globe.rotation.y = slowRotation;
        markerGroup.rotation.y = slowRotation;
        if (midwestOutline) midwestOutline.rotation.y = slowRotation;
        sceneRef.current.gridGroup.rotation.y = slowRotation;
        sceneRef.current.continentGroup.rotation.y = slowRotation;
      }

      // Zoom animation
      if (animRef.current.active) {
        animRef.current.progress += 0.006;
        const t = Math.min(animRef.current.progress, 1);
        const et = easeInOutCubic(t);

        camera.position.lerpVectors(GLOBE_POS, MIDWEST_POS, et);

        const lookTarget = new THREE.Vector3(0, 0, 0).lerp(MIDWEST_CENTER, et);
        camera.lookAt(lookTarget);

        if (t >= 1) {
          animRef.current.active = false;
          setPhase(CAMERA_PHASES.MIDWEST);
          setShowPanel(true);
        }
      }

      // Pulse animation on markers
      markerGroup.children.forEach((child) => {
        if (child.userData.isPulse) {
          const p = (time * 1.5 + child.userData.phase) % (Math.PI * 2);
          const scale = 1 + Math.sin(p) * 0.8;
          child.scale.set(scale, scale, scale);
          child.material.opacity = Math.max(0, 0.4 * (1 - Math.sin(p) * 0.5));
        }
      });

      renderer.render(scene, camera);

      if (phase === CAMERA_PHASES.MIDWEST) {
        updateMarkers2D();
      }
    };

    animate();
    return () => {
      cancelAnimationFrame(frameId);
      if (cleanup) cleanup();
    };
  }, [phase, initScene, updateMarkers2D]);

  // Mouse handling for marker hover
  const handleMouseMove = (e) => {
    if (phase !== CAMERA_PHASES.MIDWEST) return;
    const rect = mountRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    let closest = null;
    let minDist = 30;
    markers2D.forEach((m) => {
      const dist = Math.sqrt((m.x - x) ** 2 + (m.y - y) ** 2);
      if (dist < minDist) {
        minDist = dist;
        closest = m;
      }
    });
    setHoveredMarker(closest);
  };

  const handleClick = (e) => {
    if (phase === CAMERA_PHASES.GLOBE) {
      setPhase(CAMERA_PHASES.ZOOMING);
      animRef.current = { progress: 0, active: true };
      return;
    }
    if (hoveredMarker) {
      setSelectedMarker(selectedMarker?.id === hoveredMarker.id ? null : hoveredMarker);
    } else {
      setSelectedMarker(null);
    }
  };

  const handleReset = () => {
    setPhase(CAMERA_PHASES.GLOBE);
    setShowPanel(false);
    setSelectedMarker(null);
    setHoveredMarker(null);
    const { camera, globe, markerGroup, midwestOutline, gridGroup, continentGroup } = sceneRef.current;
    camera.position.copy(GLOBE_POS);
    camera.lookAt(0, 0, 0);
    globe.rotation.y = 0;
    markerGroup.rotation.y = 0;
    if (midwestOutline) midwestOutline.rotation.y = 0;
    gridGroup.rotation.y = 0;
    continentGroup.rotation.y = 0;
  };

  const avgScore = Math.round(MIDWEST_SUBMARKETS.reduce((a, b) => a + b.score, 0) / MIDWEST_SUBMARKETS.length);

  return (
    <div style={{ width: "100%", height: "100vh", background: "#000510", position: "relative", overflow: "hidden", fontFamily: "'DM Sans', 'Helvetica Neue', sans-serif" }}>
      <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet" />

      {/* Three.js mount */}
      <div
        ref={mountRef}
        style={{ width: "100%", height: "100%", cursor: phase === CAMERA_PHASES.GLOBE ? "pointer" : hoveredMarker ? "pointer" : "default" }}
        onMouseMove={handleMouseMove}
        onClick={handleClick}
      />

      {/* Top header */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, padding: "24px 32px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        background: "linear-gradient(180deg, rgba(0,5,16,0.9) 0%, transparent 100%)",
        pointerEvents: "none",
      }}>
        <div>
          <div style={{
            fontFamily: "'Space Mono', monospace", fontSize: 11, letterSpacing: 4,
            color: "#00aaff", textTransform: "uppercase", marginBottom: 4,
          }}>
            Warehouse Signal
          </div>
          <div style={{ fontSize: 22, fontWeight: 700, color: "#e0e8f0", letterSpacing: -0.5 }}>
            Industrial Expansion Radar
          </div>
        </div>
        {phase !== CAMERA_PHASES.GLOBE && (
          <button onClick={handleReset} style={{
            pointerEvents: "all", padding: "8px 20px", border: "1px solid rgba(0,170,255,0.3)",
            background: "rgba(0,20,40,0.7)", color: "#00aaff", borderRadius: 4,
            fontFamily: "'Space Mono', monospace", fontSize: 11, letterSpacing: 2,
            cursor: "pointer", textTransform: "uppercase", backdropFilter: "blur(8px)",
            transition: "all 0.2s",
          }}>
            ← Globe
          </button>
        )}
      </div>

      {/* Globe phase prompt */}
      {phase === CAMERA_PHASES.GLOBE && (
        <div style={{
          position: "absolute", bottom: 80, left: "50%", transform: "translateX(-50%)",
          textAlign: "center", animation: "fadeInUp 1s ease-out",
        }}>
          <div style={{
            fontFamily: "'Space Mono', monospace", fontSize: 12, letterSpacing: 3,
            color: "rgba(0,170,255,0.6)", textTransform: "uppercase", marginBottom: 8,
          }}>
            Click to explore
          </div>
          <div style={{ fontSize: 16, color: "rgba(224,232,240,0.5)", fontWeight: 300 }}>
            Midwest Industrial Markets
          </div>
          <div style={{
            width: 1, height: 24, background: "linear-gradient(180deg, rgba(0,170,255,0.4), transparent)",
            margin: "12px auto 0",
          }} />
        </div>
      )}

      {/* Zooming phase overlay */}
      {phase === CAMERA_PHASES.ZOOMING && (
        <div style={{
          position: "absolute", bottom: 80, left: "50%", transform: "translateX(-50%)",
          textAlign: "center",
        }}>
          <div style={{
            fontFamily: "'Space Mono', monospace", fontSize: 11, letterSpacing: 4,
            color: "rgba(0,170,255,0.8)", textTransform: "uppercase",
            animation: "pulse 1.5s ease-in-out infinite",
          }}>
            Approaching Midwest Region...
          </div>
        </div>
      )}

      {/* Marker labels (only in Midwest phase) */}
      {phase === CAMERA_PHASES.MIDWEST && markers2D.map((m) => (
        <div key={m.id} style={{
          position: "absolute",
          left: m.x,
          top: m.y,
          transform: "translate(-50%, -50%)",
          pointerEvents: "none",
          transition: "opacity 0.3s",
          opacity: showPanel ? 1 : 0,
        }}>
          {/* Label on hover */}
          {(hoveredMarker?.id === m.id || selectedMarker?.id === m.id) && (
            <div style={{
              position: "absolute", bottom: 20, left: "50%", transform: "translateX(-50%)",
              whiteSpace: "nowrap", padding: "6px 12px",
              background: "rgba(0,10,25,0.9)", border: `1px solid ${getScoreColor(m.score)}40`,
              borderRadius: 4, backdropFilter: "blur(12px)",
            }}>
              <div style={{
                fontFamily: "'Space Mono', monospace", fontSize: 10, letterSpacing: 1,
                color: getScoreColor(m.score), marginBottom: 2,
              }}>
                {m.name}
              </div>
              <div style={{ fontSize: 11, color: "#8899aa" }}>
                Score: <span style={{ color: getScoreColor(m.score), fontWeight: 700 }}>{m.score}</span>
                {" "}<span style={{ color: getTrendColor(m.trend), fontSize: 10 }}>{getTrendArrow(m.trend)}</span>
                {" · "}Vacancy: {m.vacancy}%
              </div>
            </div>
          )}
        </div>
      ))}

      {/* Side panel */}
      {showPanel && (
        <div style={{
          position: "absolute", right: 0, top: 0, bottom: 0, width: 320,
          background: "linear-gradient(270deg, rgba(0,5,16,0.95) 0%, rgba(0,5,16,0.7) 100%)",
          backdropFilter: "blur(20px)", borderLeft: "1px solid rgba(0,170,255,0.1)",
          padding: "80px 20px 20px", overflowY: "auto",
          animation: "slideInRight 0.6s ease-out",
        }}>
          {/* Aggregate stats */}
          <div style={{
            fontFamily: "'Space Mono', monospace", fontSize: 10, letterSpacing: 3,
            color: "#00aaff", textTransform: "uppercase", marginBottom: 16,
          }}>
            Region Overview
          </div>
          <div style={{ display: "flex", gap: 12, marginBottom: 24 }}>
            <div style={{
              flex: 1, padding: 12, background: "rgba(0,170,255,0.05)",
              border: "1px solid rgba(0,170,255,0.15)", borderRadius: 6,
            }}>
              <div style={{ fontSize: 28, fontWeight: 700, color: getScoreColor(avgScore) }}>{avgScore}</div>
              <div style={{ fontSize: 10, color: "#667788", fontFamily: "'Space Mono', monospace", letterSpacing: 1 }}>AVG SCORE</div>
            </div>
            <div style={{
              flex: 1, padding: 12, background: "rgba(0,170,255,0.05)",
              border: "1px solid rgba(0,170,255,0.15)", borderRadius: 6,
            }}>
              <div style={{ fontSize: 28, fontWeight: 700, color: "#e0e8f0" }}>{MIDWEST_SUBMARKETS.length}</div>
              <div style={{ fontSize: 10, color: "#667788", fontFamily: "'Space Mono', monospace", letterSpacing: 1 }}>MARKETS</div>
            </div>
          </div>

          {/* Submarket list */}
          <div style={{
            fontFamily: "'Space Mono', monospace", fontSize: 10, letterSpacing: 3,
            color: "#556677", textTransform: "uppercase", marginBottom: 10,
          }}>
            Submarkets
          </div>
          {MIDWEST_SUBMARKETS
            .sort((a, b) => b.score - a.score)
            .map((sub) => (
              <div
                key={sub.id}
                onClick={() => setSelectedMarker(selectedMarker?.id === sub.id ? null : sub)}
                style={{
                  padding: "10px 12px", marginBottom: 4, borderRadius: 4,
                  background: selectedMarker?.id === sub.id
                    ? "rgba(0,170,255,0.1)"
                    : hoveredMarker?.id === sub.id
                      ? "rgba(0,170,255,0.05)"
                      : "transparent",
                  border: selectedMarker?.id === sub.id
                    ? `1px solid ${getScoreColor(sub.score)}30`
                    : "1px solid transparent",
                  cursor: "pointer", transition: "all 0.2s",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 500, color: "#c0d0e0", marginBottom: 2 }}>
                      {sub.name}
                    </div>
                    <div style={{ fontSize: 10, color: "#556677" }}>
                      {sub.sector} · {sub.vacancy}% vac
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{
                      fontSize: 18, fontWeight: 700, color: getScoreColor(sub.score),
                      fontFamily: "'Space Mono', monospace",
                    }}>
                      {sub.score}
                    </div>
                    <div style={{ fontSize: 10, color: getTrendColor(sub.trend) }}>
                      {getTrendArrow(sub.trend)} {sub.trend}
                    </div>
                  </div>
                </div>

                {/* Expanded detail */}
                {selectedMarker?.id === sub.id && (
                  <div style={{
                    marginTop: 10, paddingTop: 10, borderTop: "1px solid rgba(0,170,255,0.1)",
                  }}>
                    <div style={{
                      fontSize: 10, color: "#556677", fontFamily: "'Space Mono', monospace",
                      letterSpacing: 1, marginBottom: 6, textTransform: "uppercase",
                    }}>
                      Recent Signals
                    </div>
                    <div style={{ fontSize: 11, color: "#8899aa", lineHeight: 1.5 }}>
                      {sub.score >= 80
                        ? `Strong expansion signals detected across ${sub.sector.toLowerCase()} sector. Multiple transcripts reference capacity additions and new DC development in this submarket.`
                        : sub.score >= 60
                          ? `Moderate activity indicators. Network studies and exploratory language suggest potential future expansion. Monitoring recommended.`
                          : `Below-average expansion signals. Limited references to this market in recent earnings calls. Some consolidation language detected.`
                      }
                    </div>
                    {/* Score bar */}
                    <div style={{
                      marginTop: 10, height: 3, background: "rgba(0,170,255,0.1)",
                      borderRadius: 2, overflow: "hidden",
                    }}>
                      <div style={{
                        width: `${sub.score}%`, height: "100%",
                        background: getScoreColor(sub.score),
                        borderRadius: 2,
                        transition: "width 0.5s ease-out",
                      }} />
                    </div>
                  </div>
                )}
              </div>
            ))}
        </div>
      )}

      {/* Bottom status bar */}
      {showPanel && (
        <div style={{
          position: "absolute", bottom: 0, left: 0, right: 320, padding: "12px 32px",
          background: "linear-gradient(0deg, rgba(0,5,16,0.9) 0%, transparent 100%)",
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <div style={{
            fontFamily: "'Space Mono', monospace", fontSize: 10, letterSpacing: 2,
            color: "#334455",
          }}>
            Q4 2024 · {MIDWEST_SUBMARKETS.length} SUBMARKETS · S&P 500 EARNINGS SCAN
          </div>
          <div style={{
            fontFamily: "'Space Mono', monospace", fontSize: 10, letterSpacing: 2,
            color: "#334455",
          }}>
            WAREHOUSE SIGNAL v0.1
          </div>
        </div>
      )}

      <style>{`
        @keyframes fadeInUp {
          from { opacity: 0; transform: translate(-50%, 20px); }
          to { opacity: 1; transform: translate(-50%, 0); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 0.8; }
          50% { opacity: 0.3; }
        }
        @keyframes slideInRight {
          from { opacity: 0; transform: translateX(40px); }
          to { opacity: 1; transform: translateX(0); }
        }
        div::-webkit-scrollbar { width: 4px; }
        div::-webkit-scrollbar-track { background: transparent; }
        div::-webkit-scrollbar-thumb { background: rgba(0,170,255,0.2); border-radius: 2px; }
      `}</style>
    </div>
  );
}
