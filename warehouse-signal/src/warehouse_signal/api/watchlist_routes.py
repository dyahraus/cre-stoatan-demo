"""Saved-watchlist CRUD."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from warehouse_signal.api.deps import get_storage
from warehouse_signal.models.schemas import Watchlist

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


class WatchlistCreate(BaseModel):
    name: str
    tickers: list[str] = []


class WatchlistUpdate(BaseModel):
    name: str | None = None
    tickers: list[str] | None = None


@router.get("")
def list_watchlists() -> list[dict]:
    return [w.model_dump(mode="json") for w in get_storage().list_watchlists()]


@router.get("/{watchlist_id}")
def get_watchlist(watchlist_id: str) -> dict:
    wl = get_storage().get_watchlist(watchlist_id)
    if not wl:
        raise HTTPException(404, f"Watchlist {watchlist_id} not found")
    return wl.model_dump(mode="json")


@router.post("", status_code=201)
def create_watchlist(req: WatchlistCreate) -> dict:
    storage = get_storage()
    now = datetime.now(timezone.utc)
    wl = Watchlist(
        id=str(uuid.uuid4()),
        name=req.name,
        tickers=[t.strip().upper() for t in req.tickers if t.strip()],
        created_at=now,
        updated_at=now,
    )
    storage.save_watchlist(wl)
    return wl.model_dump(mode="json")


@router.patch("/{watchlist_id}")
def update_watchlist(watchlist_id: str, req: WatchlistUpdate) -> dict:
    storage = get_storage()
    wl = storage.get_watchlist(watchlist_id)
    if not wl:
        raise HTTPException(404, f"Watchlist {watchlist_id} not found")
    if req.name is not None:
        wl.name = req.name
    if req.tickers is not None:
        wl.tickers = [t.strip().upper() for t in req.tickers if t.strip()]
    wl.updated_at = datetime.now(timezone.utc)
    storage.save_watchlist(wl)
    return wl.model_dump(mode="json")


@router.delete("/{watchlist_id}", status_code=204)
def delete_watchlist(watchlist_id: str) -> None:
    storage = get_storage()
    if not storage.get_watchlist(watchlist_id):
        raise HTTPException(404, f"Watchlist {watchlist_id} not found")
    storage.delete_watchlist(watchlist_id)
