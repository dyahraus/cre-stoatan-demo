import type { SignalTier } from "@/lib/types";

const STYLES: Record<SignalTier, string> = {
  strong: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  moderate: "bg-blue-500/15 text-blue-300 border-blue-500/40",
  watchlist: "bg-amber-500/15 text-amber-300 border-amber-500/40",
  noise: "bg-zinc-700/30 text-zinc-400 border-zinc-700",
};

const LABEL: Record<SignalTier, string> = {
  strong: "Strong",
  moderate: "Moderate",
  watchlist: "Watchlist",
  noise: "Noise",
};

export function TierBadge({
  tier,
  size = "md",
  className = "",
}: {
  tier: SignalTier;
  size?: "sm" | "md";
  className?: string;
}) {
  const sizeClass =
    size === "sm" ? "text-[10px] px-1.5 py-0.5" : "text-xs px-2 py-1";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border font-medium uppercase tracking-wider ${sizeClass} ${STYLES[tier]} ${className}`}
    >
      {LABEL[tier]}
    </span>
  );
}

export function ConfidenceDots({
  confidence,
  size = "sm",
}: {
  confidence: number;
  size?: "sm" | "md";
}) {
  const filled = Math.round(Math.max(0, Math.min(1, confidence)) * 5);
  const dotSize = size === "md" ? "w-2 h-2" : "w-1.5 h-1.5";
  return (
    <span
      className="inline-flex items-center gap-0.5"
      title={`${Math.round(confidence * 100)}% confidence`}
    >
      {[0, 1, 2, 3, 4].map((i) => (
        <span
          key={i}
          className={`${dotSize} rounded-full ${
            i < filled ? "bg-blue-400" : "bg-zinc-700"
          }`}
        />
      ))}
    </span>
  );
}
