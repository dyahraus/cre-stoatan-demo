"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  addKeyword,
  deleteKeyword,
  dryRunFramework,
  fetchFrameworks,
  patchKeyword,
} from "@/lib/api";
import type {
  DryRunResult,
  KeywordCategory,
  SignalFramework,
  SignalKeyword,
} from "@/lib/types";

const CATEGORY_META: {
  key: KeywordCategory;
  title: string;
  blurb: string;
}[] = [
  {
    key: "industrial_transformation",
    title: "Industrial Transformation",
    blurb:
      "Phrases naming concrete industrial assets — DCs, fulfillment centers, automation, build-to-suit.",
  },
  {
    key: "supply_chain",
    title: "Supply Chain Language",
    blurb:
      "Network design and capacity language — the broker leading indicators.",
  },
  {
    key: "commitment_level",
    title: "Commitment Level",
    blurb:
      "Verbs that tell us if it's actually happening. Each requires a $ amount, sqft, or specific date nearby.",
  },
];

export default function FrameworkPage() {
  const [framework, setFramework] = useState<SignalFramework | null>(null);
  const [allFrameworks, setAllFrameworks] = useState<SignalFramework[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [dryRunText, setDryRunText] = useState(
    "We broke ground on two new distribution centers and committed approximately 180 million in logistics capex over the next 18 months. Three build-to-suit projects are under letter of intent for Q3 2026."
  );
  const [dryRunResult, setDryRunResult] = useState<DryRunResult | null>(null);
  const [running, setRunning] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const fws = await fetchFrameworks();
      setAllFrameworks(fws);
      const def = fws.find((f) => f.is_default) ?? fws[0] ?? null;
      setFramework(def);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const groups = useMemo(() => {
    if (!framework) return null;
    const out: Record<KeywordCategory, SignalKeyword[]> = {
      industrial_transformation: [],
      supply_chain: [],
      commitment_level: [],
    };
    for (const kw of framework.keywords) out[kw.category].push(kw);
    return out;
  }, [framework]);

  async function onWeightChange(kw: SignalKeyword, weight: number) {
    if (!framework) return;
    setFramework({
      ...framework,
      keywords: framework.keywords.map((k) =>
        k.id === kw.id ? { ...k, weight } : k
      ),
    });
    try {
      await patchKeyword(framework.id, kw.id, { weight });
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  async function onAddKeyword(category: KeywordCategory, phrase: string) {
    if (!framework || !phrase.trim()) return;
    try {
      await addKeyword(framework.id, {
        category,
        phrase: phrase.trim(),
        weight: 5,
      });
      reload();
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  async function onDeleteKeyword(kw: SignalKeyword) {
    if (!framework) return;
    try {
      await deleteKeyword(framework.id, kw.id);
      setFramework({
        ...framework,
        keywords: framework.keywords.filter((k) => k.id !== kw.id),
      });
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  async function onDryRun() {
    if (!framework) return;
    setRunning(true);
    setErr(null);
    try {
      const result = await dryRunFramework(framework.id, dryRunText, 0.7);
      setDryRunResult(result);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setRunning(false);
    }
  }

  if (loading) {
    return (
      <p className="text-sm text-zinc-500 py-8 text-center">
        Loading framework...
      </p>
    );
  }

  if (!framework || !groups) {
    return (
      <p className="text-sm text-zinc-500 py-8 text-center">
        No framework found.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl md:text-2xl font-bold text-white">
          Signal Framework
        </h2>
        <p className="text-sm text-zinc-500 mt-1">
          The keyword library that drives the deterministic side of every score.
          Edit weights, add phrases, then dry-run on a snippet to see live hits.
        </p>
      </div>

      {/* Framework selector */}
      <div className="flex items-center gap-3">
        <span className="text-xs uppercase tracking-wider text-zinc-500">
          Active framework
        </span>
        <select
          value={framework.id}
          onChange={(e) => {
            const next = allFrameworks.find((f) => f.id === e.target.value);
            if (next) setFramework(next);
          }}
          className="rounded bg-zinc-900 border border-zinc-800 px-3 py-1.5 text-sm text-white focus:border-blue-500 focus:outline-none"
        >
          {allFrameworks.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name}
              {f.is_default ? " (default)" : ""}
            </option>
          ))}
        </select>
        <span className="text-xs text-zinc-500">
          {framework.keywords.length} keywords ·{" "}
          {framework.is_default ? "default" : "alternate"}
        </span>
      </div>

      {err && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
          {err}
        </div>
      )}

      {/* Three category columns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {CATEGORY_META.map((meta) => (
          <CategoryColumn
            key={meta.key}
            meta={meta}
            keywords={groups[meta.key]}
            onWeightChange={onWeightChange}
            onDelete={onDeleteKeyword}
            onAdd={(phrase) => onAddKeyword(meta.key, phrase)}
            hits={dryRunResult?.summary[meta.key] ?? 0}
          />
        ))}
      </div>

      {/* Dry-run panel */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4 space-y-3">
        <div className="flex justify-between items-baseline">
          <h3 className="text-sm font-semibold text-white">
            Dry-run on a snippet
          </h3>
          <span className="text-xs text-zinc-500">
            Pre-populated with a strong PLD-style example.
          </span>
        </div>
        <textarea
          value={dryRunText}
          onChange={(e) => setDryRunText(e.target.value)}
          rows={5}
          className="w-full rounded bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm font-mono text-zinc-100 focus:border-blue-500 focus:outline-none"
        />
        <button
          onClick={onDryRun}
          disabled={running}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50 transition-colors"
        >
          {running ? "Running..." : "Detect hits"}
        </button>

        {dryRunResult && (
          <div className="space-y-3 mt-4">
            <div className="grid grid-cols-3 gap-3">
              <Stat
                label="Total hits"
                value={dryRunResult.total_hits.toString()}
              />
              <Stat
                label="Keyword score"
                value={`${(dryRunResult.keyword_score * 100).toFixed(0)}%`}
              />
              <Stat
                label="Hybrid (LLM=70%)"
                value={`${(dryRunResult.hybrid_chunk_score * 100).toFixed(0)}%`}
              />
            </div>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {dryRunResult.hits.length === 0 && (
                <p className="text-xs text-zinc-500">No keyword matches.</p>
              )}
              {dryRunResult.hits.map((h, i) => (
                <div
                  key={i}
                  className="rounded border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs"
                >
                  <span className="inline-block px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 mr-2 uppercase tracking-wider text-[10px]">
                    {h.category.replace(/_/g, " ")}
                  </span>
                  <span className="font-mono text-white">
                    &quot;{h.match_text}&quot;
                  </span>
                  <span className="text-zinc-500 ml-2">
                    weight {h.weight_contribution.toFixed(1)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

interface ColMeta {
  key: KeywordCategory;
  title: string;
  blurb: string;
}

function CategoryColumn({
  meta,
  keywords,
  onWeightChange,
  onDelete,
  onAdd,
  hits,
}: {
  meta: ColMeta;
  keywords: SignalKeyword[];
  onWeightChange: (kw: SignalKeyword, weight: number) => void;
  onDelete: (kw: SignalKeyword) => void;
  onAdd: (phrase: string) => void;
  hits: number;
}) {
  const [newPhrase, setNewPhrase] = useState("");
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3 space-y-3">
      <div>
        <div className="flex justify-between items-baseline">
          <h3 className="text-sm font-semibold text-white">{meta.title}</h3>
          {hits > 0 && (
            <span className="text-xs text-blue-400">
              {hits} {hits === 1 ? "hit" : "hits"}
            </span>
          )}
        </div>
        <p className="text-xs text-zinc-500 mt-1">{meta.blurb}</p>
      </div>

      <div className="space-y-1.5 max-h-[480px] overflow-y-auto pr-1">
        {keywords.length === 0 && (
          <p className="text-xs text-zinc-600 italic">No keywords yet.</p>
        )}
        {keywords.map((kw) => (
          <KeywordRow
            key={kw.id}
            kw={kw}
            onWeightChange={(w) => onWeightChange(kw, w)}
            onDelete={() => onDelete(kw)}
          />
        ))}
      </div>

      <div className="flex gap-2 pt-2 border-t border-zinc-800">
        <input
          value={newPhrase}
          onChange={(e) => setNewPhrase(e.target.value)}
          placeholder="Add a phrase..."
          className="flex-1 rounded bg-zinc-900 border border-zinc-800 px-2 py-1.5 text-xs text-white focus:border-blue-500 focus:outline-none"
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              onAdd(newPhrase);
              setNewPhrase("");
            }
          }}
        />
        <button
          onClick={() => {
            onAdd(newPhrase);
            setNewPhrase("");
          }}
          className="rounded bg-zinc-800 px-2 py-1.5 text-xs text-zinc-300 hover:bg-zinc-700"
        >
          +
        </button>
      </div>
    </div>
  );
}

function KeywordRow({
  kw,
  onWeightChange,
  onDelete,
}: {
  kw: SignalKeyword;
  onWeightChange: (w: number) => void;
  onDelete: () => void;
}) {
  return (
    <div className="rounded bg-zinc-900 px-2 py-1.5 hover:bg-zinc-800 group">
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-xs text-zinc-200 truncate">
          {kw.phrase}
        </span>
        <button
          onClick={onDelete}
          className="text-zinc-600 hover:text-red-400 text-xs opacity-0 group-hover:opacity-100 transition"
          aria-label="Delete keyword"
        >
          ×
        </button>
      </div>
      <div className="flex items-center gap-2 mt-1">
        <input
          type="range"
          min={1}
          max={10}
          step={0.5}
          value={kw.weight}
          onChange={(e) => onWeightChange(parseFloat(e.target.value))}
          className="flex-1 accent-blue-500"
        />
        <span className="text-xs text-zinc-500 tabular-nums w-8 text-right">
          {kw.weight.toFixed(1)}
        </span>
      </div>
      {kw.companion_pattern && (
        <div className="text-[10px] text-amber-400/80 mt-0.5">
          requires nearby $ / sqft / date
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-zinc-900 border border-zinc-800 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-zinc-500">
        {label}
      </div>
      <div className="text-sm font-mono text-white mt-0.5">{value}</div>
    </div>
  );
}
