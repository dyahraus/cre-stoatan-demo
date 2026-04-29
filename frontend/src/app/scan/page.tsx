"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  createWatchlist,
  deleteWatchlist,
  fetchEnums,
  fetchFrameworks,
  fetchWatchlists,
  startScan,
  streamScanProgress,
} from "@/lib/api";
import type {
  EnumValues,
  ScanJob,
  ScanProgressEvent,
  SignalFramework,
  SignalTier,
  Watchlist,
} from "@/lib/types";
import { TierBadge } from "@/components/shared/tier-badge";

type Mode = "sector" | "tickers" | "watchlist";

interface ResultRow {
  ticker: string;
  quarter_key: string;
  composite: number;
  tier: SignalTier;
}

export default function ScanPage() {
  const [mode, setMode] = useState<Mode>("sector");
  const [enums, setEnums] = useState<EnumValues | null>(null);

  // Form state
  const [year, setYear] = useState(new Date().getFullYear() - 1);
  const [quarter, setQuarter] = useState(3);
  const [sectors, setSectors] = useState<string[]>(["retail"]);
  const [maxCompanies, setMaxCompanies] = useState(10);
  const [tickerText, setTickerText] = useState("PLD\nWMT\nHD");
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [watchlistId, setWatchlistId] = useState<string>("");
  const [frameworks, setFrameworks] = useState<SignalFramework[]>([]);
  const [frameworkId, setFrameworkId] = useState<string>("");

  // Run state
  const [running, setRunning] = useState(false);
  const [job, setJob] = useState<ScanJob | null>(null);
  const [events, setEvents] = useState<ScanProgressEvent[]>([]);
  const [results, setResults] = useState<ResultRow[]>([]);
  const [skipped, setSkipped] = useState<{ ticker: string; reason: string }[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    fetchEnums()
      .then(setEnums)
      .catch(() => {});
    fetchWatchlists()
      .then(setWatchlists)
      .catch(() => {});
    fetchFrameworks()
      .then((fws) => {
        setFrameworks(fws);
        const def = fws.find((f) => f.is_default) ?? fws[0];
        if (def) setFrameworkId(def.id);
      })
      .catch(() => {});
    return () => abortRef.current?.abort();
  }, []);

  const reloadWatchlists = useCallback(() => {
    fetchWatchlists()
      .then(setWatchlists)
      .catch(() => {});
  }, []);

  async function onStart() {
    setErr(null);
    setEvents([]);
    setResults([]);
    setSkipped([]);
    let payload: Record<string, unknown>;
    if (mode === "sector") {
      if (sectors.length === 0) {
        setErr("Pick at least one sector.");
        return;
      }
      payload = {
        mode: "sector",
        sectors,
        year,
        quarter,
        max_companies: Math.min(maxCompanies, 25),
      };
    } else if (mode === "tickers") {
      const list = tickerText
        .split(/[\s,]+/)
        .map((t) => t.trim().toUpperCase())
        .filter(Boolean);
      if (list.length === 0) {
        setErr("Enter at least one ticker.");
        return;
      }
      payload = { mode: "tickers", tickers: list, year, quarter };
    } else {
      if (!watchlistId) {
        setErr("Pick a watchlist.");
        return;
      }
      payload = { mode: "watchlist", watchlist_id: watchlistId, year, quarter };
    }
    if (frameworkId) payload.framework_id = frameworkId;

    setRunning(true);
    try {
      const { job_id } = await startScan(payload);
      setJob({
        id: job_id,
        status: "running",
        params: payload as ScanJob["params"],
        progress: { events: [] },
        results_summary: {},
        started_at: null,
        finished_at: null,
        error: null,
        created_at: new Date().toISOString(),
      });
      const controller = streamScanProgress(
        job_id,
        (e) => {
          setEvents((prev) => [...prev, e]);
          if (e.type === "scored") {
            setResults((prev) => [
              ...prev,
              {
                ticker: e.ticker,
                quarter_key: e.quarter_key,
                composite: e.composite,
                tier: e.tier,
              },
            ]);
          }
          if (e.type === "skip") {
            setSkipped((prev) => [...prev, { ticker: e.ticker, reason: e.reason }]);
          }
          if (e.type === "done") {
            setRunning(false);
          }
          if (e.type === "error") {
            setErr(e.message);
            setRunning(false);
          }
        },
        (msg) => {
          setErr(msg);
          setRunning(false);
        }
      );
      abortRef.current = controller;
    } catch (e) {
      setErr((e as Error).message);
      setRunning(false);
    }
  }

  async function onSaveWatchlist() {
    const list = tickerText
      .split(/[\s,]+/)
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean);
    if (list.length === 0) return;
    const name = prompt("Watchlist name:");
    if (!name) return;
    try {
      await createWatchlist(name, list);
      reloadWatchlists();
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h2 className="text-xl md:text-2xl font-bold text-white">Run a Scan</h2>
        <p className="text-sm text-zinc-500 mt-1">
          Pick a slice of the universe, fetch + score every matching transcript,
          watch progress live. Hard cap of 25 companies per scan.
        </p>
      </div>

      {/* Mode tabs */}
      <div className="flex gap-2 border-b border-zinc-800">
        {([
          ["sector", "By sector"],
          ["tickers", "By ticker list"],
          ["watchlist", "From watchlist"],
        ] as const).map(([m, label]) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`px-3 py-2 text-sm border-b-2 -mb-px transition-colors ${
              mode === m
                ? "border-blue-500 text-white"
                : "border-transparent text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Form */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Field label="Year">
          <input
            type="number"
            value={year}
            onChange={(e) => setYear(parseInt(e.target.value) || year)}
            className="w-full rounded bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
          />
        </Field>
        <Field label="Quarter">
          <select
            value={quarter}
            onChange={(e) => setQuarter(parseInt(e.target.value))}
            className="w-full rounded bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
          >
            {[1, 2, 3, 4].map((q) => (
              <option key={q} value={q}>
                Q{q}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Framework">
          <select
            value={frameworkId}
            onChange={(e) => setFrameworkId(e.target.value)}
            disabled={frameworks.length === 0}
            className="w-full rounded bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none disabled:opacity-50"
          >
            {frameworks.length === 0 && <option value="">— loading —</option>}
            {frameworks.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
                {f.is_default ? " · default" : ""} · {f.keywords.length} kw
              </option>
            ))}
          </select>
        </Field>
        {mode === "sector" && (
          <Field label="Max companies (≤25)">
            <input
              type="number"
              min={1}
              max={25}
              value={maxCompanies}
              onChange={(e) =>
                setMaxCompanies(
                  Math.min(25, Math.max(1, parseInt(e.target.value) || 1))
                )
              }
              className="w-full rounded bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
            />
          </Field>
        )}
      </div>

      {mode === "sector" && (
        <Field label="Sectors">
          <div className="flex gap-2 flex-wrap">
            {(enums?.sectors ?? []).map((s) => {
              const active = sectors.includes(s);
              return (
                <button
                  key={s}
                  onClick={() =>
                    setSectors((prev) =>
                      prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]
                    )
                  }
                  className={`px-3 py-1 rounded text-xs border transition-colors ${
                    active
                      ? "border-blue-500 bg-blue-500/15 text-blue-300"
                      : "border-zinc-800 bg-zinc-900 text-zinc-400 hover:border-zinc-700"
                  }`}
                >
                  {s}
                </button>
              );
            })}
          </div>
        </Field>
      )}

      {mode === "tickers" && (
        <div className="space-y-2">
          <Field label="Tickers (one per line or comma-separated)">
            <textarea
              value={tickerText}
              onChange={(e) => setTickerText(e.target.value)}
              rows={5}
              className="w-full rounded bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm font-mono text-white focus:border-blue-500 focus:outline-none"
            />
          </Field>
          <button
            onClick={onSaveWatchlist}
            className="text-xs text-blue-400 hover:text-blue-300"
          >
            + Save as watchlist
          </button>
        </div>
      )}

      {mode === "watchlist" && (
        <Field label="Watchlist">
          {watchlists.length === 0 ? (
            <p className="text-xs text-zinc-500">
              No watchlists yet. Create one from the &ldquo;By ticker list&rdquo;
              tab.
            </p>
          ) : (
            <div className="space-y-2">
              <select
                value={watchlistId}
                onChange={(e) => setWatchlistId(e.target.value)}
                className="w-full rounded bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
              >
                <option value="">— pick one —</option>
                {watchlists.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name} ({w.tickers.length})
                  </option>
                ))}
              </select>
              {watchlistId && (
                <div className="flex items-center justify-between text-xs text-zinc-500">
                  <span className="font-mono">
                    {watchlists.find((w) => w.id === watchlistId)?.tickers.join(", ")}
                  </span>
                  <button
                    onClick={async () => {
                      await deleteWatchlist(watchlistId);
                      setWatchlistId("");
                      reloadWatchlists();
                    }}
                    className="text-red-400 hover:text-red-300"
                  >
                    delete
                  </button>
                </div>
              )}
            </div>
          )}
        </Field>
      )}

      {err && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
          {err}
        </div>
      )}

      <button
        onClick={onStart}
        disabled={running}
        className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50 transition-colors"
      >
        {running ? "Running scan..." : "Start scan"}
      </button>

      {/* Progress feed */}
      {(events.length > 0 || job) && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4 space-y-3">
          <div className="flex justify-between items-baseline">
            <h3 className="text-sm font-semibold text-white">Progress</h3>
            <span className="text-xs text-zinc-500 font-mono">
              {results.length} scored · {skipped.length} skipped
            </span>
          </div>
          <div className="max-h-60 overflow-y-auto space-y-1 font-mono text-xs">
            {events.map((e, i) => (
              <ProgressLine key={i} event={e} />
            ))}
            {events.length === 0 && (
              <p className="text-zinc-600">Waiting for events...</p>
            )}
          </div>
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4 space-y-2">
          <h3 className="text-sm font-semibold text-white">Results</h3>
          <div className="space-y-1">
            {[...results]
              .sort((a, b) => b.composite - a.composite)
              .map((r) => (
                <Link
                  key={r.quarter_key}
                  href={`/company/${r.ticker}`}
                  className="flex items-center justify-between gap-3 rounded bg-zinc-900 px-3 py-2 text-sm hover:bg-zinc-800 transition-colors"
                >
                  <span className="font-mono font-semibold text-blue-400 w-16">
                    {r.ticker}
                  </span>
                  <TierBadge tier={r.tier} size="sm" />
                  <span className="font-mono text-zinc-200 tabular-nums w-16 text-right">
                    {(r.composite * 100).toFixed(0)}%
                  </span>
                  <span className="text-zinc-500 text-xs flex-1 text-right">
                    {r.quarter_key} →
                  </span>
                </Link>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ProgressLine({ event }: { event: ScanProgressEvent }) {
  if (event.type === "started") {
    return (
      <div className="text-zinc-500">started — total {event.total} tickers</div>
    );
  }
  if (event.type === "progress") {
    return (
      <div className="text-zinc-400">
        <span className="text-zinc-500">[{event.phase}]</span> {event.ticker}
      </div>
    );
  }
  if (event.type === "scored") {
    return (
      <div className="text-emerald-400">
        ✓ {event.ticker} — {event.tier} ({(event.composite * 100).toFixed(0)}%)
      </div>
    );
  }
  if (event.type === "skip") {
    return (
      <div className="text-amber-400">
        ⊘ {event.ticker} — {event.reason}
      </div>
    );
  }
  if (event.type === "warn") {
    return (
      <div className="text-amber-300">⚠ {event.ticker} — {event.message}</div>
    );
  }
  if (event.type === "error") {
    return <div className="text-red-400">✗ {event.message}</div>;
  }
  if (event.type === "done") {
    return (
      <div className="text-zinc-500">
        done — {event.scored ?? 0} scored, {event.skipped ?? 0} skipped
      </div>
    );
  }
  return null;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-xs uppercase tracking-wider text-zinc-500 mb-1">
        {label}
      </span>
      {children}
    </label>
  );
}
