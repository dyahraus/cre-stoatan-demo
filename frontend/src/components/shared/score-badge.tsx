import { Badge } from "@/components/ui/badge";
import { getScoreBg, formatPercent } from "@/lib/format";

export function ScoreBadge({ score }: { score: number }) {
  return (
    <Badge variant="outline" className={`font-mono ${getScoreBg(score)}`}>
      {formatPercent(score)}
    </Badge>
  );
}
