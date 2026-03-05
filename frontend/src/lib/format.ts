import type { MoveType, TimeHorizon } from "./types";

export function getScoreColor(score: number): string {
  if (score >= 0.7) return "text-green-400";
  if (score >= 0.4) return "text-yellow-400";
  return "text-zinc-400";
}

export function getScoreBg(score: number): string {
  if (score >= 0.7) return "bg-green-500/20 text-green-400 border-green-500/30";
  if (score >= 0.4)
    return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
  return "bg-zinc-500/20 text-zinc-400 border-zinc-500/30";
}

export function formatPercent(n: number): string {
  return `${(n * 100).toFixed(1)}%`;
}

const HORIZON_LABELS: Record<TimeHorizon, string> = {
  immediate: "Immediate",
  near_term: "Near Term",
  medium_term: "Medium Term",
  long_term: "Long Term",
  unspecified: "Unspecified",
};

const MOVE_LABELS: Record<MoveType, string> = {
  expansion: "Expansion",
  consolidation: "Consolidation",
  relocation: "Relocation",
  new_market_entry: "New Market Entry",
  optimization: "Optimization",
  unknown: "Unknown",
};

export function formatHorizon(h: TimeHorizon): string {
  return HORIZON_LABELS[h] || h;
}

export function formatMoveType(m: MoveType): string {
  return MOVE_LABELS[m] || m;
}

export function formatSector(s: string): string {
  return s
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}
