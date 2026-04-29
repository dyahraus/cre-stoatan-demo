"""Framework CRUD + duplicate + last-delete guard tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "ws.db"))
    from warehouse_signal.api.server import app

    with TestClient(app) as c:
        yield c


def test_create_then_list(client):
    r = client.post("/api/frameworks", json={"name": "Retail v1"})
    assert r.status_code == 201
    new_id = r.json()["id"]
    assert new_id != ""

    r = client.get("/api/frameworks")
    assert r.status_code == 200
    names = {fw["name"] for fw in r.json()}
    assert "Retail v1" in names
    # Default seed should still be present alongside the new one
    assert any(fw["is_default"] for fw in r.json())


def test_duplicate_clones_keywords(client):
    fws = client.get("/api/frameworks").json()
    src = fws[0]
    src_kw_count = len(src["keywords"])
    assert src_kw_count > 0

    r = client.post(
        f"/api/frameworks/{src['id']}/duplicate",
        json={"name": "Retail v2"},
    )
    assert r.status_code == 201
    cloned = r.json()
    assert cloned["name"] == "Retail v2"
    assert len(cloned["keywords"]) == src_kw_count
    # New keyword IDs, same content
    src_phrases = {kw["phrase"] for kw in src["keywords"]}
    cloned_phrases = {kw["phrase"] for kw in cloned["keywords"]}
    assert src_phrases == cloned_phrases
    src_kw_ids = {kw["id"] for kw in src["keywords"]}
    cloned_kw_ids = {kw["id"] for kw in cloned["keywords"]}
    assert src_kw_ids.isdisjoint(cloned_kw_ids)


def test_patch_renames_and_updates_default(client):
    new = client.post("/api/frameworks", json={"name": "Tmp"}).json()
    fid = new["id"]

    # Rename
    r = client.patch(f"/api/frameworks/{fid}", json={"name": "Renamed"})
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"

    # Promote to default — should clear is_default on the seeded one
    r = client.patch(f"/api/frameworks/{fid}", json={"is_default": True})
    assert r.status_code == 200
    assert r.json()["is_default"] is True

    fws = client.get("/api/frameworks").json()
    defaults = [f for f in fws if f["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == fid


def test_delete_works_when_more_than_one_exists(client):
    a = client.post("/api/frameworks", json={"name": "A"}).json()
    fid = a["id"]
    r = client.delete(f"/api/frameworks/{fid}")
    assert r.status_code == 204
    fws = client.get("/api/frameworks").json()
    assert all(f["id"] != fid for f in fws)


def test_delete_blocked_when_only_one_remains(client):
    fws = client.get("/api/frameworks").json()
    # Whittle down to 1
    for f in fws[1:]:
        client.delete(f"/api/frameworks/{f['id']}")
    fws = client.get("/api/frameworks").json()
    assert len(fws) == 1

    last = fws[0]
    r = client.delete(f"/api/frameworks/{last['id']}")
    assert r.status_code == 409
    assert "only framework" in r.json()["detail"]


def test_404_on_missing(client):
    assert client.get("/api/frameworks/missing").status_code == 404
    assert (
        client.patch("/api/frameworks/missing", json={"name": "x"}).status_code
        == 404
    )
    assert client.delete("/api/frameworks/missing").status_code == 404
    assert (
        client.post(
            "/api/frameworks/missing/duplicate", json={"name": "x"}
        ).status_code
        == 404
    )


def test_keyword_crud_through_api(client):
    fws = client.get("/api/frameworks").json()
    fid = fws[0]["id"]

    r = client.post(
        f"/api/frameworks/{fid}/keywords",
        json={"category": "industrial_transformation", "phrase": "ai-augmented", "weight": 6.0},
    )
    assert r.status_code == 201
    kid = r.json()["id"]

    r = client.patch(
        f"/api/frameworks/{fid}/keywords/{kid}",
        json={"weight": 8.5},
    )
    assert r.status_code == 200
    assert r.json()["weight"] == 8.5

    r = client.delete(f"/api/frameworks/{fid}/keywords/{kid}")
    assert r.status_code == 204
