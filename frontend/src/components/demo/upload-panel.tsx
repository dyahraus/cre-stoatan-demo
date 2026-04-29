"use client";

import { useEffect, useRef, useState } from "react";
import { fetchEnums, uploadTranscript } from "@/lib/api";
import type { DemoTranscript, EnumValues } from "@/lib/types";

type Mode = "sample" | "paste" | "file";

interface Props {
  /** Cached sample transcripts (the existing 3 PLD/WMT/HD demos). */
  samples: DemoTranscript[];
  /** Currently-selected transcript (sample or upload). */
  selected: DemoTranscript | null;
  /** Called when the user selects a sample or finishes an upload. */
  onSelectTranscript: (t: DemoTranscript) => void;
}

export function UploadPanel({ samples, selected, onSelectTranscript }: Props) {
  const [mode, setMode] = useState<Mode>("sample");
  const [enums, setEnums] = useState<EnumValues | null>(null);
  const [ticker, setTicker] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [year, setYear] = useState(new Date().getFullYear());
  const [quarter, setQuarter] = useState(1);
  const [sector, setSector] = useState("retail");
  const [pasted, setPasted] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    fetchEnums()
      .then(setEnums)
      .catch(() => {});
  }, []);

  async function handleSubmit() {
    setErr(null);
    if (!ticker.trim() || !companyName.trim()) {
      setErr("Ticker and company name are required.");
      return;
    }
    if (mode === "paste" && pasted.trim().length < 100) {
      setErr("Paste at least a few sentences of transcript text.");
      return;
    }
    if (mode === "file" && !file) {
      setErr("Pick a .txt or .pdf file first.");
      return;
    }
    setBusy(true);
    try {
      const resp = await uploadTranscript({
        ticker: ticker.trim().toUpperCase(),
        company_name: companyName.trim(),
        year,
        quarter,
        sector,
        raw_text: mode === "paste" ? pasted : undefined,
        file: mode === "file" ? file : undefined,
      });
      onSelectTranscript({
        ticker: resp.ticker,
        company_name: companyName.trim(),
        year: resp.year,
        quarter: resp.quarter,
        quarter_key: resp.quarter_key,
        raw_text_length: resp.raw_text_length,
        call_date: null,
      });
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Mode tabs */}
      <div className="flex gap-2 border-b border-zinc-800">
        {([
          ["sample", "Pick a sample"],
          ["paste", "Paste text"],
          ["file", "Upload file"],
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

      {mode === "sample" && (
        <div className="space-y-2">
          {samples.length === 0 && (
            <p className="text-sm text-zinc-500">Loading sample transcripts...</p>
          )}
          {samples.map((t) => {
            const active = selected?.quarter_key === t.quarter_key;
            return (
              <button
                key={t.quarter_key}
                onClick={() => onSelectTranscript(t)}
                className={`w-full text-left rounded-lg border p-3 transition-colors ${
                  active
                    ? "border-blue-500 bg-blue-500/10"
                    : "border-zinc-800 bg-zinc-900 hover:border-zinc-700"
                }`}
              >
                <div className="flex justify-between items-baseline">
                  <span className="font-mono text-sm font-medium text-white">
                    {t.ticker}
                  </span>
                  <span className="text-xs text-zinc-500">
                    {t.year} Q{t.quarter}
                  </span>
                </div>
                <div className="text-xs text-zinc-400 mt-1">
                  {t.company_name} · {t.raw_text_length.toLocaleString()} chars
                </div>
              </button>
            );
          })}
        </div>
      )}

      {(mode === "paste" || mode === "file") && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Ticker">
              <input
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                placeholder="ACME"
                maxLength={8}
                className="w-full rounded bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm font-mono text-white focus:border-blue-500 focus:outline-none"
              />
            </Field>
            <Field label="Company name">
              <input
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="Acme Corp"
                className="w-full rounded bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
              />
            </Field>
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
          </div>
          <Field label="Sector">
            <select
              value={sector}
              onChange={(e) => setSector(e.target.value)}
              className="w-full rounded bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
            >
              {(enums?.sectors ?? ["retail", "other"]).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>

          {mode === "paste" && (
            <Field label="Transcript text">
              <textarea
                value={pasted}
                onChange={(e) => setPasted(e.target.value)}
                placeholder="Paste the prepared remarks and/or Q&A here..."
                rows={10}
                className="w-full rounded bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm font-mono text-white focus:border-blue-500 focus:outline-none"
              />
              <p className="text-xs text-zinc-500 mt-1">
                {pasted.length.toLocaleString()} characters · 200KB max
              </p>
            </Field>
          )}

          {mode === "file" && (
            <Field label="Upload .txt or .pdf">
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,.pdf,text/plain,application/pdf"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="block w-full text-sm text-zinc-400 file:mr-3 file:rounded file:border-0 file:bg-blue-600 file:px-3 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-blue-500"
              />
              {file && (
                <p className="text-xs text-zinc-500 mt-1">
                  {file.name} · {(file.size / 1024).toFixed(1)} KB
                </p>
              )}
              <p className="text-xs text-zinc-500 mt-1">
                Scanned (image-only) PDFs aren&apos;t supported in v1.
              </p>
            </Field>
          )}

          {err && (
            <div className="rounded border border-red-500/30 bg-red-500/10 p-2 text-xs text-red-400">
              {err}
            </div>
          )}

          <button
            onClick={handleSubmit}
            disabled={busy}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50 transition-colors"
          >
            {busy ? "Uploading..." : "Upload + chunk"}
          </button>
          {selected && selected.quarter_key.startsWith(ticker) && (
            <p className="text-xs text-emerald-400">
              Uploaded as{" "}
              <span className="font-mono">{selected.quarter_key}</span>. Click
              &quot;Parse Sections&quot; below to continue.
            </p>
          )}
        </div>
      )}
    </div>
  );
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
