"use client";

import { useEffect, useRef } from "react";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { formatPercent } from "@/lib/format";

interface ExtractionStreamProps {
  streamText: string;
  isStreaming: boolean;
  extractions: Record<string, unknown>[];
  promptPreview: string | null;
  currentChunkLabel?: string;
}

export function ExtractionStream({
  streamText,
  isStreaming,
  extractions,
  promptPreview,
  currentChunkLabel,
}: ExtractionStreamProps) {
  const scrollRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [streamText]);

  return (
    <div className="space-y-4">
      {promptPreview && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-3">
          <p className="text-[10px] uppercase tracking-wider text-zinc-600 mb-1">
            Prompt sent to LLM
          </p>
          <p className="text-xs text-zinc-500 font-mono">{promptPreview}</p>
        </div>
      )}

      {/* Streaming terminal */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-950 overflow-hidden">
        <div className="flex items-center gap-2 px-3 py-2 border-b border-zinc-800 bg-zinc-900/50">
          <div className="flex gap-1.5">
            <div className="h-2.5 w-2.5 rounded-full bg-red-500/60" />
            <div className="h-2.5 w-2.5 rounded-full bg-yellow-500/60" />
            <div className="h-2.5 w-2.5 rounded-full bg-green-500/60" />
          </div>
          <span className="text-[10px] text-zinc-500 ml-2">
            LLM Response
            {currentChunkLabel && (
              <span className="text-zinc-600"> — {currentChunkLabel}</span>
            )}
          </span>
          {isStreaming && (
            <span className="ml-auto text-[10px] text-green-400 animate-pulse">
              streaming...
            </span>
          )}
        </div>
        <pre
          ref={scrollRef}
          className="p-4 text-xs font-mono text-green-400/90 leading-relaxed max-h-[300px] overflow-auto whitespace-pre-wrap break-words"
        >
          {streamText || (
            <span className="text-zinc-600">Waiting for response...</span>
          )}
          {isStreaming && (
            <span className="inline-block w-2 h-4 bg-green-400/80 ml-0.5 animate-pulse" />
          )}
        </pre>
      </div>

      {/* Parsed extraction results */}
      {extractions.map((ext, i) => (
        <ExtractionResult key={i} data={ext} index={extractions.length > 1 ? i : undefined} />
      ))}
    </div>
  );
}

function ExtractionResult({ data, index }: { data: Record<string, unknown>; index?: number }) {
  const relevance = (data.warehouse_relevance as number) ?? 0;
  const expansion = (data.expansion_score as number) ?? 0;
  const moveType = (data.move_type as string) ?? "unknown";
  const timeHorizon = (data.time_horizon as string) ?? "unspecified";
  const reasoning = (data.reasoning as string) ?? "";
  const evidence = (data.evidence_quote as string) ?? "";
  const signals = (data.signals as Record<string, unknown>) ?? {};
  const geoMentions = (data.geographic_mentions as Array<Record<string, unknown>>) ?? [];

  return (
    <div className="rounded-lg border border-green-500/20 bg-green-500/5 p-4 space-y-4">
      <p className="text-xs font-semibold text-green-400 uppercase tracking-wider">
        Parsed Extraction{index !== undefined ? ` — Chunk ${index + 1}` : ""}
      </p>

      {/* Score bars */}
      <div className="grid gap-3 md:grid-cols-2">
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-zinc-400">Warehouse Relevance</span>
            <span className="text-white font-mono">
              {formatPercent(relevance)}
            </span>
          </div>
          <Progress value={relevance * 100} className="h-2" />
        </div>
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-zinc-400">Expansion Score</span>
            <span className="text-white font-mono">
              {formatPercent(expansion)}
            </span>
          </div>
          <Progress value={expansion * 100} className="h-2" />
        </div>
      </div>

      {/* Badges */}
      <div className="flex flex-wrap gap-2">
        <Badge variant="outline">{moveType.replace("_", " ")}</Badge>
        <Badge variant="outline">{timeHorizon.replace("_", " ")}</Badge>
        {Boolean(signals.capex_expansion) && (
          <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
            CAPEX
          </Badge>
        )}
        {Boolean(signals.build_to_suit) && (
          <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30">
            BTS
          </Badge>
        )}
        {Boolean(signals.last_mile_expansion) && (
          <Badge className="bg-purple-500/20 text-purple-400 border-purple-500/30">
            Last-Mile
          </Badge>
        )}
      </div>

      {/* Geographies */}
      {geoMentions.length > 0 && (
        <div>
          <p className="text-xs text-zinc-500 mb-1">Geographic Mentions</p>
          <div className="flex flex-wrap gap-1.5">
            {geoMentions.map((g, i) => (
              <Badge key={i} variant="secondary" className="text-[10px]">
                {g.region as string}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Evidence */}
      {evidence && (
        <div>
          <p className="text-xs text-zinc-500 mb-1">Evidence Quote</p>
          <p className="text-xs text-zinc-300 italic border-l-2 border-zinc-700 pl-3">
            &ldquo;{evidence}&rdquo;
          </p>
        </div>
      )}

      {/* Reasoning */}
      {reasoning && (
        <div>
          <p className="text-xs text-zinc-500 mb-1">Reasoning</p>
          <p className="text-xs text-zinc-400">{reasoning}</p>
        </div>
      )}
    </div>
  );
}
