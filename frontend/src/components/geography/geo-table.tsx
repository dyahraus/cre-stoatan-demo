import Link from "next/link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ScoreBadge } from "@/components/shared/score-badge";
import type { GeographySummary } from "@/lib/types";

export function GeoTable({ data }: { data: GeographySummary[] }) {
  if (data.length === 0) {
    return (
      <p className="text-zinc-500 text-sm py-8 text-center">
        No geography data available.
      </p>
    );
  }

  return (
    <>
      {/* Desktop table */}
      <div className="hidden md:block">
        <Table>
          <TableHeader>
            <TableRow className="border-zinc-800 hover:bg-transparent">
              <TableHead className="text-zinc-500">Region</TableHead>
              <TableHead className="text-zinc-500"># Companies</TableHead>
              <TableHead className="text-zinc-500">Avg Score</TableHead>
              <TableHead className="text-zinc-500">Max Score</TableHead>
              <TableHead className="text-zinc-500">Tickers</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((g) => (
              <TableRow key={g.region} className="border-zinc-800 hover:bg-zinc-900/50">
                <TableCell className="font-semibold text-zinc-200">
                  {g.region}
                </TableCell>
                <TableCell className="text-zinc-400">{g.num_companies}</TableCell>
                <TableCell>
                  <ScoreBadge score={g.avg_score} />
                </TableCell>
                <TableCell>
                  <ScoreBadge score={g.max_score} />
                </TableCell>
                <TableCell>
                  <div className="flex gap-1 flex-wrap">
                    {g.tickers.map((t) => (
                      <Link
                        key={t}
                        href={`/company/${t}`}
                        className="text-xs font-mono text-blue-400 hover:text-blue-300"
                      >
                        {t}
                      </Link>
                    ))}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Mobile card list */}
      <div className="md:hidden space-y-3">
        {data.map((g) => (
          <div
            key={g.region}
            className="p-4 bg-zinc-900 border border-zinc-800 rounded-lg"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold text-zinc-200">{g.region}</span>
              <span className="text-xs text-zinc-500">{g.num_companies} companies</span>
            </div>
            <div className="flex items-center gap-3 mb-3">
              <div>
                <div className="text-[10px] text-zinc-600 uppercase mb-0.5">Avg</div>
                <ScoreBadge score={g.avg_score} />
              </div>
              <div>
                <div className="text-[10px] text-zinc-600 uppercase mb-0.5">Max</div>
                <ScoreBadge score={g.max_score} />
              </div>
            </div>
            <div className="flex gap-2 flex-wrap">
              {g.tickers.map((t) => (
                <Link
                  key={t}
                  href={`/company/${t}`}
                  className="text-xs font-mono text-blue-400 active:text-blue-300 py-1"
                >
                  {t}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
