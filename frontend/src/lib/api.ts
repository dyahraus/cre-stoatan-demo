import type {
  BoostConfig,
  CompanyHistoryEntry,
  CompanyScore,
  ConceptMode,
  DemoChunkResult,
  DemoParseResult,
  DemoScoreResult,
  DemoTranscript,
  DryRunResult,
  EnumValues,
  GeographySummary,
  KeywordCategory,
  ScanJob,
  ScanProgressEvent,
  SignalConcept,
  SignalExtraction,
  SignalFramework,
  Stats,
  TranscriptScore,
  UploadResponse,
  Watchlist,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL}/api`
  : "/api";

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export interface ScoreFilters {
  min_score?: number;
  sector?: string;
  geography?: string;
  move_type?: string;
  time_horizon?: string;
  top_n?: number;
}

export async function fetchScores(
  params?: ScoreFilters
): Promise<CompanyScore[]> {
  const sp = new URLSearchParams();
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "") {
        sp.set(k, String(v));
      }
    }
  }
  const qs = sp.toString();
  return fetchJSON<CompanyScore[]>(`/scores${qs ? `?${qs}` : ""}`);
}

export async function fetchCompanyScore(
  ticker: string
): Promise<CompanyScore> {
  return fetchJSON<CompanyScore>(`/scores/${ticker}`);
}

export async function fetchExtractions(
  ticker: string
): Promise<SignalExtraction[]> {
  return fetchJSON<SignalExtraction[]>(`/scores/${ticker}/extractions`);
}

export async function fetchGeographies(): Promise<GeographySummary[]> {
  return fetchJSON<GeographySummary[]>("/geographies");
}

export async function fetchStats(): Promise<Stats> {
  return fetchJSON<Stats>("/stats");
}

export async function fetchEnums(): Promise<EnumValues> {
  return fetchJSON<EnumValues>("/enums");
}

// Demo pipeline API

export async function fetchDemoTranscripts(): Promise<DemoTranscript[]> {
  return fetchJSON<DemoTranscript[]>("/demo/transcripts");
}

export async function fetchDemoParse(
  quarterKey: string
): Promise<DemoParseResult> {
  return fetchJSON<DemoParseResult>(`/demo/parse?quarter_key=${quarterKey}`);
}

export async function fetchDemoChunks(
  quarterKey: string
): Promise<DemoChunkResult> {
  return fetchJSON<DemoChunkResult>(`/demo/chunks?quarter_key=${quarterKey}`);
}

export async function fetchDemoScore(
  quarterKey: string,
  extractions: object[]
): Promise<DemoScoreResult> {
  const res = await fetch(`${BASE}/demo/score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ quarter_key: quarterKey, extractions }),
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<DemoScoreResult>;
}

export interface StreamCallbacks {
  onChunkInfo?: (info: {
    chunk_index: number;
    section_type: string;
    token_estimate: number;
  }) => void;
  onPrompt?: (prompt: { system: string; user_preview: string }) => void;
  onToken?: (text: string) => void;
  onExtraction?: (data: object) => void;
  onDone?: () => void;
  onError?: (msg: string) => void;
}

export function streamDemoExtraction(
  quarterKey: string,
  chunkIndex: number,
  callbacks: StreamCallbacks
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(
        `${BASE}/demo/extract/stream?quarter_key=${quarterKey}&chunk_index=${chunkIndex}`,
        { signal: controller.signal }
      );
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const parts = buffer.split("\n\n");
        buffer = parts.pop()!;

        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data: ")) continue;
          try {
            const payload = JSON.parse(line.slice(6));
            switch (payload.type) {
              case "chunk_info":
                callbacks.onChunkInfo?.(payload);
                break;
              case "prompt":
                callbacks.onPrompt?.(payload);
                break;
              case "token":
                callbacks.onToken?.(payload.text);
                break;
              case "extraction":
                callbacks.onExtraction?.(payload.data);
                break;
              case "done":
                callbacks.onDone?.();
                break;
              case "error":
                callbacks.onError?.(payload.message);
                break;
            }
          } catch {
            // skip malformed SSE lines
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        callbacks.onError?.((err as Error).message);
      }
    }
  })();

  return controller;
}

// ---------------------------------------------------------------------------
// Frameworks (Phase 1A)
// ---------------------------------------------------------------------------

export async function fetchFrameworks(): Promise<SignalFramework[]> {
  return fetchJSON<SignalFramework[]>("/frameworks");
}

export async function fetchFramework(id: string): Promise<SignalFramework> {
  return fetchJSON<SignalFramework>(`/frameworks/${id}`);
}

export async function createFramework(
  body: { name: string; description?: string; is_default?: boolean }
): Promise<SignalFramework> {
  const res = await fetch(`${BASE}/frameworks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function patchFramework(
  id: string,
  body: Partial<{
    name: string;
    description: string;
    is_default: boolean;
    boosts: BoostConfig;
  }>
): Promise<SignalFramework> {
  const res = await fetch(`${BASE}/frameworks/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function deleteFramework(id: string): Promise<void> {
  const res = await fetch(`${BASE}/frameworks/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error(await readError(res));
}

export async function duplicateFramework(
  sourceId: string,
  body: { name: string; description?: string; is_default?: boolean }
): Promise<SignalFramework> {
  const res = await fetch(`${BASE}/frameworks/${sourceId}/duplicate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

async function readError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return `API ${res.status}: ${data.detail}`;
  } catch {
    // fall through
  }
  return `API error ${res.status}`;
}

export interface ImportResult {
  framework_id: string;
  imported: number;
  skipped: number;
  errors: { line: number; reason: string }[];
}

export async function importKeywordsCSV(
  frameworkId: string,
  file: File
): Promise<ImportResult> {
  const form = new FormData();
  form.set("file", file);
  const res = await fetch(
    `${BASE}/frameworks/${frameworkId}/keywords/import`,
    { method: "POST", body: form }
  );
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export function frameworkTemplateUrl(): string {
  return `${BASE}/frameworks/template.csv`;
}

// ---------------------------------------------------------------------------
// Concepts (Phase 6D)
// ---------------------------------------------------------------------------

export async function addConcept(
  frameworkId: string,
  body: {
    category: KeywordCategory;
    label: string;
    description?: string;
    example_phrases?: string[];
    weight?: number;
    threshold?: number;
    mode?: ConceptMode;
  }
): Promise<SignalConcept> {
  const res = await fetch(`${BASE}/frameworks/${frameworkId}/concepts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function patchConcept(
  frameworkId: string,
  conceptId: string,
  body: Partial<{
    category: KeywordCategory;
    label: string;
    description: string;
    example_phrases: string[];
    weight: number;
    threshold: number;
    mode: ConceptMode;
  }>
): Promise<SignalConcept> {
  const res = await fetch(
    `${BASE}/frameworks/${frameworkId}/concepts/${conceptId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }
  );
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function deleteConcept(
  frameworkId: string,
  conceptId: string
): Promise<void> {
  const res = await fetch(
    `${BASE}/frameworks/${frameworkId}/concepts/${conceptId}`,
    { method: "DELETE" }
  );
  if (!res.ok && res.status !== 204) throw new Error(await readError(res));
}

export async function patchKeyword(
  frameworkId: string,
  keywordId: string,
  body: Partial<{
    category: string;
    phrase: string;
    is_regex: boolean;
    weight: number;
    companion_pattern: string | null;
    notes: string;
  }>
): Promise<unknown> {
  const res = await fetch(
    `${BASE}/frameworks/${frameworkId}/keywords/${keywordId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }
  );
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function addKeyword(
  frameworkId: string,
  body: {
    category: string;
    phrase: string;
    weight?: number;
    is_regex?: boolean;
    companion_pattern?: string | null;
  }
): Promise<unknown> {
  const res = await fetch(`${BASE}/frameworks/${frameworkId}/keywords`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function deleteKeyword(
  frameworkId: string,
  keywordId: string
): Promise<void> {
  const res = await fetch(
    `${BASE}/frameworks/${frameworkId}/keywords/${keywordId}`,
    { method: "DELETE" }
  );
  if (!res.ok && res.status !== 204) throw new Error(`API error ${res.status}`);
}

export async function dryRunFramework(
  frameworkId: string,
  text: string,
  llmExpansionScore = 0.0
): Promise<DryRunResult> {
  const res = await fetch(`${BASE}/frameworks/${frameworkId}/dry-run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text,
      llm_expansion_score: llmExpansionScore,
    }),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Upload (Phase 1B)
// ---------------------------------------------------------------------------

export async function uploadTranscript(
  data: {
    ticker: string;
    company_name: string;
    year: number;
    quarter: number;
    sector: string;
    raw_text?: string;
    file?: File | null;
  }
): Promise<UploadResponse> {
  const form = new FormData();
  form.set("ticker", data.ticker);
  form.set("company_name", data.company_name);
  form.set("year", String(data.year));
  form.set("quarter", String(data.quarter));
  form.set("sector", data.sector);
  if (data.raw_text) form.set("raw_text", data.raw_text);
  if (data.file) form.set("file", data.file);

  const res = await fetch(`${BASE}/transcripts/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `Upload failed (${res.status})`);
  }
  return res.json();
}

export async function refreshTranscriptScore(
  quarterKey: string,
  body: {
    framework_id?: string;
    run_keyword_engine?: boolean;
    run_llm?: boolean;
  } = {}
): Promise<TranscriptScore> {
  const res = await fetch(`${BASE}/transcripts/${quarterKey}/score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `API error ${res.status}`);
  }
  return res.json();
}

export async function fetchTranscriptScore(
  quarterKey: string
): Promise<TranscriptScore> {
  return fetchJSON<TranscriptScore>(`/transcripts/${quarterKey}/score`);
}

export async function fetchCompanyHistory(
  ticker: string
): Promise<CompanyHistoryEntry[]> {
  return fetchJSON<CompanyHistoryEntry[]>(`/companies/${ticker}/history`);
}

// ---------------------------------------------------------------------------
// Watchlists (Phase 3)
// ---------------------------------------------------------------------------

export async function fetchWatchlists(): Promise<Watchlist[]> {
  return fetchJSON<Watchlist[]>("/watchlists");
}

export async function createWatchlist(
  name: string,
  tickers: string[]
): Promise<Watchlist> {
  const res = await fetch(`${BASE}/watchlists`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, tickers }),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.json();
}

export async function deleteWatchlist(id: string): Promise<void> {
  const res = await fetch(`${BASE}/watchlists/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error(`API error ${res.status}`);
}

// ---------------------------------------------------------------------------
// Scans (Phase 3)
// ---------------------------------------------------------------------------

export async function startScan(
  payload: Record<string, unknown>
): Promise<{ job_id: string; ticker_count: number }> {
  const res = await fetch(`${BASE}/scans`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `API error ${res.status}`);
  }
  return res.json();
}

export async function fetchScan(id: string): Promise<ScanJob> {
  return fetchJSON<ScanJob>(`/scans/${id}`);
}

export async function fetchScans(): Promise<ScanJob[]> {
  return fetchJSON<ScanJob[]>("/scans");
}

export function streamScanProgress(
  jobId: string,
  onEvent: (e: ScanProgressEvent) => void,
  onError?: (msg: string) => void
): AbortController {
  const controller = new AbortController();
  (async () => {
    try {
      const res = await fetch(`${BASE}/scans/${jobId}/stream`, {
        signal: controller.signal,
      });
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop()!;
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data: ")) continue;
          try {
            const payload = JSON.parse(line.slice(6)) as ScanProgressEvent;
            onEvent(payload);
            if (payload.type === "done") return;
          } catch {
            // skip malformed
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        onError?.((err as Error).message);
      }
    }
  })();
  return controller;
}
