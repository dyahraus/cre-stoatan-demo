"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatSector } from "@/lib/format";
import type { EnumValues } from "@/lib/types";

interface RadarFiltersProps {
  enums: EnumValues | null;
  filters: {
    min_score: string;
    sector: string;
    geography: string;
    move_type: string;
    time_horizon: string;
  };
  onChange: (key: string, value: string) => void;
}

export function RadarFilters({ enums, filters, onChange }: RadarFiltersProps) {
  const [open, setOpen] = useState(false);

  return (
    <div>
      {/* Mobile toggle */}
      <button
        onClick={() => setOpen(!open)}
        className="flex md:hidden items-center gap-2 px-4 py-3 w-full bg-zinc-900 border border-zinc-800 rounded-lg text-sm text-zinc-300 mb-3"
      >
        <span>Filters</span>
        <span className="text-zinc-500 text-xs ml-auto">{open ? "Hide" : "Show"}</span>
      </button>

      {/* Filter controls */}
      <div className={`${open ? "grid" : "hidden"} md:flex grid-cols-2 flex-wrap gap-3 items-end`}>
        <div className="space-y-1">
          <label className="text-xs text-zinc-500">Min Score</label>
          <Input
            type="number"
            min="0"
            max="1"
            step="0.05"
            value={filters.min_score}
            onChange={(e) => onChange("min_score", e.target.value)}
            className="w-full md:w-24 bg-zinc-900 border-zinc-700"
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs text-zinc-500">Sector</label>
          <Select
            value={filters.sector}
            onValueChange={(v) => onChange("sector", v === "all" ? "" : v)}
          >
            <SelectTrigger className="w-full md:w-44 bg-zinc-900 border-zinc-700">
              <SelectValue placeholder="All Sectors" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Sectors</SelectItem>
              {enums?.sectors.map((s) => (
                <SelectItem key={s} value={s}>
                  {formatSector(s)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <label className="text-xs text-zinc-500">Geography</label>
          <Input
            placeholder="e.g. Texas"
            value={filters.geography}
            onChange={(e) => onChange("geography", e.target.value)}
            className="w-full md:w-36 bg-zinc-900 border-zinc-700"
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs text-zinc-500">Move Type</label>
          <Select
            value={filters.move_type}
            onValueChange={(v) => onChange("move_type", v === "all" ? "" : v)}
          >
            <SelectTrigger className="w-full md:w-40 bg-zinc-900 border-zinc-700">
              <SelectValue placeholder="All Types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              {enums?.move_types.map((m) => (
                <SelectItem key={m} value={m}>
                  {m.replace(/_/g, " ")}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <label className="text-xs text-zinc-500">Time Horizon</label>
          <Select
            value={filters.time_horizon}
            onValueChange={(v) => onChange("time_horizon", v === "all" ? "" : v)}
          >
            <SelectTrigger className="w-full md:w-40 bg-zinc-900 border-zinc-700">
              <SelectValue placeholder="All Horizons" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Horizons</SelectItem>
              {enums?.time_horizons.map((t) => (
                <SelectItem key={t} value={t}>
                  {t.replace(/_/g, " ")}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  );
}
