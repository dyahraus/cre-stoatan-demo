"use client";

import { Progress } from "@/components/ui/progress";
import { formatPercent } from "@/lib/format";
import type { DemoScoreResult } from "@/lib/types";

interface ScoreDisplayProps {
  result: DemoScoreResult;
}

const COMPONENT_META: Record<
  string,
  { label: string; weight: string; color: string }
> = {
  max_expansion: {
    label: "Max Expansion Score",
    weight: "40%",
    color: "text-blue-400",
  },
  weighted_avg: {
    label: "Weighted Avg (Relevance x Expansion)",
    weight: "30%",
    color: "text-purple-400",
  },
  flag_bonus: {
    label: "Signal Flag Bonus",
    weight: "15%",
    color: "text-green-400",
  },
  time_bonus: {
    label: "Time Horizon Bonus",
    weight: "15%",
    color: "text-yellow-400",
  },
};

export function ScoreDisplay({ result }: ScoreDisplayProps) {
  const { composite_score, is_relevant, components, extraction_summary, note } =
    result;

  return (
    <div className="space-y-5">
      {/* Composite score */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-4">
        <div className="flex items-baseline justify-between mb-2">
          <span className="text-sm font-semibold text-zinc-300">
            Composite Score
          </span>
          <span className="text-2xl font-bold text-white font-mono">
            {formatPercent(composite_score)}
          </span>
        </div>
        <Progress value={composite_score * 100} className="h-3" />
        {!is_relevant && (
          <p className="text-xs text-zinc-500 mt-2">
            Below relevance threshold — chunk scored as not warehouse-relevant.
          </p>
        )}
      </div>

      {/* Formula breakdown */}
      <div className="space-y-3">
        <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
          Formula Breakdown
        </p>
        {Object.entries(components).map(([key, comp]) => {
          const meta = COMPONENT_META[key];
          if (!meta) return null;
          return (
            <div
              key={key}
              className="rounded-lg border border-zinc-800/50 bg-zinc-900/30 p-3"
            >
              <div className="flex items-center justify-between text-xs mb-1.5">
                <div className="flex items-center gap-2">
                  <span className={meta.color}>{meta.label}</span>
                  <span className="text-zinc-600">({meta.weight})</span>
                </div>
                <span className="text-white font-mono">
                  {formatPercent(comp.contribution)}
                </span>
              </div>
              <Progress value={comp.value * 100} className="h-1.5" />
              <p className="text-[10px] text-zinc-600 mt-1">
                raw value: {formatPercent(comp.value)} x {meta.weight} ={" "}
                {formatPercent(comp.contribution)}
              </p>
              {comp.flags && (
                <p className="text-[10px] text-zinc-500 mt-0.5">
                  Flags: {comp.flags.capex ? "CAPEX " : ""}
                  {comp.flags.build_to_suit ? "BTS " : ""}
                  {comp.flags.last_mile ? "Last-Mile " : ""}
                  {!comp.flags.capex &&
                    !comp.flags.build_to_suit &&
                    !comp.flags.last_mile &&
                    "none"}
                </p>
              )}
              {comp.time_horizon && (
                <p className="text-[10px] text-zinc-500 mt-0.5">
                  Time horizon: {comp.time_horizon.replace("_", " ")}
                </p>
              )}
            </div>
          );
        })}
      </div>

      {/* Extraction summary */}
      <div className="rounded-lg border border-zinc-800/50 bg-zinc-900/30 p-3 space-y-1">
        <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">
          Extraction Input
        </p>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
          <span className="text-zinc-500">Relevance</span>
          <span className="text-white font-mono">
            {formatPercent(extraction_summary.warehouse_relevance)}
          </span>
          <span className="text-zinc-500">Expansion</span>
          <span className="text-white font-mono">
            {formatPercent(extraction_summary.expansion_score)}
          </span>
          <span className="text-zinc-500">Move Type</span>
          <span className="text-zinc-300">
            {extraction_summary.move_type.replace("_", " ")}
          </span>
          <span className="text-zinc-500">Time Horizon</span>
          <span className="text-zinc-300">
            {extraction_summary.time_horizon.replace("_", " ")}
          </span>
        </div>
        {extraction_summary.evidence_quote && (
          <p className="text-[10px] text-zinc-500 italic border-l-2 border-zinc-700 pl-2 mt-2">
            &ldquo;{extraction_summary.evidence_quote}&rdquo;
          </p>
        )}
      </div>

      {/* Note */}
      {note && (
        <p className="text-xs text-zinc-600 italic">{note}</p>
      )}
    </div>
  );
}
