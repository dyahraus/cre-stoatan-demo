"use client";

import { useEffect, useState } from "react";
import { fetchGeographies } from "@/lib/api";
import type { GeographySummary } from "@/lib/types";
import { GeoTable } from "@/components/geography/geo-table";

const MIDWEST_REGIONS = new Set([
  "US_Midwest", "Midwest",
  "Indianapolis", "Chicago", "Columbus", "Columbus_OH",
  "Kansas_City", "Cincinnati", "St_Louis", "Minneapolis",
  "Milwaukee", "Detroit", "Louisville", "Memphis",
  "Ohio", "Grand_Rapids",
]);

function isMidwestRegion(region: string): boolean {
  if (MIDWEST_REGIONS.has(region)) return true;
  const lower = region.toLowerCase().replace(/_/g, " ");
  return lower.includes("midwest") || lower.includes("chicago")
    || lower.includes("indianapolis") || lower.includes("columbus")
    || lower.includes("kansas city") || lower.includes("cincinnati")
    || lower.includes("st louis") || lower.includes("minneapolis")
    || lower.includes("milwaukee") || lower.includes("detroit");
}

export default function GeographyPage() {
  const [data, setData] = useState<GeographySummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchGeographies()
      .then((all) => setData(all.filter((g) => isMidwestRegion(g.region))))
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl md:text-2xl font-bold text-white">Geography</h2>
        <p className="text-sm text-zinc-500 mt-1">
          Midwest regions ranked by average expansion signal strength
        </p>
      </div>

      {loading ? (
        <p className="text-zinc-500 text-sm py-8 text-center">Loading...</p>
      ) : (
        <GeoTable data={data} />
      )}
    </div>
  );
}
