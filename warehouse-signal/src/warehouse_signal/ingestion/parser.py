"""Transcript parsing and chunking.

Two responsibilities:
1. Section parsing: split raw transcript into prepared remarks vs Q&A
   (when the provider doesn't do this for us)
2. Chunking: break sections into LLM-sized chunks for signal extraction
"""

from __future__ import annotations

import re
import hashlib

from warehouse_signal.config import Config
from warehouse_signal.models.schemas import (
    SectionType,
    Transcript,
    TranscriptChunk,
    TranscriptSection,
)

# ---------------------------------------------------------------------------
# Section detection patterns
# ---------------------------------------------------------------------------

# Common patterns that signal the transition from prepared remarks to Q&A
_QA_BOUNDARY_PATTERNS = [
    re.compile(r"(?:operator|moderator)[,:]?\s*(?:we are|we're|let's|let us)?\s*(?:now\s+)?(?:open|begin|start)\s+(?:the\s+)?(?:line|floor|call)\s+(?:for|to)\s+questions", re.IGNORECASE),
    re.compile(r"(?:let's|let us)\s+(?:open|begin|start)\s+(?:it\s+)?(?:up\s+)?(?:for|to)\s+questions", re.IGNORECASE),
    re.compile(r"operator,?\s+(?:please\s+)?open\s+the\s+(?:line|call)", re.IGNORECASE),
    re.compile(r"q(?:uestion)?[\s-]*(?:and|&)[\s-]*a(?:nswer)?\s*(?:session|period|portion)", re.IGNORECASE),
    re.compile(r"(?:we'll|we will)\s+now\s+take\s+(?:your\s+)?questions", re.IGNORECASE),
    re.compile(r"(?:i|we)\s+(?:would|will|'d)\s+(?:now\s+)?like\s+to\s+(?:open|turn)\s+(?:the\s+call|it)\s+(?:over\s+)?(?:for|to)\s+questions", re.IGNORECASE),
]

# Patterns for identifying speakers in Q&A
_SPEAKER_PATTERN = re.compile(
    r"^([A-Z][a-zA-Z\s\.\-']{2,40})\s*(?:--|—|:)\s*",
    re.MULTILINE,
)


def parse_sections(transcript: Transcript) -> Transcript:
    """Parse a transcript into prepared remarks and Q&A sections.

    If the transcript already has non-FULL sections (i.e., the provider
    gave us structured data), this is a no-op.

    Mutates and returns the transcript.
    """
    if transcript.has_sections:
        return transcript  # Provider already segmented

    raw = transcript.raw_text
    if not raw:
        return transcript

    # Try to find the Q&A boundary
    split_pos = None
    for pattern in _QA_BOUNDARY_PATTERNS:
        match = pattern.search(raw)
        if match:
            split_pos = match.start()
            break

    if split_pos and split_pos > 200:  # sanity: prepared remarks should be substantial
        prepared_text = raw[:split_pos].strip()
        qa_text = raw[split_pos:].strip()

        transcript.sections = [
            TranscriptSection(
                section_type=SectionType.PREPARED_REMARKS,
                text=prepared_text,
            ),
            TranscriptSection(
                section_type=SectionType.QA,
                text=qa_text,
            ),
        ]
    else:
        # Could not detect boundary — keep as single section
        transcript.sections = [
            TranscriptSection(
                section_type=SectionType.FULL,
                text=raw,
            )
        ]

    return transcript


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~0.75 tokens per word for English text."""
    return int(len(text.split()) * 1.33)


def _make_chunk_id(transcript_key: str, chunk_index: int) -> str:
    """Deterministic chunk ID."""
    raw = f"{transcript_key}::{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def chunk_transcript(
    transcript: Transcript,
    target_tokens: int | None = None,
    max_tokens: int | None = None,
) -> list[TranscriptChunk]:
    """Break transcript sections into LLM-sized chunks.

    Chunks respect section boundaries (never spans prepared remarks into Q&A).
    Splits on paragraph boundaries when possible, sentence boundaries as fallback.
    """
    target = target_tokens or Config.CHUNK_TARGET_TOKENS
    maximum = max_tokens or Config.CHUNK_MAX_TOKENS

    if not transcript.sections:
        parse_sections(transcript)

    chunks: list[TranscriptChunk] = []
    chunk_index = 0

    for section in transcript.sections:
        paragraphs = _split_paragraphs(section.text)

        current_text = ""
        current_tokens = 0

        for para in paragraphs:
            para_tokens = _estimate_tokens(para)

            # If a single paragraph exceeds max, split it by sentences
            if para_tokens > maximum:
                # Flush current buffer
                if current_text.strip():
                    chunks.append(_build_chunk(
                        transcript.quarter_key, chunk_index, current_text,
                        section.section_type, section.speaker, section.speaker_role,
                    ))
                    chunk_index += 1
                    current_text = ""
                    current_tokens = 0

                # Split the oversized paragraph
                for sentence_chunk in _split_by_sentences(para, target, maximum):
                    chunks.append(_build_chunk(
                        transcript.quarter_key, chunk_index, sentence_chunk,
                        section.section_type, section.speaker, section.speaker_role,
                    ))
                    chunk_index += 1
                continue

            # Would adding this paragraph exceed target?
            if current_tokens + para_tokens > target and current_text.strip():
                chunks.append(_build_chunk(
                    transcript.quarter_key, chunk_index, current_text,
                    section.section_type, section.speaker, section.speaker_role,
                ))
                chunk_index += 1
                current_text = para
                current_tokens = para_tokens
            else:
                current_text += ("\n\n" if current_text else "") + para
                current_tokens += para_tokens

        # Flush remaining text in this section
        if current_text.strip():
            chunks.append(_build_chunk(
                transcript.quarter_key, chunk_index, current_text,
                section.section_type, section.speaker, section.speaker_role,
            ))
            chunk_index += 1

    return chunks


def _build_chunk(
    transcript_key: str,
    index: int,
    text: str,
    section_type: SectionType,
    speaker: str | None,
    speaker_role: str | None,
) -> TranscriptChunk:
    return TranscriptChunk(
        chunk_id=_make_chunk_id(transcript_key, index),
        transcript_key=transcript_key,
        chunk_index=index,
        text=text.strip(),
        section_type=section_type,
        speaker=speaker,
        speaker_role=speaker_role,
        token_estimate=_estimate_tokens(text),
    )


def _split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs on double newlines."""
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()]


def _split_by_sentences(text: str, target: int, maximum: int) -> list[str]:
    """Split text by sentences, grouping to stay near target token count."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    result_chunks = []
    current = ""
    current_tokens = 0

    for sentence in sentences:
        sent_tokens = _estimate_tokens(sentence)
        if current_tokens + sent_tokens > target and current:
            result_chunks.append(current.strip())
            current = sentence
            current_tokens = sent_tokens
        else:
            current += (" " if current else "") + sentence
            current_tokens += sent_tokens

    if current.strip():
        result_chunks.append(current.strip())

    return result_chunks
