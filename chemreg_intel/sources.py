from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import SourceRecord


class SourceRegistry:
    """Small local registry that keeps source metadata independent of evidence rows."""

    def __init__(self) -> None:
        self._sources: dict[str, SourceRecord] = {}

    def register(self, key: str, source: SourceRecord) -> None:
        if key in self._sources and self._sources[key] != source:
            raise ValueError(f"Source key already registered with different metadata: {key}")
        self._sources[key] = source

    def get(self, key: str) -> SourceRecord:
        return self._sources[key]

    def values(self) -> list[SourceRecord]:
        return list(self._sources.values())

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps({key: asdict(value) for key, value in self._sources.items()}, indent=2), encoding="utf-8")

