import type {
  CompanyScore,
  DemoChunkResult,
  DemoParseResult,
  DemoScoreResult,
  DemoTranscript,
  EnumValues,
  GeographySummary,
  SignalExtraction,
  Stats,
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
