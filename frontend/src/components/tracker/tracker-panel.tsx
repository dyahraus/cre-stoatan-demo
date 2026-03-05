"use client";

import Link from "next/link";
import { ScoreBadge } from "@/components/shared/score-badge";
import { SignalFlags } from "@/components/shared/signal-flags";
import { MoveTypeBadge, TimeHorizonBadge } from "@/components/shared/enum-badge";
import { LocationPanel } from "@/components/tracker/location-panel";
import { formatRegionName } from "@/lib/geo-coords";
import type { CompanyScore, GeographySummary } from "@/lib/types";
import type { Submarket } from "@/lib/submarkets";

interface TrackerPanelProps {
  geographies: GeographySummary[];
  scores: CompanyScore[];
  selectedRegion: string | null;
  onSelectRegion: (id: string | null) => void;
  panelMode: "locations" | "companies";
  onPanelModeChange: (mode: "locations" | "companies") => void;
  submarkets: Submarket[];
  selectedSubmarket: string | null;
  hoveredSubmarket: string | null;
  onSelectSubmarket: (id: string | null) => void;
  isDrilldownRegion: boolean;
}

function getScoreColorHex(score: number): string {
  if (score >= 0.85) return "#00ff88";
  if (score >= 0.7) return "#00ccff";
  if (score >= 0.55) return "#ffaa00";
  return "#ff4466";
}

export function TrackerPanel({
  geographies,
  scores,
  selectedRegion,
  onSelectRegion,
  panelMode,
  onPanelModeChange,
  submarkets,
  selectedSubmarket,
  hoveredSubmarket,
  onSelectSubmarket,
  isDrilldownRegion,
}: TrackerPanelProps) {
  const selectedGeo = geographies.find((g) => g.region === selectedRegion);
  const regionScores = selectedGeo
    ? scores.filter((s) => selectedGeo.tickers.includes(s.ticker))
    : [];

  return (
    <div
      className="absolute right-0 top-0 bottom-0 w-80 border-l border-blue-500/10 overflow-y-auto animate-[slideInRight_0.6s_ease-out]"
      style={{
        background: "linear-gradient(270deg, rgba(0,5,16,0.95) 0%, rgba(0,5,16,0.8) 100%)",
        backdropFilter: "blur(20px)",
      }}
    >
      <div className="p-5 pt-6">
        {/* Toggle tabs — only show when in a drill-down region */}
        {selectedRegion && isDrilldownRegion && (
          <>
            <button
              onClick={() => onSelectRegion(null)}
              className="text-xs text-blue-400 hover:text-blue-300 font-mono tracking-wider uppercase mb-3"
            >
              &larr; All Regions
            </button>
            <h3 className="text-lg font-semibold text-zinc-100 mb-4">
              {formatRegionName(selectedRegion)}
            </h3>
            <div className="flex mb-5 border-b border-zinc-800">
              <button
                onClick={() => onPanelModeChange("locations")}
                className={`flex-1 pb-2 text-xs font-mono tracking-wider uppercase transition-colors ${
                  panelMode === "locations"
                    ? "text-blue-400 border-b-2 border-blue-400"
                    : "text-zinc-600 hover:text-zinc-400"
                }`}
              >
                Locations
              </button>
              <button
                onClick={() => onPanelModeChange("companies")}
                className={`flex-1 pb-2 text-xs font-mono tracking-wider uppercase transition-colors ${
                  panelMode === "companies"
                    ? "text-blue-400 border-b-2 border-blue-400"
                    : "text-zinc-600 hover:text-zinc-400"
                }`}
              >
                Companies
              </button>
            </div>

            {panelMode === "locations" ? (
              <LocationPanel
                submarkets={submarkets}
                selectedSubmarket={selectedSubmarket}
                hoveredSubmarket={hoveredSubmarket}
                onSelectSubmarket={onSelectSubmarket}
              />
            ) : (
              <CompanyList scores={regionScores} />
            )}
          </>
        )}

        {/* Non-drilldown selected region — just company view */}
        {selectedRegion && !isDrilldownRegion && selectedGeo && (
          <>
            <button
              onClick={() => onSelectRegion(null)}
              className="text-xs text-blue-400 hover:text-blue-300 font-mono tracking-wider uppercase mb-4"
            >
              &larr; All Regions
            </button>
            <h3 className="text-lg font-semibold text-zinc-100 mb-4">
              {formatRegionName(selectedRegion)}
            </h3>
            <div className="flex gap-3 mb-4">
              <div className="flex-1 p-3 rounded-md bg-blue-500/5 border border-blue-500/15">
                <div
                  className="text-2xl font-bold font-mono"
                  style={{ color: getScoreColorHex(selectedGeo.avg_score) }}
                >
                  {Math.round(selectedGeo.avg_score * 100)}
                </div>
                <div className="text-[10px] text-zinc-500 font-mono tracking-wider">AVG SCORE</div>
              </div>
              <div className="flex-1 p-3 rounded-md bg-blue-500/5 border border-blue-500/15">
                <div className="text-2xl font-bold text-zinc-100 font-mono">{selectedGeo.num_companies}</div>
                <div className="text-[10px] text-zinc-500 font-mono tracking-wider">COMPANIES</div>
              </div>
            </div>
            <CompanyList scores={regionScores} />
          </>
        )}

        {/* No region selected — show all regions list */}
        {!selectedRegion && (
          <>
            <div className="text-[10px] text-blue-400 font-mono tracking-widest uppercase mb-3">
              All Regions
            </div>
            <div className="space-y-0.5">
              {geographies
                .sort((a, b) => b.avg_score - a.avg_score)
                .map((g) => (
                  <button
                    key={g.region}
                    onClick={() => onSelectRegion(g.region)}
                    className="w-full text-left p-3 rounded hover:bg-blue-500/5 transition-colors"
                  >
                    <div className="flex justify-between items-center">
                      <div>
                        <div className="text-sm font-medium text-zinc-300">
                          {formatRegionName(g.region)}
                        </div>
                        <div className="text-[10px] text-zinc-600 mt-0.5">
                          {g.num_companies} companies
                        </div>
                      </div>
                      <div
                        className="text-lg font-bold font-mono"
                        style={{ color: getScoreColorHex(g.avg_score) }}
                      >
                        {Math.round(g.avg_score * 100)}
                      </div>
                    </div>
                  </button>
                ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// Extracted company list sub-component
function CompanyList({ scores }: { scores: CompanyScore[] }) {
  if (scores.length === 0) {
    return <p className="text-xs text-zinc-600">No companies in this region.</p>;
  }
  return (
    <div className="space-y-1">
      <div className="text-[10px] text-zinc-600 font-mono tracking-widest uppercase mb-2">
        Companies
      </div>
      {scores
        .sort((a, b) => b.composite_score - a.composite_score)
        .map((s) => (
          <Link
            key={s.ticker}
            href={`/company/${s.ticker}`}
            className="block p-3 rounded hover:bg-blue-500/5 transition-colors group"
          >
            <div className="flex justify-between items-start">
              <div>
                <div className="text-sm font-semibold text-zinc-200 group-hover:text-white">
                  <span className="font-mono text-blue-400">{s.ticker}</span>{" "}
                  <span className="text-zinc-400 font-normal">{s.company_name}</span>
                </div>
                <div className="flex gap-1 mt-1.5">
                  <MoveTypeBadge moveType={s.dominant_move_type} />
                  <TimeHorizonBadge horizon={s.dominant_time_horizon} />
                </div>
              </div>
              <ScoreBadge score={s.composite_score} />
            </div>
            <div className="mt-1.5">
              <SignalFlags
                hasCapex={s.has_capex_signal}
                hasBts={s.has_build_to_suit}
                hasLastMile={s.has_last_mile}
              />
            </div>
          </Link>
        ))}
    </div>
  );
}
