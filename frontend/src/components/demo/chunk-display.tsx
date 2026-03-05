"use client";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { DemoChunkResult } from "@/lib/types";

interface ChunkDisplayProps {
  result: DemoChunkResult;
  selectedIndices: number[];
  onToggleChunk: (index: number) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
}

export function ChunkDisplay({
  result,
  selectedIndices,
  onToggleChunk,
  onSelectAll,
  onDeselectAll,
}: ChunkDisplayProps) {
  const allSelected = selectedIndices.length === result.chunks.length;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 text-sm text-zinc-400">
        <span>
          <span className="text-white font-semibold">
            {result.total_chunks}
          </span>{" "}
          chunks
        </span>
        <span>
          ~<span className="text-white font-semibold">{result.avg_tokens}</span>{" "}
          avg tokens
        </span>
        <span className="text-blue-400 font-medium">
          {selectedIndices.length} selected
        </span>
      </div>

      <div className="flex items-center gap-2">
        <p className="text-xs text-zinc-500">
          Select chunks to analyze:
        </p>
        <button
          onClick={allSelected ? onDeselectAll : onSelectAll}
          className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
        >
          {allSelected ? "Deselect All" : "Select All"}
        </button>
      </div>

      <div className="max-h-[400px] overflow-auto rounded-lg border border-zinc-800">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-zinc-900 text-zinc-500 text-xs">
            <tr>
              <th className="p-2 text-left w-12">#</th>
              <th className="p-2 text-left w-24">Section</th>
              <th className="p-2 text-right w-20">Tokens</th>
              <th className="p-2 text-left">Preview</th>
            </tr>
          </thead>
          <tbody>
            {result.chunks.map((chunk) => {
              const isSelected = selectedIndices.includes(chunk.chunk_index);
              return (
                <tr
                  key={chunk.chunk_index}
                  onClick={() => onToggleChunk(chunk.chunk_index)}
                  className={cn(
                    "cursor-pointer border-t border-zinc-800/50 transition-colors",
                    isSelected
                      ? "bg-blue-500/10"
                      : "hover:bg-zinc-800/30"
                  )}
                >
                  <td className="p-2">
                    <span
                      className={cn(
                        "inline-flex h-6 w-6 items-center justify-center rounded-full text-xs",
                        isSelected
                          ? "bg-blue-500 text-white"
                          : "bg-zinc-800 text-zinc-400"
                      )}
                    >
                      {chunk.chunk_index}
                    </span>
                  </td>
                  <td className="p-2">
                    <Badge variant="outline" className="text-[10px]">
                      {chunk.section_type.replace("_", " ")}
                    </Badge>
                  </td>
                  <td className="p-2 text-right text-zinc-400 font-mono text-xs">
                    {chunk.token_estimate}
                  </td>
                  <td className="p-2 text-xs text-zinc-500 truncate max-w-[300px]">
                    {chunk.text_preview}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
