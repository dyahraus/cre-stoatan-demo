"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  addKeyword,
  createFramework,
  deleteFramework,
  deleteKeyword,
  dryRunFramework,
  duplicateFramework,
  fetchFrameworks,
  patchFramework,
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
    const is404 = err?.includes("404");
    return (
      <div className="space-y-4 max-w-2xl">
        <h2 className="text-xl md:text-2xl font-bold text-white">
          Signal Framework
        </h2>
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-300 space-y-2">
          <p className="font-medium">Couldn&apos;t load any frameworks.</p>
          {err && <p className="text-xs font-mono text-amber-200/80">{err}</p>}
          {is404 && (
            <p className="text-xs">
              The backend doesn&apos;t expose <code>/api/frameworks</code> yet.
              On production this means Railway needs to redeploy off the latest
              commit. In dev, restart the FastAPI backend.
            </p>
          )}
          <button
            onClick={reload}
            className="mt-1 rounded bg-amber-500/20 hover:bg-amber-500/30 px-3 py-1 text-xs"
          >
            Retry
          </button>
        </div>
      </div>
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

      {/* Framework header bar */}
      <FrameworkHeader
        framework={framework}
        allFrameworks={allFrameworks}
        onSwitch={(id) => {
          const next = allFrameworks.find((f) => f.id === id);
          if (next) setFramework(next);
        }}
        onMutated={reload}
        onError={(m) => setErr(m)}
      />

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

function FrameworkHeader({
  framework,
  allFrameworks,
  onSwitch,
  onMutated,
  onError,
}: {
  framework: SignalFramework;
  allFrameworks: SignalFramework[];
  onSwitch: (id: string) => void;
  onMutated: () => void;
  onError: (msg: string) => void;
}) {
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(framework.name);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [copyKeywords, setCopyKeywords] = useState(false);
  const [busy, setBusy] = useState(false);
  const isOnly = allFrameworks.length === 1;

  // Sync rename buffer when active framework changes
  useEffect(() => {
    setName(framework.name);
    setRenaming(false);
  }, [framework.id, framework.name]);

  async function commitRename() {
    if (!name.trim() || name === framework.name) {
      setRenaming(false);
      setName(framework.name);
      return;
    }
    setBusy(true);
    try {
      await patchFramework(framework.id, { name: name.trim() });
      onMutated();
      setRenaming(false);
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function setAsDefault() {
    if (framework.is_default) return;
    setBusy(true);
    try {
      await patchFramework(framework.id, { is_default: true });
      onMutated();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onDuplicate() {
    const name = prompt(
      "Name for the duplicated framework:",
      `${framework.name} (copy)`
    );
    if (!name?.trim()) return;
    setBusy(true);
    try {
      const cloned = await duplicateFramework(framework.id, {
        name: name.trim(),
      });
      onMutated();
      onSwitch(cloned.id);
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onDelete() {
    if (isOnly) return;
    if (!confirm(`Delete framework "${framework.name}"? This can't be undone.`)) {
      return;
    }
    setBusy(true);
    try {
      await deleteFramework(framework.id);
      const remaining = allFrameworks.filter((f) => f.id !== framework.id);
      const next = remaining.find((f) => f.is_default) ?? remaining[0];
      if (next) onSwitch(next.id);
      onMutated();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onCreate() {
    if (!newName.trim()) return;
    setBusy(true);
    try {
      const fw = copyKeywords
        ? await duplicateFramework(framework.id, { name: newName.trim() })
        : await createFramework({ name: newName.trim() });
      onMutated();
      onSwitch(fw.id);
      setCreating(false);
      setNewName("");
      setCopyKeywords(false);
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-3 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={framework.id}
          onChange={(e) => onSwitch(e.target.value)}
          disabled={busy}
          className="rounded bg-zinc-900 border border-zinc-800 px-3 py-1.5 text-sm text-white focus:border-blue-500 focus:outline-none disabled:opacity-50"
        >
          {allFrameworks.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name}
              {f.is_default ? " · default" : ""}
            </option>
          ))}
        </select>

        {renaming ? (
          <div className="flex items-center gap-1">
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              onBlur={commitRename}
              onKeyDown={(e) => {
                if (e.key === "Enter") commitRename();
                if (e.key === "Escape") {
                  setRenaming(false);
                  setName(framework.name);
                }
              }}
              className="rounded bg-zinc-900 border border-blue-500 px-2 py-1.5 text-sm text-white focus:outline-none"
            />
          </div>
        ) : (
          <button
            onClick={() => setRenaming(true)}
            disabled={busy}
            className="text-xs text-zinc-400 hover:text-zinc-200 px-2 py-1 rounded hover:bg-zinc-800 transition disabled:opacity-50"
            title="Rename framework"
          >
            ✎ rename
          </button>
        )}

        <button
          onClick={() => setCreating((v) => !v)}
          disabled={busy}
          className="rounded bg-blue-600 hover:bg-blue-500 text-white text-xs px-2.5 py-1.5 disabled:opacity-50"
        >
          + New framework
        </button>
        <button
          onClick={onDuplicate}
          disabled={busy}
          className="rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs px-2.5 py-1.5 disabled:opacity-50"
        >
          Duplicate
        </button>
        {!framework.is_default && (
          <button
            onClick={setAsDefault}
            disabled={busy}
            className="rounded border border-zinc-700 hover:border-emerald-500/50 text-zinc-300 hover:text-emerald-300 text-xs px-2.5 py-1.5 disabled:opacity-50"
          >
            Set as default
          </button>
        )}
        <button
          onClick={onDelete}
          disabled={busy || isOnly}
          title={
            isOnly
              ? "Can't delete the only framework"
              : "Delete this framework"
          }
          className="rounded border border-red-500/30 text-red-400 hover:bg-red-500/10 text-xs px-2.5 py-1.5 disabled:opacity-30 disabled:cursor-not-allowed ml-auto"
        >
          Delete
        </button>
      </div>

      <div className="text-xs text-zinc-500">
        {framework.keywords.length} keywords ·{" "}
        {framework.is_default ? "default framework" : "alternate framework"} ·
        updated {new Date(framework.updated_at).toLocaleDateString()}
        {framework.description && (
          <span className="ml-2 italic">— {framework.description}</span>
        )}
      </div>

      {creating && (
        <div className="rounded border border-blue-500/30 bg-blue-500/5 p-3 space-y-2">
          <div className="flex items-center gap-2">
            <input
              autoFocus
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Framework name (e.g. 'REIT-tuned v1')"
              className="flex-1 rounded bg-zinc-900 border border-zinc-800 px-3 py-1.5 text-sm text-white focus:border-blue-500 focus:outline-none"
              onKeyDown={(e) => {
                if (e.key === "Enter") onCreate();
              }}
            />
            <label className="flex items-center gap-1.5 text-xs text-zinc-400 cursor-pointer">
              <input
                type="checkbox"
                checked={copyKeywords}
                onChange={(e) => setCopyKeywords(e.target.checked)}
              />
              Copy current keywords
            </label>
            <button
              onClick={onCreate}
              disabled={busy || !newName.trim()}
              className="rounded bg-blue-600 hover:bg-blue-500 text-white text-xs px-3 py-1.5 disabled:opacity-50"
            >
              Create
            </button>
            <button
              onClick={() => {
                setCreating(false);
                setNewName("");
                setCopyKeywords(false);
              }}
              className="text-xs text-zinc-500 hover:text-zinc-300 px-2"
            >
              Cancel
            </button>
          </div>
          <p className="text-[11px] text-zinc-500">
            {copyKeywords
              ? "Will clone every keyword + weight from the current framework."
              : "Will start blank. Add keywords manually or import a CSV."}
          </p>
        </div>
      )}
    </div>
  );
}
