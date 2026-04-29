"""Manual transcript upload (text + PDF) round-trip tests."""

from __future__ import annotations

import io
import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "ws.db"))
    # Late-import so the env var is honored
    from warehouse_signal.api.server import app

    with TestClient(app) as c:
        yield c


_PLD_TEXT = (
    "We broke ground on two new distribution centers this quarter and "
    "committed approximately 180 million in logistics capex over the next "
    "18 months. We have committed to adding 2.4 million sq ft of new "
    "fulfillment center capacity. Three build-to-suit projects under letter "
    "of intent for Q3 2026. Our network optimization study identified "
    "capacity constraints across our Midwest hub network. We are also "
    "evaluating new fulfillment nodes in secondary markets."
)


def test_text_upload_roundtrip(client):
    r = client.post(
        "/api/transcripts/upload",
        data={
            "ticker": "PLD",
            "company_name": "Prologis",
            "year": 2024,
            "quarter": 3,
            "sector": "reit_industrial",
            "raw_text": _PLD_TEXT,
        },
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload["quarter_key"] == "PLD_2024Q3"
    assert payload["chunk_count"] >= 1

    # Re-score with keyword engine only (no LLM)
    r2 = client.post(
        f"/api/transcripts/{payload['quarter_key']}/score",
        json={"run_keyword_engine": True, "run_llm": False},
    )
    assert r2.status_code == 200
    score = r2.json()
    assert "composite_score" in score
    assert score["tier"] in {"strong", "moderate", "watchlist", "noise"}
    # Even without LLM, keyword + commitment components should be > 0
    components = score["score_components"]
    assert components["keyword_component"] > 0
    assert components["commitment_component"] > 0


def test_text_upload_rejects_empty(client):
    r = client.post(
        "/api/transcripts/upload",
        data={
            "ticker": "X",
            "company_name": "X",
            "year": 2024,
            "quarter": 1,
            "sector": "other",
        },
    )
    assert r.status_code == 400


def test_text_upload_caps_size(client):
    huge = "x " * 200_000  # well over the 200KB cap
    r = client.post(
        "/api/transcripts/upload",
        data={
            "ticker": "X",
            "company_name": "X",
            "year": 2024,
            "quarter": 1,
            "sector": "other",
            "raw_text": huge,
        },
    )
    assert r.status_code == 413


def test_pdf_upload_roundtrip(client):
    pypdf = pytest.importorskip("pypdf")
    from pypdf import PdfWriter

    # Build a text-containing PDF in memory using pypdf — pypdf can't add
    # text to a blank doc directly, so we use a minimal third-party route.
    # Instead, we'll use a hand-rolled minimal PDF that contains text.
    minimal_pdf = _build_minimal_text_pdf(_PLD_TEXT)
    r = client.post(
        "/api/transcripts/upload",
        files={"file": ("transcript.pdf", minimal_pdf, "application/pdf")},
        data={
            "ticker": "PLD",
            "company_name": "Prologis",
            "year": 2024,
            "quarter": 3,
            "sector": "reit_industrial",
        },
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["quarter_key"] == "PLD_2024Q3"
    assert payload["raw_text_length"] > 100


def test_pdf_upload_rejects_scanned(client):
    """A large file with no extractable text should be rejected."""
    # 60KB of binary garbage that pypdf will refuse to parse OR extract no text
    fake = b"%PDF-1.4\n" + b"\x00" * 60_000 + b"\n%%EOF\n"
    r = client.post(
        "/api/transcripts/upload",
        files={"file": ("scanned.pdf", fake, "application/pdf")},
        data={
            "ticker": "X",
            "company_name": "X",
            "year": 2024,
            "quarter": 1,
            "sector": "other",
        },
    )
    assert r.status_code == 400


def _build_minimal_text_pdf(text: str) -> bytes:
    """Hand-roll a tiny single-page PDF with literal text content."""
    # This is a minimal PDF where the page's content stream is just a
    # text-show command. pypdf will parse it and yield the text.
    # Reference: PDF 1.4 spec, §7.5
    safe = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    content_stream = f"BT /F1 12 Tf 50 750 Td ({safe}) Tj ET".encode("latin-1", "replace")
    contents_obj = (
        b"4 0 obj\n<< /Length "
        + str(len(content_stream)).encode()
        + b" >>\nstream\n"
        + content_stream
        + b"\nendstream\nendobj\n"
    )
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Count 1 /Kids [3 0 R] >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        ),
        contents_obj,
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for obj in objects:
        offsets.append(len(out))
        out += obj
    xref_offset = len(out)
    out += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n"
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        b"trailer\n<< /Size "
        + str(len(objects) + 1).encode()
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_offset).encode()
        + b"\n%%EOF\n"
    )
    return out
