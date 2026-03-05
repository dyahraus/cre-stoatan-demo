"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { fetchScores, fetchEnums } from "@/lib/api";
import type { CompanyScore, EnumValues } from "@/lib/types";
import { RadarFilters } from "@/components/radar/radar-filters";
import { RadarTable } from "@/components/radar/radar-table";

function RadarContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [scores, setScores] = useState<CompanyScore[]>([]);
  const [enums, setEnums] = useState<EnumValues | null>(null);
  const [loading, setLoading] = useState(true);

  const filters = {
    min_score: searchParams.get("min_score") || "0",
    sector: searchParams.get("sector") || "",
    geography: searchParams.get("geography") || "",
    move_type: searchParams.get("move_type") || "",
    time_horizon: searchParams.get("time_horizon") || "",
  };

  const updateFilter = useCallback(
    (key: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString());
      if (value) {
        params.set(key, value);
      } else {
        params.delete(key);
      }
      router.push(`/radar?${params.toString()}`);
    },
    [searchParams, router]
  );

  useEffect(() => {
    fetchEnums().then(setEnums).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (filters.min_score && parseFloat(filters.min_score) > 0)
      params.min_score = filters.min_score;
    if (filters.sector) params.sector = filters.sector;
    if (filters.geography) params.geography = filters.geography;
    if (filters.move_type) params.move_type = filters.move_type;
    if (filters.time_horizon) params.time_horizon = filters.time_horizon;

    fetchScores(params)
      .then(setScores)
      .catch(() => setScores([]))
      .finally(() => setLoading(false));
  }, [
    filters.min_score,
    filters.sector,
    filters.geography,
    filters.move_type,
    filters.time_horizon,
  ]);

  return (
    <>
      <RadarFilters enums={enums} filters={filters} onChange={updateFilter} />

      {loading ? (
        <p className="text-zinc-500 text-sm py-8 text-center">Loading...</p>
      ) : (
        <RadarTable scores={scores} />
      )}
    </>
  );
}

export default function RadarPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl md:text-2xl font-bold text-white">Deal Radar</h2>
        <p className="text-sm text-zinc-500 mt-1">
          Companies ranked by warehouse expansion signal strength
        </p>
      </div>

      <Suspense
        fallback={
          <p className="text-zinc-500 text-sm py-8 text-center">Loading...</p>
        }
      >
        <RadarContent />
      </Suspense>
    </div>
  );
}
