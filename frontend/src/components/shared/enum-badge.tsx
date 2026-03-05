import { Badge } from "@/components/ui/badge";
import { formatMoveType, formatHorizon } from "@/lib/format";
import type { MoveType, TimeHorizon } from "@/lib/types";

export function MoveTypeBadge({ moveType }: { moveType: MoveType }) {
  const colors: Record<string, string> = {
    expansion: "bg-emerald-600/20 text-emerald-400 border-emerald-600/30",
    new_market_entry: "bg-cyan-600/20 text-cyan-400 border-cyan-600/30",
    consolidation: "bg-orange-600/20 text-orange-400 border-orange-600/30",
    relocation: "bg-amber-600/20 text-amber-400 border-amber-600/30",
    optimization: "bg-slate-600/20 text-slate-400 border-slate-600/30",
    unknown: "bg-zinc-600/20 text-zinc-400 border-zinc-600/30",
  };
  return (
    <Badge className={`text-xs ${colors[moveType] || colors.unknown}`}>
      {formatMoveType(moveType)}
    </Badge>
  );
}

export function TimeHorizonBadge({ horizon }: { horizon: TimeHorizon }) {
  const colors: Record<string, string> = {
    immediate: "bg-red-600/20 text-red-400 border-red-600/30",
    near_term: "bg-orange-600/20 text-orange-400 border-orange-600/30",
    medium_term: "bg-yellow-600/20 text-yellow-400 border-yellow-600/30",
    long_term: "bg-blue-600/20 text-blue-400 border-blue-600/30",
    unspecified: "bg-zinc-600/20 text-zinc-400 border-zinc-600/30",
  };
  return (
    <Badge className={`text-xs ${colors[horizon] || colors.unspecified}`}>
      {formatHorizon(horizon)}
    </Badge>
  );
}
