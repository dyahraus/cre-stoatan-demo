import Link from "next/link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { ScoreBadge } from "@/components/shared/score-badge";
import { SignalFlags } from "@/components/shared/signal-flags";
import { MoveTypeBadge, TimeHorizonBadge } from "@/components/shared/enum-badge";
import type { CompanyScore } from "@/lib/types";

export function RadarTable({ scores }: { scores: CompanyScore[] }) {
  if (scores.length === 0) {
    return (
      <p className="text-zinc-500 text-sm py-8 text-center">
        No companies match the current filters.
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
              <TableHead className="w-12 text-zinc-500">#</TableHead>
              <TableHead className="text-zinc-500">Ticker</TableHead>
              <TableHead className="text-zinc-500">Company</TableHead>
              <TableHead className="text-zinc-500">Score</TableHead>
              <TableHead className="text-zinc-500">Move</TableHead>
              <TableHead className="text-zinc-500">Horizon</TableHead>
              <TableHead className="text-zinc-500">Geographies</TableHead>
              <TableHead className="text-zinc-500">Signals</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {scores.map((s, i) => (
              <TableRow key={s.ticker} className="border-zinc-800 hover:bg-zinc-900/50">
                <TableCell className="text-zinc-500 font-mono text-xs">
                  {i + 1}
                </TableCell>
                <TableCell>
                  <Link
                    href={`/company/${s.ticker}`}
                    className="font-mono font-semibold text-blue-400 hover:text-blue-300"
                  >
                    {s.ticker}
                  </Link>
                </TableCell>
                <TableCell className="text-zinc-300">{s.company_name}</TableCell>
                <TableCell>
                  <ScoreBadge score={s.composite_score} />
                </TableCell>
                <TableCell>
                  <MoveTypeBadge moveType={s.dominant_move_type} />
                </TableCell>
                <TableCell>
                  <TimeHorizonBadge horizon={s.dominant_time_horizon} />
                </TableCell>
                <TableCell>
                  <div className="flex gap-1 flex-wrap">
                    {s.top_geographies.slice(0, 3).map((g) => (
                      <Badge
                        key={g}
                        variant="outline"
                        className="text-xs border-zinc-700 text-zinc-400"
                      >
                        {g}
                      </Badge>
                    ))}
                  </div>
                </TableCell>
                <TableCell>
                  <SignalFlags
                    hasCapex={s.has_capex_signal}
                    hasBts={s.has_build_to_suit}
                    hasLastMile={s.has_last_mile}
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Mobile card list */}
      <div className="md:hidden space-y-3">
        {scores.map((s, i) => (
          <Link
            key={s.ticker}
            href={`/company/${s.ticker}`}
            className="block p-4 bg-zinc-900 border border-zinc-800 rounded-lg active:bg-zinc-800 transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-zinc-600 font-mono text-xs">{i + 1}</span>
                <span className="font-mono font-semibold text-blue-400">{s.ticker}</span>
                <span className="text-zinc-400 text-sm truncate">{s.company_name}</span>
              </div>
              <ScoreBadge score={s.composite_score} />
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <MoveTypeBadge moveType={s.dominant_move_type} />
              <TimeHorizonBadge horizon={s.dominant_time_horizon} />
              <SignalFlags
                hasCapex={s.has_capex_signal}
                hasBts={s.has_build_to_suit}
                hasLastMile={s.has_last_mile}
              />
            </div>
            {s.top_geographies.length > 0 && (
              <div className="flex gap-1 flex-wrap mt-2">
                {s.top_geographies.slice(0, 3).map((g) => (
                  <Badge
                    key={g}
                    variant="outline"
                    className="text-[10px] border-zinc-700 text-zinc-500"
                  >
                    {g}
                  </Badge>
                ))}
              </div>
            )}
          </Link>
        ))}
      </div>
    </>
  );
}
