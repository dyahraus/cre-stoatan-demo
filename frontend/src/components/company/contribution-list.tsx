import type { ChunkContribution, ScoreComponents } from "@/lib/types";

const COMPONENT_META: {
  key: keyof ScoreComponents;
  label: string;
  weight: number; // matches the formula in scoring/aggregator.py
  blurb: string;
}[] = [
  {
    key: "max_expansion",
    label: "Peak signal",
    weight: 0.4,
    blurb: "Strongest single chunk in the transcript.",
  },
  {
    key: "weighted_avg",
    label: "Weighted average",
    weight: 0.3,
    blurb: "Average chunk score, weighted by warehouse relevance.",
  },
  {
    key: "flag_bonus",
    label: "Signal flags",
    weight: 0.15,
    blurb: "Capex / build-to-suit / last-mile bonus.",
  },
  {
    key: "time_bonus",
    label: "Time horizon",
    weight: 0.15,
    blurb: "Near-term mentions weighted higher than historical.",
  },
];

const FRAMEWORK_COMPONENTS: {
  key: keyof ScoreComponents;
  label: string;
  blurb: string;
}[] = [
  {
    key: "keyword_component",
    label: "Keyword match score",
    blurb:
      "Average per-chunk keyword strength under the active framework. Fed into chunk scores at 30% weight.",
  },
  {
    key: "commitment_component",
    label: "Commitment evidence",
    blurb:
      "Concentrated commitment-level hits — phrases backed by a $ amount, sqft, or date. 15% of every chunk score.",
  },
];

export function ContributionList({
  components,
  contributions,
  composite,
}: {
  components: ScoreComponents;
  contributions: ChunkContribution[];
  composite: number;
}) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4 space-y-4">
      <div className="flex justify-between items-baseline">
        <h3 className="text-sm font-semibold text-white">
          Score derivation
        </h3>
        <div className="text-xs text-zinc-500">
          Composite ={" "}
          <span className="font-mono text-zinc-200">
            {(composite * 100).toFixed(1)}%
          </span>
        </div>
      </div>

      <p className="text-xs text-zinc-500">
        The composite is a 4-component blend over relevant chunks. Each chunk
        score itself is 55% LLM expansion + 30% keyword strength + 15%
        commitment evidence — every contribution traces back to either an LLM
        rationale or a literal regex match.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {COMPONENT_META.map((m) => {
          const value = (components[m.key] ?? 0) as number;
          const contribution = value * m.weight;
          return (
            <ComponentBar
              key={m.key}
              label={m.label}
              weight={`${(m.weight * 100).toFixed(0)}%`}
              value={value}
              contribution={contribution}
              blurb={m.blurb}
            />
          );
        })}
      </div>

      {components.boost_multiplier !== undefined &&
        Math.abs(components.boost_multiplier - 1) > 0.001 && (
          <div className="rounded border border-blue-500/30 bg-blue-500/5 p-2.5 text-xs flex items-center justify-between">
            <span className="text-zinc-400">
              Section + speaker boosts (avg across relevant chunks)
            </span>
            <span className="font-mono text-blue-300">
              {components.boost_multiplier.toFixed(2)}× ·{" "}
              {components.boost_multiplier > 1 ? "+" : ""}
              {((components.boost_multiplier - 1) * 100).toFixed(0)}%
            </span>
          </div>
        )}

      <div className="border-t border-zinc-800 pt-3 space-y-2">
        <h4 className="text-xs uppercase tracking-wider text-zinc-500">
          Framework rollups (transparency)
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {FRAMEWORK_COMPONENTS.map((m) => (
            <FrameworkRollup
              key={m.key}
              label={m.label}
              value={components[m.key] ?? 0}
              blurb={m.blurb}
            />
          ))}
        </div>
      </div>

      {contributions.length > 0 && (
        <div className="border-t border-zinc-800 pt-3 space-y-2">
          <h4 className="text-xs uppercase tracking-wider text-zinc-500">
            Top contributing chunks
          </h4>
          <div className="space-y-2">
            {contributions.map((c) => (
              <div
                key={c.chunk_id}
                className="rounded border border-zinc-800 bg-zinc-900 p-3 text-xs space-y-1.5"
              >
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="font-mono text-zinc-500">
                    chunk #{c.chunk_index}
                  </span>
                  <span className="text-zinc-400">
                    contribution{" "}
                    <span className="font-mono text-white">
                      {(c.contribution * 100).toFixed(1)}%
                    </span>
                  </span>
                  <span className="text-zinc-400">
                    relevance{" "}
                    <span className="font-mono text-white">
                      {(c.warehouse_relevance * 100).toFixed(0)}
                    </span>
                  </span>
                  {c.keyword_hit_count > 0 && (
                    <span className="rounded bg-blue-500/20 text-blue-300 px-1.5 py-0.5 text-[10px] uppercase tracking-wider">
                      {c.keyword_hit_count} keyword
                      {c.keyword_hit_count === 1 ? "" : "s"}
                    </span>
                  )}
                </div>
                {c.evidence_quote && (
                  <blockquote className="border-l-2 border-blue-500/50 pl-2 italic text-zinc-300">
                    &ldquo;{c.evidence_quote}&rdquo;
                  </blockquote>
                )}
                {c.reasoning && (
                  <p className="text-zinc-500 text-[11px]">{c.reasoning}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ComponentBar({
  label,
  weight,
  value,
  contribution,
  blurb,
}: {
  label: string;
  weight: string;
  value: number;
  contribution: number;
  blurb: string;
}) {
  return (
    <div className="rounded bg-zinc-900 border border-zinc-800 p-2.5 space-y-1">
      <div className="flex justify-between items-baseline">
        <span className="text-xs font-medium text-zinc-200">{label}</span>
        <span className="text-[10px] text-zinc-500 uppercase tracking-wider">
          weight {weight}
        </span>
      </div>
      <div className="h-1.5 bg-zinc-800 rounded overflow-hidden">
        <div
          className="h-full bg-blue-500 transition-all"
          style={{ width: `${Math.min(100, value * 100)}%` }}
        />
      </div>
      <div className="flex justify-between items-baseline text-[11px]">
        <span className="text-zinc-500">{blurb}</span>
        <span className="font-mono text-zinc-300 tabular-nums">
          {(value * 100).toFixed(0)}% → +{(contribution * 100).toFixed(1)}%
        </span>
      </div>
    </div>
  );
}

function FrameworkRollup({
  label,
  value,
  blurb,
}: {
  label: string;
  value: number;
  blurb: string;
}) {
  return (
    <div className="rounded bg-zinc-900 border border-zinc-800 p-2.5 space-y-1">
      <div className="flex justify-between items-baseline">
        <span className="text-xs font-medium text-zinc-200">{label}</span>
        <span className="font-mono text-zinc-300 text-xs tabular-nums">
          {(value * 100).toFixed(0)}%
        </span>
      </div>
      <div className="h-1.5 bg-zinc-800 rounded overflow-hidden">
        <div
          className="h-full bg-amber-500 transition-all"
          style={{ width: `${Math.min(100, value * 100)}%` }}
        />
      </div>
      <p className="text-[11px] text-zinc-500">{blurb}</p>
    </div>
  );
}
