"use client";

import { Badge } from "@/components/ui/badge";
import type { DemoParseResult } from "@/lib/types";

interface ParseDisplayProps {
  result: DemoParseResult;
}

export function ParseDisplay({ result }: ParseDisplayProps) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="text-sm text-zinc-400">
          {result.sections.length} section{result.sections.length !== 1 && "s"}{" "}
          detected
        </span>
        <Badge variant={result.boundary_found ? "default" : "secondary"}>
          {result.boundary_found ? "Q&A boundary found" : "No Q&A boundary"}
        </Badge>
      </div>

      <div className="space-y-3">
        {result.sections.map((section, i) => (
          <div
            key={i}
            className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-4"
          >
            <div className="flex items-center justify-between mb-2">
              <Badge variant="outline" className="text-xs">
                {section.section_type.replace("_", " ")}
              </Badge>
              <span className="text-xs text-zinc-500">
                {(section.text_length / 1000).toFixed(1)}K chars
              </span>
            </div>
            <div className="max-h-[200px] overflow-auto">
              <p className="text-xs text-zinc-500 font-mono leading-relaxed whitespace-pre-wrap">
                {section.text_preview}
              </p>
            </div>
          </div>
        ))}
      </div>

      {!result.boundary_found && (
        <p className="text-xs text-zinc-600 italic">
          The parser could not detect a Q&A transition in this transcript. The
          entire text is treated as a single section.
        </p>
      )}
    </div>
  );
}
