import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ScoreBadge } from "@/components/shared/score-badge";
import { MoveTypeBadge } from "@/components/shared/enum-badge";
import type { SignalExtraction } from "@/lib/types";

export function ExtractionTable({
  extractions,
}: {
  extractions: SignalExtraction[];
}) {
  if (extractions.length === 0) {
    return (
      <p className="text-zinc-500 text-sm py-4">No extractions available.</p>
    );
  }

  return (
    <div>
      <h3 className="text-sm text-zinc-400 font-semibold mb-3">
        Per-Chunk Extractions ({extractions.length})
      </h3>

      {/* Desktop table */}
      <div className="hidden md:block">
        <Table>
          <TableHeader>
            <TableRow className="border-zinc-800 hover:bg-transparent">
              <TableHead className="text-zinc-500">Transcript</TableHead>
              <TableHead className="text-zinc-500">Relevance</TableHead>
              <TableHead className="text-zinc-500">Expansion</TableHead>
              <TableHead className="text-zinc-500">Move</TableHead>
              <TableHead className="text-zinc-500 w-1/3">Evidence</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {extractions.map((e) => (
              <TableRow
                key={e.chunk_id}
                className="border-zinc-800 hover:bg-zinc-900/50"
              >
                <TableCell className="font-mono text-xs text-zinc-400">
                  {e.transcript_key}
                </TableCell>
                <TableCell>
                  <ScoreBadge score={e.warehouse_relevance} />
                </TableCell>
                <TableCell>
                  <ScoreBadge score={e.expansion_score} />
                </TableCell>
                <TableCell>
                  <MoveTypeBadge moveType={e.move_type} />
                </TableCell>
                <TableCell className="text-xs text-zinc-400 max-w-xs truncate">
                  {e.evidence_quote || "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Mobile cards */}
      <div className="md:hidden space-y-3">
        {extractions.map((e) => (
          <div
            key={e.chunk_id}
            className="p-3 bg-zinc-900 border border-zinc-800 rounded-lg space-y-2"
          >
            <div className="font-mono text-xs text-zinc-500 truncate">
              {e.transcript_key}
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <div>
                <div className="text-[10px] text-zinc-600 mb-0.5">Relevance</div>
                <ScoreBadge score={e.warehouse_relevance} />
              </div>
              <div>
                <div className="text-[10px] text-zinc-600 mb-0.5">Expansion</div>
                <ScoreBadge score={e.expansion_score} />
              </div>
              <div>
                <div className="text-[10px] text-zinc-600 mb-0.5">Move</div>
                <MoveTypeBadge moveType={e.move_type} />
              </div>
            </div>
            {e.evidence_quote && (
              <p className="text-xs text-zinc-400 italic line-clamp-2">
                {e.evidence_quote}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
