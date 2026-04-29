"""Bulk-import (CSV / JSON) tests for the framework keywords endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "ws.db"))
    from warehouse_signal.api.server import app

    with TestClient(app) as c:
        yield c


def _default_id(client) -> str:
    fws = client.get("/api/frameworks").json()
    return fws[0]["id"]


def test_template_csv_downloadable(client):
    r = client.get("/api/frameworks/template.csv")
    assert r.status_code == 200
    assert "phrase,category,weight" in r.text
    assert "industrial_transformation" in r.text


def test_csv_happy_path(client):
    fid = _default_id(client)
    csv_data = (
        "phrase,category,weight,is_regex,companion_pattern,notes\n"
        "forklift density,supply_chain,4.0,false,,\n"
        "robotic palletizer,industrial_transformation,7.5,false,,\n"
        '"3PL handoff",supply_chain,5.0,false,,"client term"\n'
    )
    r = client.post(
        f"/api/frameworks/{fid}/keywords/import",
        files={"file": ("kw.csv", csv_data, "text/csv")},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["imported"] == 3
    assert payload["skipped"] == 0
    assert payload["errors"] == []


def test_csv_idempotent_dedupes(client):
    fid = _default_id(client)
    csv_data = (
        "phrase,category,weight\n"
        "forklift density,supply_chain,4.0\n"
        "forklift density,supply_chain,9.0\n"  # in-batch dupe
    )
    r = client.post(
        f"/api/frameworks/{fid}/keywords/import",
        files={"file": ("kw.csv", csv_data, "text/csv")},
    ).json()
    assert r["imported"] == 1
    assert r["skipped"] == 1

    # Re-uploading the same row again should be a no-op
    r2 = client.post(
        f"/api/frameworks/{fid}/keywords/import",
        files={"file": ("kw.csv", csv_data, "text/csv")},
    ).json()
    assert r2["imported"] == 0
    assert r2["skipped"] == 2


def test_csv_skips_bad_rows(client):
    fid = _default_id(client)
    csv_data = (
        "phrase,category,weight,is_regex,companion_pattern\n"
        ",supply_chain,3.0,false,\n"  # missing phrase
        "good,not_a_category,3.0,false,\n"  # invalid category
        "[bad-regex,industrial_transformation,3.0,true,\n"  # bad regex
        "good supplier,supply_chain,3.0,false,[bad,companion\n"  # bad companion
        "valid term,supply_chain,3.5,false,\n"  # ok
    )
    r = client.post(
        f"/api/frameworks/{fid}/keywords/import",
        files={"file": ("kw.csv", csv_data, "text/csv")},
    ).json()
    assert r["imported"] == 1
    assert r["skipped"] == 4
    reasons = " ".join(e["reason"] for e in r["errors"])
    assert "phrase and category" in reasons
    assert "unknown category" in reasons
    assert "bad regex" in reasons
    assert "bad companion regex" in reasons


def test_csv_missing_required_column_400(client):
    fid = _default_id(client)
    csv_data = "phrase,weight\nfoo,3.0\n"  # no category
    r = client.post(
        f"/api/frameworks/{fid}/keywords/import",
        files={"file": ("kw.csv", csv_data, "text/csv")},
    )
    assert r.status_code == 400
    assert "category" in r.json()["detail"]


def test_json_body_path(client):
    fid = _default_id(client)
    r = client.post(
        f"/api/frameworks/{fid}/keywords/import-json",
        json={
            "rows": [
                {"phrase": "automated retrieval system", "category": "industrial_transformation", "weight": 6.0},
                {"phrase": "trailer dwell time", "category": "supply_chain", "weight": 5.5},
            ]
        },
    ).json()
    assert r["imported"] == 2
    assert r["skipped"] == 0


def test_import_404_on_missing_framework(client):
    r = client.post(
        "/api/frameworks/nope/keywords/import",
        files={"file": ("kw.csv", "phrase,category\nfoo,supply_chain\n", "text/csv")},
    )
    assert r.status_code == 404
