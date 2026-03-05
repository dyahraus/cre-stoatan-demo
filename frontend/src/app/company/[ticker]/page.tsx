"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { fetchCompanyScore, fetchExtractions } from "@/lib/api";
import type { CompanyScore, SignalExtraction } from "@/lib/types";
import { ScorePanel } from "@/components/company/score-panel";
import { SignalDetails } from "@/components/company/signal-details";
import { EvidenceList } from "@/components/company/evidence-list";
import { ExtractionTable } from "@/components/company/extraction-table";

export default function CompanyDetailPage() {
  const params = useParams<{ ticker: string }>();
  const ticker = params.ticker?.toUpperCase() ?? "";
  const [score, setScore] = useState<CompanyScore | null>(null);
  const [extractions, setExtractions] = useState<SignalExtraction[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ticker) return;
    fetchCompanyScore(ticker)
      .then(setScore)
      .catch(() => setError("Company not found"));
    fetchExtractions(ticker)
      .then(setExtractions)
      .catch(() => {});
  }, [ticker]);

  if (error) {
    return (
      <div className="space-y-4">
        <Link
          href="/radar"
          className="text-sm text-blue-400 hover:text-blue-300"
        >
          &larr; Back to Radar
        </Link>
        <p className="text-zinc-500">{error}</p>
      </div>
    );
  }

  if (!score) {
    return <p className="text-zinc-500 text-sm py-8 text-center">Loading...</p>;
  }

  return (
    <div className="space-y-6">
      <Link
        href="/radar"
        className="inline-flex items-center text-sm text-blue-400 hover:text-blue-300 active:text-blue-300 py-2"
      >
        &larr; Back to Radar
      </Link>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ScorePanel score={score} />
        <SignalDetails score={score} />
      </div>

      <EvidenceList snippets={score.evidence_snippets} />
      <ExtractionTable extractions={extractions} />
    </div>
  );
}
