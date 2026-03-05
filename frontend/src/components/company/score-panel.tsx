import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { ScoreBadge } from "@/components/shared/score-badge";
import { formatPercent, formatSector } from "@/lib/format";
import type { CompanyScore } from "@/lib/types";

export function ScorePanel({ score }: { score: CompanyScore }) {
  return (
    <Card className="bg-zinc-900 border-zinc-800">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="text-lg md:text-xl text-white">
              {score.ticker}{" "}
              <span className="text-zinc-400 font-normal">
                {score.company_name}
              </span>
            </CardTitle>
            <p className="text-xs text-zinc-500 mt-1">
              {formatSector(score.sector)}
            </p>
          </div>
          <ScoreBadge score={score.composite_score} />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <div className="flex justify-between text-xs text-zinc-500 mb-1">
            <span>Composite Score</span>
            <span>{formatPercent(score.composite_score)}</span>
          </div>
          <Progress value={score.composite_score * 100} className="h-2" />
        </div>

        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-zinc-500">Avg Expansion</span>
            <p className="text-white font-mono">
              {formatPercent(score.avg_expansion_score)}
            </p>
          </div>
          <div>
            <span className="text-zinc-500">Max Expansion</span>
            <p className="text-white font-mono">
              {formatPercent(score.max_expansion_score)}
            </p>
          </div>
          <div>
            <span className="text-zinc-500">Avg Relevance</span>
            <p className="text-white font-mono">
              {formatPercent(score.avg_warehouse_relevance)}
            </p>
          </div>
          <div>
            <span className="text-zinc-500">Relevant Chunks</span>
            <p className="text-white font-mono">
              {score.num_relevant_chunks} / {score.total_chunks}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
