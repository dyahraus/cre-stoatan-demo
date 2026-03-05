import { Badge } from "@/components/ui/badge";

interface SignalFlagsProps {
  hasCapex: boolean;
  hasBts: boolean;
  hasLastMile: boolean;
}

export function SignalFlags({ hasCapex, hasBts, hasLastMile }: SignalFlagsProps) {
  return (
    <div className="flex gap-1 flex-wrap">
      {hasCapex && (
        <Badge className="bg-green-600/20 text-green-400 border-green-600/30 text-xs">
          CAPEX
        </Badge>
      )}
      {hasBts && (
        <Badge className="bg-blue-600/20 text-blue-400 border-blue-600/30 text-xs">
          BTS
        </Badge>
      )}
      {hasLastMile && (
        <Badge className="bg-purple-600/20 text-purple-400 border-purple-600/30 text-xs">
          LM
        </Badge>
      )}
    </div>
  );
}
