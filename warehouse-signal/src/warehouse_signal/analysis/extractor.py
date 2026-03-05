"""Claude API signal extractor.

Uses the Anthropic SDK to analyze transcript chunks for warehouse expansion signals.
"""

from __future__ import annotations

import json
import re

import anthropic
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from warehouse_signal.analysis.base import SignalAnalyzer
from warehouse_signal.analysis.prompt import format_extraction_prompt, format_system_prompt
from warehouse_signal.config import Config
from warehouse_signal.models.schemas import ChunkExtraction, TranscriptChunk


class ClaudeAnalyzer(SignalAnalyzer):
    """Signal extraction using the Claude API."""

    def __init__(self):
        if not Config.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY is required. Set it in .env.")
        self._client = anthropic.AsyncAnthropic(api_key=Config.ANTHROPIC_API_KEY)
        self._model = Config.LLM_MODEL
        self._max_tokens = Config.EXTRACTION_MAX_TOKENS

    @property
    def name(self) -> str:
        return "claude"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=30),
        retry=retry_if_exception_type(
            (anthropic.RateLimitError, anthropic.InternalServerError)
        ),
    )
    async def _call_api(self, system: str, user: str) -> str:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text

    async def extract_signals(
        self,
        chunk: TranscriptChunk,
        ticker: str,
        company_name: str,
        year: int,
        quarter: int,
    ) -> ChunkExtraction:
        system = format_system_prompt(
            ticker=ticker,
            company_name=company_name,
            year=year,
            quarter=quarter,
            section_type=chunk.section_type.value,
        )
        user = format_extraction_prompt(chunk_text=chunk.text)

        try:
            raw = await self._call_api(system, user)
            parsed = _parse_json(raw)
            return ChunkExtraction(**parsed)
        except Exception as e:
            return ChunkExtraction(
                warehouse_relevance=0.0,
                expansion_score=0.0,
                reasoning=f"Extraction failed: {e}",
            )

    async def close(self) -> None:
        await self._client.close()


def _parse_json(text: str) -> dict:
    """Parse JSON from LLM response, stripping markdown fences if present."""
    cleaned = text.strip()
    # Strip markdown code fences
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    return json.loads(cleaned)
