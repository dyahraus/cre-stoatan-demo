"use client";

import dynamic from "next/dynamic";
import { useCallback, useRef, useState } from "react";
import { MIDWEST_SUBMARKETS } from "@/lib/submarkets";
import type { Marker2D } from "@/components/tracker/tracker-globe";
import { TrackerTooltip } from "@/components/tracker/tracker-tooltip";
import { LocationPanel } from "@/components/tracker/location-panel";

const TrackerGlobe = dynamic(
  () => import("@/components/tracker/tracker-globe"),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full flex items-center justify-center bg-black">
        <div className="text-zinc-600 text-sm font-mono tracking-widest uppercase">
          Loading Globe...
        </div>
      </div>
    ),
  }
);

export default function TrackerPage() {
  const [zoomed, setZoomed] = useState(false);
  const [markers2D, setMarkers2D] = useState<Marker2D[]>([]);
  const [selectedSubmarket, setSelectedSubmarket] = useState<string | null>(null);
  const [hoveredSubmarket, setHoveredSubmarket] = useState<string | null>(null);
  const [sheetSnap, setSheetSnap] = useState<"collapsed" | "peek" | "expanded">("expanded");

  const sheetRef = useRef<HTMLDivElement>(null);
  const dragState = useRef({ startY: 0, startH: 0, lastY: 0, lastTime: 0 });

  const SNAP_COLLAPSED = 48;
  const SNAP_PEEK = 140;

  const handleMarkers2DChange = useCallback((m: Marker2D[]) => {
    setMarkers2D(m);
  }, []);

  const handleReset = () => {
    setZoomed(false);
    setSelectedSubmarket(null);
    setHoveredSubmarket(null);
    setSheetSnap("peek");
  };

  const handleSheetTouchStart = (e: React.TouchEvent) => {
    const y = e.touches[0].clientY;
    const h = sheetRef.current?.offsetHeight ?? SNAP_PEEK;
    dragState.current = { startY: y, startH: h, lastY: y, lastTime: Date.now() };
  };

  const handleSheetTouchMove = (e: React.TouchEvent) => {
    if (!sheetRef.current) return;
    const y = e.touches[0].clientY;
    const delta = dragState.current.startY - y;
    const maxH = window.innerHeight * 0.55;
    const newH = Math.max(SNAP_COLLAPSED, Math.min(dragState.current.startH + delta, maxH));
    sheetRef.current.style.height = `${newH}px`;
    sheetRef.current.style.transition = "none";
    dragState.current.lastY = y;
    dragState.current.lastTime = Date.now();
  };

  const handleSheetTouchEnd = () => {
    if (!sheetRef.current) return;
    const currentH = sheetRef.current.offsetHeight;
    const totalMove = Math.abs(dragState.current.startY - dragState.current.lastY);

    // Reset inline styles so CSS class takes over
    sheetRef.current.style.height = "";
    sheetRef.current.style.transition = "";

    // Tap detection (< 5px movement)
    if (totalMove < 5) {
      if (sheetSnap === "expanded") setSheetSnap("peek");
      else setSheetSnap("expanded");
      return;
    }

    // Velocity: positive = swiping down
    const velocity = (dragState.current.lastY - dragState.current.startY) / Math.max(1, Date.now() - dragState.current.lastTime);

    if (velocity > 0.3) {
      // Fast downward flick
      setSheetSnap(sheetSnap === "expanded" ? "peek" : "collapsed");
    } else if (velocity < -0.3) {
      // Fast upward flick
      setSheetSnap(sheetSnap === "collapsed" ? "peek" : "expanded");
    } else {
      // Snap to nearest
      const expandedPx = window.innerHeight * 0.55;
      const distances = [
        { snap: "collapsed" as const, d: Math.abs(currentH - SNAP_COLLAPSED) },
        { snap: "peek" as const, d: Math.abs(currentH - SNAP_PEEK) },
        { snap: "expanded" as const, d: Math.abs(currentH - expandedPx) },
      ];
      distances.sort((a, b) => a.d - b.d);
      setSheetSnap(distances[0].snap);
    }
  };

  return (
    <div className="-m-4 -mb-20 md:-m-6 md:-mb-6 h-screen relative overflow-hidden bg-black">
      {/* Top header overlay */}
      <div
        className="absolute top-0 left-0 right-0 z-10 px-4 py-4 md:px-8 md:py-6 flex justify-between items-center pointer-events-none"
        style={{
          background: "linear-gradient(180deg, rgba(0,5,16,0.9) 0%, transparent 100%)",
        }}
      >
        <div>
          <div className="text-[10px] md:text-[11px] font-mono tracking-[3px] md:tracking-[4px] text-blue-400 uppercase mb-1">
            Industrial Signal
          </div>
          <div className="text-lg md:text-xl font-bold text-zinc-200 tracking-tight">
            Market Tracker
          </div>
        </div>
        {zoomed && (
          <button
            onClick={handleReset}
            className="pointer-events-auto px-4 py-3 md:px-5 md:py-2 border border-blue-500/30 bg-[rgba(0,20,40,0.7)] text-blue-400 rounded font-mono text-[11px] tracking-widest uppercase cursor-pointer hover:bg-[rgba(0,30,60,0.8)] transition-colors"
            style={{ backdropFilter: "blur(8px)" }}
          >
            &larr; Globe
          </button>
        )}
      </div>

      {/* Globe canvas */}
      <TrackerGlobe
        submarkets={MIDWEST_SUBMARKETS}
        zoomed={zoomed}
        selectedSubmarket={selectedSubmarket}
        onZoomIn={() => setZoomed(true)}
        onHoverSubmarket={setHoveredSubmarket}
        onSelectSubmarket={(id) => {
          setSelectedSubmarket(id);
          if (id && window.innerWidth < 768) setSheetSnap("expanded");
        }}
        markers2D={markers2D}
        onMarkers2DChange={handleMarkers2DChange}
      />

      {/* Tooltip */}
      <TrackerTooltip
        hoveredSubmarket={hoveredSubmarket}
        markers2D={markers2D}
      />

      {/* Globe phase prompt */}
      {!zoomed && (
        <div className="absolute bottom-24 md:bottom-20 inset-x-0 flex justify-center pointer-events-none">
          <div
            className="text-center"
            style={{ animation: "fadeInUp 1s ease-out both" }}
          >
            <div className="text-xs font-mono tracking-widest text-blue-400/60 uppercase mb-2">
              Tap to explore
            </div>
            <div className="text-base text-zinc-200/50 font-light">
              Midwest Industrial Markets
            </div>
            <div
              className="w-px h-6 mx-auto mt-3"
              style={{ background: "linear-gradient(180deg, rgba(0,170,255,0.4), transparent)" }}
            />
          </div>
        </div>
      )}

      {/* Zooming text */}
      {zoomed && markers2D.length === 0 && (
        <div className="absolute bottom-24 md:bottom-20 inset-x-0 flex justify-center pointer-events-none">
          <div
            className="text-[11px] font-mono tracking-[4px] text-blue-400/80 uppercase"
            style={{ animation: "pulse-glow 1.5s ease-in-out infinite" }}
          >
            Approaching Midwest Region...
          </div>
        </div>
      )}

      {/* Panel — bottom sheet on mobile, right panel on desktop */}
      {zoomed && (
        <div
          ref={sheetRef}
          className={`absolute inset-x-0 bottom-0 ${
            sheetSnap === "collapsed" ? "h-[48px]" : sheetSnap === "peek" ? "h-[140px]" : "h-[55vh]"
          } transition-[height] duration-300 ease-out md:h-auto md:inset-x-auto md:right-0 md:top-0 md:bottom-0 md:w-80 border-t md:border-t-0 md:border-l border-blue-500/10 ${
            sheetSnap === "expanded" ? "overflow-y-auto" : "overflow-hidden"
          } md:overflow-y-auto animate-[slideUp_0.4s_ease-out] md:animate-[slideInRight_0.6s_ease-out] rounded-t-2xl md:rounded-none`}
          style={{
            background: "linear-gradient(0deg, rgba(0,5,16,0.98) 0%, rgba(0,5,16,0.92) 100%)",
            backdropFilter: "blur(20px)",
          }}
        >
          {/* Mobile drag handle */}
          <div
            className="flex flex-col items-center pt-2 pb-2 md:hidden cursor-grab active:cursor-grabbing"
            style={{ touchAction: "none" }}
            onTouchStart={handleSheetTouchStart}
            onTouchMove={handleSheetTouchMove}
            onTouchEnd={handleSheetTouchEnd}
          >
            <div className="w-10 h-1 rounded-full bg-zinc-600 mb-1" />
            <div className="text-[9px] font-mono tracking-widest text-zinc-600 uppercase">
              {sheetSnap === "expanded" ? "Swipe down" : "Swipe up"}
            </div>
          </div>
          <div className="p-5 pt-0 md:pt-20">
            <LocationPanel
              submarkets={MIDWEST_SUBMARKETS}
              selectedSubmarket={selectedSubmarket}
              hoveredSubmarket={hoveredSubmarket}
              onSelectSubmarket={setSelectedSubmarket}
            />
          </div>
        </div>
      )}

      {/* Bottom status bar — desktop only */}
      {zoomed && (
        <div
          className="absolute bottom-0 left-0 right-80 px-8 py-3 hidden md:flex justify-between items-center"
          style={{ background: "linear-gradient(0deg, rgba(0,5,16,0.9) 0%, transparent 100%)" }}
        >
          <div className="text-[10px] font-mono tracking-widest text-zinc-700">
            {MIDWEST_SUBMARKETS.length} SUBMARKETS · MIDWEST INDUSTRIAL CORRIDOR · EARNINGS SIGNAL SCAN
          </div>
          <div className="text-[10px] font-mono tracking-widest text-zinc-700">
            WAREHOUSE SIGNAL v0.1
          </div>
        </div>
      )}
    </div>
  );
}
