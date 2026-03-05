"""Shared dependencies for API routes."""

from warehouse_signal.storage.sqlite import Storage

_storage: Storage | None = None


def init_storage() -> None:
    global _storage
    _storage = Storage()


def close_storage() -> None:
    global _storage
    _storage = None


def get_storage() -> Storage:
    assert _storage is not None, "Storage not initialized"
    return _storage
