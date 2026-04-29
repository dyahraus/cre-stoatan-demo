"""Signal Framework CRUD + dry-run + bulk-import endpoints.

A "framework" is a named bundle of (phrase, weight, category) rules that
the keyword engine applies to every chunk. Users edit it via /framework
in the UI; this router exposes the persistence layer.
"""

from __future__ import annotations

import csv
import io
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from warehouse_signal.analysis.concept_engine import (
    concept_score,
    detect as detect_concepts,
    hits_summary_by_concept,
)
from warehouse_signal.analysis.embeddings import NullEmbedder, get_embedder
from warehouse_signal.analysis.keyword_engine import (
    commitment_evidence_bonus,
    detect,
    hits_summary_by_category,
    keyword_score,
)
from warehouse_signal.api.deps import get_storage
from warehouse_signal.models.schemas import (
    BoostConfig,
    ConceptMode,
    KeywordCategory,
    SignalConcept,
    SignalFramework,
    SignalKeyword,
    TranscriptChunk,
    SectionType,
)
from warehouse_signal.scoring.aggregator import compute_chunk_score

router = APIRouter(prefix="/frameworks", tags=["frameworks"])


# ---------------------------------------------------------------------------
# Static routes — declared first so they don't collide with /{framework_id}
# ---------------------------------------------------------------------------

_TEMPLATE_CSV = (
    "phrase,category,weight,is_regex,companion_pattern,notes\n"
    "distribution center,industrial_transformation,7.0,false,,\n"
    '"broke ground",commitment_level,9.0,false,'
    '"\\$\\s?\\d|\\d[\\d,\\.]*\\s*(million|billion|sq\\.?\\s?ft)",'
    '"requires nearby $ amount or sqft"\n'
    "automation,industrial_transformation,5.0,false,,R&D-tagged\n"
)


@router.get("/template.csv", response_class=PlainTextResponse)
def keyword_template_csv() -> str:
    """Downloadable CSV template for bulk imports."""
    return _TEMPLATE_CSV


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
    boosts: BoostConfig | None = None


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
    if req.boosts is not None:
        fw.boosts = req.boosts
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
# Concepts (semantic detectors, Phase 6D)
# ---------------------------------------------------------------------------

class ConceptCreate(BaseModel):
    category: KeywordCategory
    label: str
    description: str = ""
    example_phrases: list[str] = []
    weight: float = Field(ge=1.0, le=10.0, default=5.0)
    threshold: float = Field(ge=0.5, le=0.9, default=0.65)
    mode: ConceptMode = ConceptMode.EMBEDDING


class ConceptUpdate(BaseModel):
    category: KeywordCategory | None = None
    label: str | None = None
    description: str | None = None
    example_phrases: list[str] | None = None
    weight: float | None = Field(default=None, ge=1.0, le=10.0)
    threshold: float | None = Field(default=None, ge=0.5, le=0.9)
    mode: ConceptMode | None = None


@router.post("/{framework_id}/concepts", status_code=201)
def add_concept(framework_id: str, req: ConceptCreate) -> dict:
    storage = get_storage()
    if not storage.get_framework(framework_id):
        raise HTTPException(404, f"Framework {framework_id} not found")
    concept = SignalConcept(
        id=str(uuid.uuid4()),
        framework_id=framework_id,
        category=req.category,
        label=req.label,
        description=req.description,
        example_phrases=req.example_phrases,
        weight=req.weight,
        threshold=req.threshold,
        mode=req.mode,
        created_at=datetime.now(timezone.utc),
    )
    storage.add_concept(concept)
    return concept.model_dump(mode="json")


@router.patch("/{framework_id}/concepts/{concept_id}")
def update_concept(
    framework_id: str, concept_id: str, req: ConceptUpdate
) -> dict:
    storage = get_storage()
    fw = storage.get_framework(framework_id)
    if not fw:
        raise HTTPException(404, f"Framework {framework_id} not found")
    target = next((c for c in fw.concepts if c.id == concept_id), None)
    if not target:
        raise HTTPException(404, f"Concept {concept_id} not in framework")
    if req.category is not None:
        target.category = req.category
    if req.label is not None:
        target.label = req.label
    if req.description is not None:
        target.description = req.description
    if req.example_phrases is not None:
        target.example_phrases = req.example_phrases
    if req.weight is not None:
        target.weight = req.weight
    if req.threshold is not None:
        target.threshold = req.threshold
    if req.mode is not None:
        target.mode = req.mode
    storage.update_concept(target)
    return target.model_dump(mode="json")


@router.delete("/{framework_id}/concepts/{concept_id}", status_code=204)
def delete_concept(framework_id: str, concept_id: str) -> None:
    storage = get_storage()
    if not storage.get_framework(framework_id):
        raise HTTPException(404, f"Framework {framework_id} not found")
    storage.delete_concept(concept_id)


# ---------------------------------------------------------------------------
# Bulk import (CSV / JSON)
# ---------------------------------------------------------------------------

_REQUIRED_COLUMNS = {"phrase", "category"}
_OPTIONAL_COLUMNS = {"weight", "is_regex", "companion_pattern", "notes"}


class ImportRow(BaseModel):
    phrase: str
    category: str
    weight: float = 5.0
    is_regex: bool = False
    companion_pattern: str | None = None
    notes: str = ""


class ImportRequest(BaseModel):
    rows: list[ImportRow]


class ImportResult(BaseModel):
    framework_id: str
    imported: int
    skipped: int
    errors: list[dict]


def _parse_bool(s: str) -> bool:
    return str(s).strip().lower() in {"true", "1", "yes", "y", "t"}


def _existing_keyword_keys(fw: SignalFramework) -> set[tuple[str, str, bool]]:
    """Dedupe key: (phrase lowercase, category, is_regex)."""
    return {
        (k.phrase.strip().lower(), k.category.value, k.is_regex)
        for k in fw.keywords
    }


def _process_import_rows(
    framework_id: str, fw: SignalFramework, rows: list[tuple[int, dict]]
) -> ImportResult:
    storage = get_storage()
    existing = _existing_keyword_keys(fw)
    imported = 0
    skipped = 0
    errors: list[dict] = []
    seen_in_batch: set[tuple[str, str, bool]] = set()

    for line_num, raw in rows:
        try:
            phrase = (raw.get("phrase") or "").strip()
            category_str = (raw.get("category") or "").strip()
            if not phrase or not category_str:
                errors.append(
                    {"line": line_num, "reason": "phrase and category required"}
                )
                skipped += 1
                continue
            try:
                category = KeywordCategory(category_str)
            except ValueError:
                errors.append(
                    {
                        "line": line_num,
                        "reason": f"unknown category {category_str!r}",
                    }
                )
                skipped += 1
                continue

            weight_raw = raw.get("weight", 5.0)
            try:
                weight = float(weight_raw) if weight_raw not in ("", None) else 5.0
            except (TypeError, ValueError):
                errors.append(
                    {"line": line_num, "reason": f"invalid weight {weight_raw!r}"}
                )
                skipped += 1
                continue
            weight = max(1.0, min(10.0, weight))

            is_regex_raw = raw.get("is_regex", False)
            is_regex = (
                bool(is_regex_raw)
                if isinstance(is_regex_raw, bool)
                else _parse_bool(is_regex_raw)
            )

            if is_regex:
                try:
                    re.compile(phrase)
                except re.error as e:
                    errors.append(
                        {"line": line_num, "reason": f"bad regex: {e}"}
                    )
                    skipped += 1
                    continue

            companion = (raw.get("companion_pattern") or "").strip() or None
            if companion:
                try:
                    re.compile(companion)
                except re.error as e:
                    errors.append(
                        {
                            "line": line_num,
                            "reason": f"bad companion regex: {e}",
                        }
                    )
                    skipped += 1
                    continue

            key = (phrase.lower(), category.value, is_regex)
            if key in existing or key in seen_in_batch:
                skipped += 1
                continue
            seen_in_batch.add(key)

            kw = SignalKeyword(
                id=str(uuid.uuid4()),
                framework_id=framework_id,
                category=category,
                phrase=phrase,
                is_regex=is_regex,
                weight=weight,
                companion_pattern=companion,
                notes=(raw.get("notes") or "").strip(),
                created_at=datetime.now(timezone.utc),
            )
            storage.add_keyword(kw)
            imported += 1
        except Exception as e:  # noqa: BLE001
            errors.append({"line": line_num, "reason": str(e)})
            skipped += 1

    return ImportResult(
        framework_id=framework_id,
        imported=imported,
        skipped=skipped,
        errors=errors,
    )


@router.post("/{framework_id}/keywords/import")
async def import_keywords_csv(
    framework_id: str,
    file: UploadFile = File(...),
) -> ImportResult:
    """Import keywords from a CSV file (multipart upload).

    CSV columns: phrase (required), category (required), weight,
    is_regex, companion_pattern, notes. Header row required.

    Idempotent: rows that match an existing (phrase, category,
    is_regex) in the framework are skipped, not duplicated.
    """
    storage = get_storage()
    fw = storage.get_framework(framework_id)
    if not fw:
        raise HTTPException(404, f"Framework {framework_id} not found")
    try:
        data = (await file.read()).decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Could not read file: {e}")
    try:
        reader = csv.DictReader(io.StringIO(data))
        if reader.fieldnames is None or not _REQUIRED_COLUMNS.issubset(
            {(c or "").strip() for c in reader.fieldnames}
        ):
            raise HTTPException(
                400,
                f"CSV must include columns {sorted(_REQUIRED_COLUMNS)}",
            )
        rows = [(line_num, row) for line_num, row in enumerate(reader, start=2)]
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Malformed CSV: {e}")
    return _process_import_rows(framework_id, fw, rows)


@router.post("/{framework_id}/keywords/import-json")
def import_keywords_json(
    framework_id: str, body: ImportRequest
) -> ImportResult:
    """Import keywords from a JSON body. Useful for programmatic clients."""
    storage = get_storage()
    fw = storage.get_framework(framework_id)
    if not fw:
        raise HTTPException(404, f"Framework {framework_id} not found")
    rows = [(i, r.model_dump()) for i, r in enumerate(body.rows, start=1)]
    return _process_import_rows(framework_id, fw, rows)


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
    kw_score_val = keyword_score(hits)
    commit_score = commitment_evidence_bonus(hits)

    concept_hits = []
    concept_score_val = 0.0
    embedder_status = "none"
    if fw.concepts:
        embedder = get_embedder()
        if not isinstance(embedder, NullEmbedder):
            embedder_status = embedder.name
            try:
                chunk_vec = embedder.embed(req.text)
            except Exception:  # noqa: BLE001
                chunk_vec = []
            if chunk_vec:
                concept_hits = detect_concepts(
                    chunk, fw.concepts, chunk_vec, embedder=embedder
                )
                concept_score_val = concept_score(concept_hits)
        else:
            embedder_status = "missing-key"

    hybrid, _, _, _ = compute_chunk_score(
        req.llm_expansion_score, hits, concept_hits
    )

    return {
        "framework_id": framework_id,
        "hits": [h.model_dump(mode="json") for h in hits],
        "concept_hits": [c.model_dump(mode="json") for c in concept_hits],
        "keyword_score": kw_score_val,
        "concept_score": concept_score_val,
        "commitment_score": commit_score,
        "hybrid_chunk_score": hybrid,
        "llm_expansion_score": req.llm_expansion_score,
        "summary": hits_summary_by_category(hits),
        "concept_summary": hits_summary_by_concept(concept_hits),
        "total_hits": len(hits),
        "total_concept_hits": len(concept_hits),
        "embedder": embedder_status,
    }
