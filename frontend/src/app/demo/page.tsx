"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchDemoTranscripts,
  fetchDemoParse,
  fetchDemoChunks,
  fetchDemoScore,
  streamDemoExtraction,
} from "@/lib/api";
import type {
  DemoTranscript,
  DemoParseResult,
  DemoChunkResult,
  DemoScoreResult,
} from "@/lib/types";
import { StepCard } from "@/components/demo/step-card";
import { TranscriptSelector } from "@/components/demo/transcript-selector";
import { ParseDisplay } from "@/components/demo/parse-display";
import { ChunkDisplay } from "@/components/demo/chunk-display";
import { ExtractionStream } from "@/components/demo/extraction-stream";
import { ScoreDisplay } from "@/components/demo/score-display";

type DemoStep = "select" | "parse" | "chunk" | "extract" | "score";
const STEPS: DemoStep[] = ["select", "parse", "chunk", "extract", "score"];

function stepStatus(
  step: DemoStep,
  current: DemoStep
): "locked" | "active" | "completed" {
  const ci = STEPS.indexOf(current);
  const si = STEPS.indexOf(step);
  if (si < ci) return "completed";
  if (si === ci) return "active";
  return "locked";
}

export default function DemoPage() {
  // Data state
  const [transcripts, setTranscripts] = useState<DemoTranscript[]>([]);
  const [selected, setSelected] = useState<DemoTranscript | null>(null);
  const [parseResult, setParseResult] = useState<DemoParseResult | null>(null);
  const [chunkResult, setChunkResult] = useState<DemoChunkResult | null>(null);
  const [selectedChunkIndices, setSelectedChunkIndices] = useState<number[]>(
    []
  );
  const [streamText, setStreamText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [extractions, setExtractions] = useState<Record<string, unknown>[]>([]);
  const [promptPreview, setPromptPreview] = useState<string | null>(null);
  const [currentChunkLabel, setCurrentChunkLabel] = useState<string>("");
  const [scoreResult, setScoreResult] = useState<DemoScoreResult | null>(null);

  // UI state
  const [step, setStep] = useState<DemoStep>("select");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Load transcripts on mount
  useEffect(() => {
    setLoading(true);
    fetchDemoTranscripts()
      .then(setTranscripts)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  // Cleanup stream on unmount
  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const resetFrom = useCallback((fromStep: DemoStep) => {
    const idx = STEPS.indexOf(fromStep);
    if (idx <= 1) setParseResult(null);
    if (idx <= 2) {
      setChunkResult(null);
      setSelectedChunkIndices([]);
    }
    if (idx <= 3) {
      setStreamText("");
      setIsStreaming(false);
      setExtractions([]);
      setPromptPreview(null);
      setCurrentChunkLabel("");
      abortRef.current?.abort();
    }
    if (idx <= 4) setScoreResult(null);
    setError(null);
  }, []);

  const handleSelectTranscript = useCallback(
    (t: DemoTranscript) => {
      if (selected?.quarter_key !== t.quarter_key) {
        resetFrom("parse");
      }
      setSelected(t);
    },
    [selected, resetFrom]
  );

  const handleParse = useCallback(async () => {
    if (!selected) return;
    resetFrom("parse");
    setLoading(true);
    try {
      const result = await fetchDemoParse(selected.quarter_key);
      setParseResult(result);
      setStep("parse");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [selected, resetFrom]);

  const handleChunk = useCallback(async () => {
    if (!selected) return;
    resetFrom("chunk");
    setLoading(true);
    try {
      const result = await fetchDemoChunks(selected.quarter_key);
      setChunkResult(result);
      setStep("chunk");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [selected, resetFrom]);

  const handleToggleChunk = useCallback((index: number) => {
    setSelectedChunkIndices((prev) =>
      prev.includes(index)
        ? prev.filter((i) => i !== index)
        : [...prev, index].sort((a, b) => a - b)
    );
  }, []);

  const handleSelectAllChunks = useCallback(() => {
    if (!chunkResult) return;
    setSelectedChunkIndices(chunkResult.chunks.map((c) => c.chunk_index));
  }, [chunkResult]);

  const handleDeselectAllChunks = useCallback(() => {
    setSelectedChunkIndices([]);
  }, []);

  const handleExtract = useCallback(
    (indices: number[]) => {
      if (!selected || indices.length === 0) return;
      const quarterKey = selected.quarter_key;
      resetFrom("extract");
      setStep("extract");
      setIsStreaming(true);

      const sorted = [...indices].sort((a, b) => a - b);
      let current = 0;

      function runNext() {
        if (current >= sorted.length) {
          setIsStreaming(false);
          setCurrentChunkLabel("");
          return;
        }

        const chunkIdx = sorted[current];
        const label = `Chunk ${chunkIdx} (${current + 1}/${sorted.length})`;
        setCurrentChunkLabel(label);

        if (current > 0) {
          setStreamText(
            (prev) => prev + `\n\n--- ${label} ---\n\n`
          );
        }

        const controller = streamDemoExtraction(
          quarterKey,
          chunkIdx,
          {
            onPrompt: (p) => setPromptPreview(p.user_preview),
            onToken: (text) => setStreamText((prev) => prev + text),
            onExtraction: (data) =>
              setExtractions((prev) => [
                ...prev,
                data as Record<string, unknown>,
              ]),
            onDone: () => {
              current++;
              runNext();
            },
            onError: (msg) => {
              setError(msg);
              setIsStreaming(false);
            },
          }
        );
        abortRef.current = controller;
      }

      runNext();
    },
    [selected, resetFrom]
  );

  const handleExtractSelected = useCallback(() => {
    handleExtract(selectedChunkIndices);
  }, [handleExtract, selectedChunkIndices]);

  const handleExtractAll = useCallback(() => {
    if (!chunkResult) return;
    const all = chunkResult.chunks.map((c) => c.chunk_index);
    setSelectedChunkIndices(all);
    handleExtract(all);
  }, [handleExtract, chunkResult]);

  const handleScore = useCallback(async () => {
    if (!selected || extractions.length === 0) return;
    setLoading(true);
    try {
      const result = await fetchDemoScore(selected.quarter_key, extractions);
      setScoreResult(result);
      setStep("score");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [selected, extractions]);

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Pipeline Demo</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Step through the industrial signal extraction pipeline on a real
          earnings transcript.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-3 text-xs underline"
          >
            dismiss
          </button>
        </div>
      )}

      {/* Step 1: Select Transcript */}
      <StepCard
        stepNumber={1}
        title="Select Transcript"
        description="Choose an earnings call transcript to analyze."
        status={stepStatus("select", step)}
        summary={
          selected
            ? `${selected.ticker} — ${selected.company_name} (${selected.year} Q${selected.quarter})`
            : undefined
        }
      >
        {loading && transcripts.length === 0 ? (
          <p className="text-sm text-zinc-500 animate-pulse">
            Loading transcripts...
          </p>
        ) : (
          <>
            <TranscriptSelector
              transcripts={transcripts}
              selected={selected}
              onSelect={handleSelectTranscript}
            />
            {selected && (
              <button
                onClick={handleParse}
                disabled={loading}
                className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50 transition-colors"
              >
                {loading ? "Parsing..." : "Parse Sections"}
              </button>
            )}
          </>
        )}
      </StepCard>

      {/* Step 2: Parse */}
      <StepCard
        stepNumber={2}
        title="Parse Sections"
        description="Detect prepared remarks vs Q&A sections."
        status={stepStatus("parse", step)}
        summary={
          parseResult
            ? `${parseResult.sections.length} sections, ${parseResult.boundary_found ? "Q&A found" : "no Q&A boundary"}`
            : undefined
        }
      >
        {parseResult && (
          <>
            <ParseDisplay result={parseResult} />
            <button
              onClick={handleChunk}
              disabled={loading}
              className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50 transition-colors"
            >
              {loading ? "Chunking..." : "Chunk Transcript"}
            </button>
          </>
        )}
      </StepCard>

      {/* Step 3: Chunk */}
      <StepCard
        stepNumber={3}
        title="Chunk Transcript"
        description="Split into ~800-token chunks for LLM analysis."
        status={stepStatus("chunk", step)}
        summary={
          chunkResult
            ? `${chunkResult.total_chunks} chunks, ~${chunkResult.avg_tokens} avg tokens`
            : undefined
        }
      >
        {chunkResult && (
          <>
            <ChunkDisplay
              result={chunkResult}
              selectedIndices={selectedChunkIndices}
              onToggleChunk={handleToggleChunk}
              onSelectAll={handleSelectAllChunks}
              onDeselectAll={handleDeselectAllChunks}
            />
            <div className="mt-4 flex gap-3">
              {selectedChunkIndices.length > 0 && (
                <button
                  onClick={handleExtractSelected}
                  disabled={isStreaming}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50 transition-colors"
                >
                  {isStreaming
                    ? "Extracting..."
                    : `Run Extraction (${selectedChunkIndices.length} chunk${selectedChunkIndices.length > 1 ? "s" : ""})`}
                </button>
              )}
              <button
                onClick={handleExtractAll}
                disabled={isStreaming}
                className="rounded-lg border border-blue-500/50 bg-blue-500/10 px-4 py-2 text-sm font-medium text-blue-400 hover:bg-blue-500/20 disabled:opacity-50 transition-colors"
              >
                {isStreaming ? "Extracting..." : "Run All Chunks"}
              </button>
            </div>
          </>
        )}
      </StepCard>

      {/* Step 4: Extract */}
      <StepCard
        stepNumber={4}
        title="Extract Signals"
        description="Stream LLM analysis of selected chunks."
        status={stepStatus("extract", step)}
        summary={
          extractions.length > 0
            ? `${extractions.length} extraction${extractions.length > 1 ? "s" : ""} complete`
            : undefined
        }
      >
        <ExtractionStream
          streamText={streamText}
          isStreaming={isStreaming}
          extractions={extractions}
          promptPreview={promptPreview}
          currentChunkLabel={currentChunkLabel}
        />
        {extractions.length > 0 && !isStreaming && (
          <button
            onClick={handleScore}
            disabled={loading}
            className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50 transition-colors"
          >
            {loading ? "Scoring..." : "Compute Score"}
          </button>
        )}
      </StepCard>

      {/* Step 5: Score */}
      <StepCard
        stepNumber={5}
        title="Composite Score"
        description="See how the extraction feeds the scoring formula."
        status={stepStatus("score", step)}
        summary={
          scoreResult
            ? `Score: ${(scoreResult.composite_score * 100).toFixed(1)}%`
            : undefined
        }
      >
        {scoreResult && <ScoreDisplay result={scoreResult} />}
      </StepCard>
    </div>
  );
}
