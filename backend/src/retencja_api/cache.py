"""File-based cache for slow upstream responses and computed analyses."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from retencja_api.config import CACHE_DIR


def cache_path(namespace: str, key: str, suffix: str) -> Path:
    digest = hashlib.sha256(key.encode()).hexdigest()[:24]
    directory = CACHE_DIR / namespace
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{digest}{suffix}"


def read_json(namespace: str, key: str) -> Any | None:
    path = cache_path(namespace, key, ".json")
    if not path.exists():
        return None
    return json.loads(path.read_text())


def write_json(namespace: str, key: str, value: Any) -> None:
    path = cache_path(namespace, key, ".json")
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value))
    tmp.replace(path)


def cached_at(namespace: str, key: str) -> datetime | None:
    """When a cached response was written (= when the data was downloaded), if cached."""
    path = cache_path(namespace, key, ".json")
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, UTC)
