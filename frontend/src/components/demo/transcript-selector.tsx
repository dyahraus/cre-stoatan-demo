"use client";

import { cn } from "@/lib/utils";
import type { DemoTranscript } from "@/lib/types";

interface TranscriptSelectorProps {
  transcripts: DemoTranscript[];
  selected: DemoTranscript | null;
  onSelect: (t: DemoTranscript) => void;
}

export function TranscriptSelector({
  transcripts,
  selected,
  onSelect,
}: TranscriptSelectorProps) {
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {transcripts.map((t) => {
        const isSelected = selected?.quarter_key === t.quarter_key;
        return (
          <button
            key={t.quarter_key}
            onClick={() => onSelect(t)}
            className={cn(
              "rounded-lg border p-4 text-left transition-all",
              isSelected
                ? "border-blue-500 bg-blue-500/10"
                : "border-zinc-800 bg-zinc-900/50 hover:border-zinc-600 hover:bg-zinc-900"
            )}
          >
            <div className="flex items-baseline justify-between">
              <span className="text-lg font-bold text-white">{t.ticker}</span>
              <span className="text-xs text-zinc-500">
                FY{t.year} Q{t.quarter}
              </span>
            </div>
            <p className="mt-1 text-sm text-zinc-400">{t.company_name}</p>
            <div className="mt-3 flex items-center justify-between text-xs text-zinc-500">
              <span>{(t.raw_text_length / 1000).toFixed(0)}K chars</span>
              {t.call_date && <span>{t.call_date}</span>}
            </div>
          </button>
        );
      })}
    </div>
  );
}
