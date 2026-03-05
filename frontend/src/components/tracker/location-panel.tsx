"use client";

import type { Submarket } from "@/lib/submarkets";

interface LocationPanelProps {
  submarkets: Submarket[];
  selectedSubmarket: string | null;
  hoveredSubmarket: string | null;
  onSelectSubmarket: (id: string | null) => void;
}

function getScoreColorHex(score: number): string {
  if (score >= 85) return "#00ff88";
  if (score >= 70) return "#00ccff";
  if (score >= 55) return "#ffaa00";
  return "#ff4466";
}

function getTrendArrow(trend: "up" | "stable" | "down"): string {
  if (trend === "up") return "▲";
  if (trend === "down") return "▼";
  return "●";
}

function getTrendColor(trend: "up" | "stable" | "down"): string {
  if (trend === "up") return "#00ff88";
  if (trend === "down") return "#ff4466";
  return "#888";
}

function getSignalText(score: number, sector: string): string {
  if (score >= 80) {
    return `Strong expansion signals detected across ${sector.toLowerCase()} sector. Multiple transcripts reference capacity additions and new DC development in this submarket.`;
  }
  if (score >= 60) {
    return "Moderate activity indicators. Network studies and exploratory language suggest potential future expansion. Monitoring recommended.";
  }
  return "Below-average expansion signals. Limited references to this market in recent earnings calls. Some consolidation language detected.";
}

export function LocationPanel({
  submarkets,
  selectedSubmarket,
  hoveredSubmarket,
  onSelectSubmarket,
}: LocationPanelProps) {
  const avgScore = Math.round(
    submarkets.reduce((a, b) => a + b.score, 0) / submarkets.length
  );

  return (
    <div>
      {/* Region Overview header */}
      <div className="text-[10px] font-mono tracking-[3px] text-blue-400 uppercase mb-4">
        Region Overview
      </div>

      {/* Stat cards */}
      <div className="flex gap-3 mb-6">
        <div className="flex-1 p-3 rounded-md bg-blue-500/5 border border-blue-500/15">
          <div
            className="text-[28px] font-bold font-mono"
            style={{ color: getScoreColorHex(avgScore) }}
          >
            {avgScore}
          </div>
          <div className="text-[10px] text-zinc-600 font-mono tracking-wider">
            AVG SCORE
          </div>
        </div>
        <div className="flex-1 p-3 rounded-md bg-blue-500/5 border border-blue-500/15">
          <div className="text-[28px] font-bold text-zinc-100 font-mono">
            {submarkets.length}
          </div>
          <div className="text-[10px] text-zinc-600 font-mono tracking-wider">
            MARKETS
          </div>
        </div>
      </div>

      {/* Submarkets label */}
      <div className="text-[10px] font-mono tracking-[3px] text-zinc-600 uppercase mb-2.5">
        Submarkets
      </div>

      {/* Submarket list */}
      {[...submarkets]
        .sort((a, b) => b.score - a.score)
        .map((sub) => {
          const isSelected = selectedSubmarket === sub.id;
          const isHovered = hoveredSubmarket === sub.id;

          return (
            <div
              key={sub.id}
              onClick={() =>
                onSelectSubmarket(isSelected ? null : sub.id)
              }
              className="rounded mb-1 cursor-pointer transition-all"
              style={{
                padding: "10px 12px",
                background: isSelected
                  ? "rgba(0,170,255,0.1)"
                  : isHovered
                    ? "rgba(0,170,255,0.05)"
                    : "transparent",
                border: isSelected
                  ? `1px solid ${getScoreColorHex(sub.score)}30`
                  : "1px solid transparent",
              }}
            >
              <div className="flex justify-between items-center">
                <div>
                  <div className="text-[13px] font-medium text-zinc-300 mb-0.5">
                    {sub.name}
                  </div>
                  <div className="text-[10px] text-zinc-600">
                    {sub.sector} · {sub.vacancy}% vac
                  </div>
                </div>
                <div className="text-right">
                  <div
                    className="text-lg font-bold font-mono"
                    style={{ color: getScoreColorHex(sub.score) }}
                  >
                    {sub.score}
                  </div>
                  <div
                    className="text-[10px]"
                    style={{ color: getTrendColor(sub.trend) }}
                  >
                    {getTrendArrow(sub.trend)} {sub.trend}
                  </div>
                </div>
              </div>

              {/* Expanded detail */}
              {isSelected && (
                <div className="mt-2.5 pt-2.5 border-t border-blue-500/10">
                  <div className="text-[10px] text-zinc-600 font-mono tracking-wider uppercase mb-1.5">
                    Recent Signals
                  </div>
                  <div className="text-[11px] text-zinc-500 leading-relaxed">
                    {getSignalText(sub.score, sub.sector)}
                  </div>
                  {/* Score bar */}
                  <div className="mt-2.5 h-[3px] bg-blue-500/10 rounded-sm overflow-hidden">
                    <div
                      className="h-full rounded-sm transition-[width] duration-500 ease-out"
                      style={{
                        width: `${sub.score}%`,
                        background: getScoreColorHex(sub.score),
                      }}
                    />
                  </div>
                </div>
              )}
            </div>
          );
        })}
    </div>
  );
}
