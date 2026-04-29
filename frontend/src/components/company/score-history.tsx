"use client";

import { useEffect, useState } from "react";
import { fetchCompanyHistory } from "@/lib/api";
import type { CompanyHistoryEntry, SignalTier } from "@/lib/types";
import { TierBadge } from "@/components/shared/tier-badge";

const TIER_COLOR: Record<SignalTier, string> = {
  strong: "#10b981", // emerald
  moderate: "#3b82f6", // blue
  watchlist: "#f59e0b", // amber
  noise: "#52525b", // zinc-600
};

export function ScoreHistory({ ticker }: { ticker: string }) {
  const [entries, setEntries] = useState<CompanyHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchCompanyHistory(ticker)
      .then(setEntries)
      .catch(() => setEntries([]))
      .finally(() => setLoading(false));
  }, [ticker]);

  if (loading) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
        <p className="text-sm text-zinc-500">Loading history...</p>
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4">
        <h3 className="text-sm font-semibold text-white">Quarterly history</h3>
        <p className="text-xs text-zinc-500 mt-2">
          No prior quarters scored yet. Upload another transcript on{" "}
          <code className="font-mono text-zinc-300">/demo</code> to start a
          timeline.
        </p>
      </div>
    );
  }

  // SVG sparkline geometry
  const W = 480;
  const H = 80;
  const PADX = 16;
  const PADY = 12;
  const xStep =
    entries.length > 1 ? (W - PADX * 2) / (entries.length - 1) : 0;

  const points = entries.map((e, i) => ({
    cx: PADX + i * xStep,
    cy: PADY + (1 - e.composite_score) * (H - PADY * 2),
    entry: e,
  }));

  const pathD = points
    .map((p, i) => (i === 0 ? `M ${p.cx} ${p.cy}` : `L ${p.cx} ${p.cy}`))
    .join(" ");

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4 space-y-3">
      <div className="flex justify-between items-baseline">
        <h3 className="text-sm font-semibold text-white">Quarterly history</h3>
        <span className="text-xs text-zinc-500">
          {entries.length} {entries.length === 1 ? "quarter" : "quarters"}
        </span>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        preserveAspectRatio="none"
      >
        <line
          x1={PADX}
          x2={W - PADX}
          y1={H / 2}
          y2={H / 2}
          stroke="#27272a"
          strokeDasharray="2 4"
        />
        <path
          d={pathD}
          stroke="#3f3f46"
          strokeWidth={1.5}
          fill="none"
        />
        {points.map((p, i) => (
          <circle
            key={i}
            cx={p.cx}
            cy={p.cy}
            r={5}
            fill={TIER_COLOR[p.entry.tier]}
          >
            <title>
              {p.entry.year} Q{p.entry.quarter} ·{" "}
              {(p.entry.composite_score * 100).toFixed(0)}% · {p.entry.tier}
            </title>
          </circle>
        ))}
      </svg>

      <div className="space-y-1.5 max-h-64 overflow-y-auto">
        {[...entries].reverse().map((e) => (
          <div
            key={e.quarter_key}
            className="flex items-center justify-between gap-3 rounded bg-zinc-900 px-2 py-1.5 text-xs"
          >
            <span className="font-mono text-zinc-400 shrink-0 w-16">
              {e.year} Q{e.quarter}
            </span>
            <TierBadge tier={e.tier} size="sm" />
            <span className="font-mono text-zinc-200 tabular-nums shrink-0 w-12 text-right">
              {(e.composite_score * 100).toFixed(0)}%
            </span>
            <span className="text-zinc-500 truncate flex-1 italic">
              {e.top_evidence
                ? `"${e.top_evidence.slice(0, 80)}${e.top_evidence.length > 80 ? "..." : ""}"`
                : "(no evidence quote)"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
