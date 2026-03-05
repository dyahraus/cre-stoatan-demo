import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SignalFlags } from "@/components/shared/signal-flags";
import { MoveTypeBadge, TimeHorizonBadge } from "@/components/shared/enum-badge";
import type { CompanyScore } from "@/lib/types";

export function SignalDetails({ score }: { score: CompanyScore }) {
  return (
    <Card className="bg-zinc-900 border-zinc-800">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm text-zinc-400">Signal Details</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <p className="text-xs text-zinc-500 mb-2">Signal Flags</p>
          <SignalFlags
            hasCapex={score.has_capex_signal}
            hasBts={score.has_build_to_suit}
            hasLastMile={score.has_last_mile}
          />
        </div>

        <div className="flex gap-6">
          <div>
            <p className="text-xs text-zinc-500 mb-1">Move Type</p>
            <MoveTypeBadge moveType={score.dominant_move_type} />
          </div>
          <div>
            <p className="text-xs text-zinc-500 mb-1">Time Horizon</p>
            <TimeHorizonBadge horizon={score.dominant_time_horizon} />
          </div>
        </div>

        <div>
          <p className="text-xs text-zinc-500 mb-2">Top Geographies</p>
          <div className="flex gap-1 flex-wrap">
            {score.top_geographies.map((g) => (
              <Badge
                key={g}
                variant="outline"
                className="border-zinc-700 text-zinc-300 text-xs"
              >
                {g}
              </Badge>
            ))}
            {score.top_geographies.length === 0 && (
              <span className="text-xs text-zinc-600">None detected</span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
