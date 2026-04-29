"""Signal Framework CRUD + dry-run endpoints.

A "framework" is a named bundle of (phrase, weight, category) rules that
the keyword engine applies to every chunk. Users edit it via /framework
in the UI; this router exposes the persistence layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from warehouse_signal.analysis.keyword_engine import (
    commitment_evidence_bonus,
    detect,
    hits_summary_by_category,
    keyword_score,
)
from warehouse_signal.api.deps import get_storage
from warehouse_signal.models.schemas import (
    KeywordCategory,
    SignalFramework,
    SignalKeyword,
    TranscriptChunk,
    SectionType,
)
from warehouse_signal.scoring.aggregator import compute_chunk_score

router = APIRouter(prefix="/frameworks", tags=["frameworks"])


# ---------------------------------------------------------------------------
# Request / response shapes
# ---------------------------------------------------------------------------

class FrameworkCreate(BaseModel):
    name: str
    description: str = ""
    is_default: bool = False


class FrameworkUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_default: bool | None = None


class KeywordCreate(BaseModel):
    category: KeywordCategory
    phrase: str
    is_regex: bool = False
    weight: float = Field(ge=1.0, le=10.0, default=5.0)
    companion_pattern: str | None = None
    notes: str = ""


class KeywordUpdate(BaseModel):
    category: KeywordCategory | None = None
    phrase: str | None = None
    is_regex: bool | None = None
    weight: float | None = Field(default=None, ge=1.0, le=10.0)
    companion_pattern: str | None = None
    notes: str | None = None


class DryRunRequest(BaseModel):
    text: str
    section_type: SectionType = SectionType.PREPARED_REMARKS
    # Optional LLM expansion score so the dry-run can preview the hybrid composite
    llm_expansion_score: float = 0.0


# ---------------------------------------------------------------------------
# Frameworks
# ---------------------------------------------------------------------------

@router.get("")
def list_frameworks() -> list[dict]:
    storage = get_storage()
    return [fw.model_dump(mode="json") for fw in storage.list_frameworks()]


@router.get("/{framework_id}")
def get_framework(framework_id: str) -> dict:
    storage = get_storage()
    fw = storage.get_framework(framework_id)
    if not fw:
        raise HTTPException(404, f"Framework {framework_id} not found")
    return fw.model_dump(mode="json")


@router.post("", status_code=201)
def create_framework(req: FrameworkCreate) -> dict:
    storage = get_storage()
    now = datetime.now(timezone.utc)
    fw = SignalFramework(
        id=str(uuid.uuid4()),
        name=req.name,
        description=req.description,
        is_default=req.is_default,
        keywords=[],
        created_at=now,
        updated_at=now,
    )
    storage.save_framework(fw)
    return fw.model_dump(mode="json")


@router.patch("/{framework_id}")
def update_framework(framework_id: str, req: FrameworkUpdate) -> dict:
    storage = get_storage()
    fw = storage.get_framework(framework_id)
    if not fw:
        raise HTTPException(404, f"Framework {framework_id} not found")
    if req.name is not None:
        fw.name = req.name
    if req.description is not None:
        fw.description = req.description
    if req.is_default is not None:
        fw.is_default = req.is_default
    fw.updated_at = datetime.now(timezone.utc)
    storage.save_framework(fw)
    return fw.model_dump(mode="json")


@router.delete("/{framework_id}", status_code=204)
def delete_framework(framework_id: str) -> None:
    storage = get_storage()
    if not storage.get_framework(framework_id):
        raise HTTPException(404, f"Framework {framework_id} not found")
    if storage.db["signal_frameworks"].count <= 1:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot delete the only framework. Create another framework "
                "first, then delete this one."
            ),
        )
    storage.delete_framework(framework_id)


@router.post("/{framework_id}/duplicate", status_code=201)
def duplicate_framework(framework_id: str, req: FrameworkCreate) -> dict:
    storage = get_storage()
    src = storage.get_framework(framework_id)
    if not src:
        raise HTTPException(404, f"Framework {framework_id} not found")
    now = datetime.now(timezone.utc)
    new_id = str(uuid.uuid4())
    cloned_keywords = [
        SignalKeyword(
            id=str(uuid.uuid4()),
            framework_id=new_id,
            category=kw.category,
            phrase=kw.phrase,
            is_regex=kw.is_regex,
            weight=kw.weight,
            companion_pattern=kw.companion_pattern,
            notes=kw.notes,
            created_at=now,
        )
        for kw in src.keywords
    ]
    cloned = SignalFramework(
        id=new_id,
        name=req.name or f"{src.name} (copy)",
        description=req.description or src.description,
        is_default=req.is_default,
        keywords=cloned_keywords,
        created_at=now,
        updated_at=now,
    )
    storage.save_framework(cloned)
    return cloned.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------

@router.post("/{framework_id}/keywords", status_code=201)
def add_keyword(framework_id: str, req: KeywordCreate) -> dict:
    storage = get_storage()
    if not storage.get_framework(framework_id):
        raise HTTPException(404, f"Framework {framework_id} not found")
    kw = SignalKeyword(
        id=str(uuid.uuid4()),
        framework_id=framework_id,
        category=req.category,
        phrase=req.phrase,
        is_regex=req.is_regex,
        weight=req.weight,
        companion_pattern=req.companion_pattern,
        notes=req.notes,
        created_at=datetime.now(timezone.utc),
    )
    storage.add_keyword(kw)
    return kw.model_dump(mode="json")


@router.patch("/{framework_id}/keywords/{keyword_id}")
def update_keyword(
    framework_id: str, keyword_id: str, req: KeywordUpdate
) -> dict:
    storage = get_storage()
    fw = storage.get_framework(framework_id)
    if not fw:
        raise HTTPException(404, f"Framework {framework_id} not found")
    target = next((k for k in fw.keywords if k.id == keyword_id), None)
    if not target:
        raise HTTPException(404, f"Keyword {keyword_id} not in framework")
    if req.category is not None:
        target.category = req.category
    if req.phrase is not None:
        target.phrase = req.phrase
    if req.is_regex is not None:
        target.is_regex = req.is_regex
    if req.weight is not None:
        target.weight = req.weight
    if req.companion_pattern is not None:
        target.companion_pattern = req.companion_pattern or None
    if req.notes is not None:
        target.notes = req.notes
    storage.update_keyword(target)
    return target.model_dump(mode="json")


@router.delete("/{framework_id}/keywords/{keyword_id}", status_code=204)
def delete_keyword(framework_id: str, keyword_id: str) -> None:
    storage = get_storage()
    if not storage.get_framework(framework_id):
        raise HTTPException(404, f"Framework {framework_id} not found")
    storage.delete_keyword(keyword_id)


# ---------------------------------------------------------------------------
# Dry-run: preview hits + projected score against arbitrary text
# ---------------------------------------------------------------------------

@router.post("/{framework_id}/dry-run")
def dry_run(framework_id: str, req: DryRunRequest) -> dict:
    storage = get_storage()
    fw = storage.get_framework(framework_id)
    if not fw:
        raise HTTPException(404, f"Framework {framework_id} not found")

    chunk = TranscriptChunk(
        chunk_id="dry-run",
        transcript_key="dry-run",
        chunk_index=0,
        text=req.text,
        section_type=req.section_type,
        token_estimate=len(req.text.split()),
    )
    hits = detect(chunk, fw)
    kw_score = keyword_score(hits)
    commit_score = commitment_evidence_bonus(hits)
    hybrid, _, _ = compute_chunk_score(req.llm_expansion_score, hits)

    return {
        "framework_id": framework_id,
        "hits": [h.model_dump(mode="json") for h in hits],
        "keyword_score": kw_score,
        "commitment_score": commit_score,
        "hybrid_chunk_score": hybrid,
        "llm_expansion_score": req.llm_expansion_score,
        "summary": hits_summary_by_category(hits),
        "total_hits": len(hits),
    }
