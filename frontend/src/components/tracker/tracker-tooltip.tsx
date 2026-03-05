"use client";

import type { Marker2D } from "@/components/tracker/tracker-globe";

interface TrackerTooltipProps {
  hoveredSubmarket: string | null;
  markers2D: Marker2D[];
}

function getScoreColorHex(score: number): string {
  if (score >= 85) return "#00ff88";
  if (score >= 70) return "#00ccff";
  if (score >= 55) return "#ffaa00";
  return "#ff4466";
}

function getTrendArrow(trend: string): string {
  if (trend === "up") return "▲";
  if (trend === "down") return "▼";
  return "●";
}

function getTrendColor(trend: string): string {
  if (trend === "up") return "#00ff88";
  if (trend === "down") return "#ff4466";
  return "#888";
}

export function TrackerTooltip({
  hoveredSubmarket,
  markers2D,
}: TrackerTooltipProps) {
  if (!hoveredSubmarket) return null;

  const marker = markers2D.find((m) => m.id === hoveredSubmarket);
  if (!marker) return null;

  return (
    <div
      className="absolute pointer-events-none z-10"
      style={{
        left: Math.max(80, Math.min(marker.x, (typeof window !== "undefined" ? window.innerWidth : 400) - 80)),
        top: Math.max(40, marker.y - 16),
        transform: "translate(-50%, -100%)",
      }}
    >
      <div
        className="px-3 py-2 rounded whitespace-nowrap"
        style={{
          background: "rgba(0,10,25,0.9)",
          border: `1px solid ${getScoreColorHex(marker.score)}40`,
          backdropFilter: "blur(12px)",
        }}
      >
        <div
          className="text-[10px] font-mono tracking-wider mb-0.5"
          style={{ color: getScoreColorHex(marker.score) }}
        >
          {marker.name}
        </div>
        <div className="text-[11px] text-zinc-500">
          Score:{" "}
          <span className="font-bold" style={{ color: getScoreColorHex(marker.score) }}>
            {marker.score}
          </span>
          {" "}
          <span style={{ color: getTrendColor(marker.trend), fontSize: 10 }}>
            {getTrendArrow(marker.trend)}
          </span>
          {" · "}Vacancy: {marker.vacancy}%
        </div>
      </div>
    </div>
  );
}
