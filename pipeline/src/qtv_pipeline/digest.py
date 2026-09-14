"""Canonical form and content digest for the snapshot.

Two builds over an identical mirror must produce the same content_digest even
though generated_at and the per-run request/byte counters differ. Those
volatile fields are stripped before hashing; everything else, including field
order (via sort_keys), is canonicalized.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

_VOLATILE_SOURCE_KEYS = {"fetched_at", "requests", "bytes", "mode"}


def _strip_volatile(doc: dict[str, Any]) -> dict[str, Any]:
    stripped = {k: v for k, v in doc.items() if k != "generated_at"}
    stripped["build"] = {k: v for k, v in stripped["build"].items() if k != "run"}
    stripped["sources"] = {
        name: {k: v for k, v in src.items() if k not in _VOLATILE_SOURCE_KEYS}
        for name, src in stripped["sources"].items()
    }
    return stripped


def canonical_bytes(doc: dict[str, Any]) -> bytes:
    stripped = _strip_volatile(doc)
    return json.dumps(stripped, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def content_digest(doc: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(doc)).hexdigest()


def file_digest(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()
