from __future__ import annotations

from .adapters.base import SourceAdapter


class AdapterRegistry:
    """Explicit adapter registry; applications can register new sources at runtime."""

    def __init__(self) -> None:
        self._adapters: dict[str, SourceAdapter] = {}

    def register(self, adapter: SourceAdapter) -> None:
        if adapter.adapter_id in self._adapters:
            raise ValueError(f"Adapter already registered: {adapter.adapter_id}")
        self._adapters[adapter.adapter_id] = adapter

    def get(self, adapter_id: str) -> SourceAdapter:
        try:
            return self._adapters[adapter_id]
        except KeyError as exc:
            raise KeyError(f"Unknown source adapter: {adapter_id}") from exc

    def adapter_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))

