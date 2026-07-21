"""
EVA Memory Manager
Category-keyed JSON store with remember/forget tool functions,
size-capping, and system-prompt serialization.
"""

import json
import time
from pathlib import Path
from typing import Any, Optional

_MEMORY_DIR = Path(__file__).resolve().parent.parent / "config"
_MEMORY_FILE = _MEMORY_DIR / "memory.json"
_MAX_ENTRIES_PER_CATEGORY = 50
_MAX_TOTAL_ENTRIES = 200


class MemoryManager:
    """Persistent memory store exposed as tool functions for the model."""

    _instance: Optional["MemoryManager"] = None

    def __new__(cls) -> "MemoryManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self) -> None:
        if self._loaded:
            return
        self._data: dict[str, list[dict[str, Any]]] = {}
        self._load()
        self._loaded = True

    # ── Tool-facing API ─────────────────────────────────────────

    def remember(self, key: str, value: str,
                 category: str = "general") -> str:
        """
        Store a memory entry. Called by the model via tool dispatch.
        Returns a confirmation string for the model.
        """
        if category not in self._data:
            self._data[category] = []

        # Update existing entry if key matches
        for entry in self._data[category]:
            if entry.get("key") == key:
                entry["value"] = value
                entry["updated_at"] = time.time()
                self._save()
                return f"Updated memory: [{category}] {key}"

        # New entry
        self._data[category].append({
            "key": key,
            "value": value,
            "created_at": time.time(),
            "updated_at": time.time(),
        })

        self._trim_category(category)
        self._trim_total()
        self._save()
        return f"Remembered: [{category}] {key} = {value}"

    def forget(self, key: str, category: str = "general") -> str:
        """
        Remove a memory entry. Called by the model via tool dispatch.
        Returns a confirmation string.
        """
        if category not in self._data:
            return f"No memories in category '{category}'."

        before = len(self._data[category])
        self._data[category] = [
            e for e in self._data[category] if e.get("key") != key
        ]

        if len(self._data[category]) == before:
            return f"No memory with key '{key}' in category '{category}'."

        if not self._data[category]:
            del self._data[category]

        self._save()
        return f"Forgot: [{category}] {key}"

    def recall(self, key: Optional[str] = None,
               category: Optional[str] = None) -> str:
        """Retrieve memories, optionally filtered by key and/or category."""
        results: list[str] = []

        categories = [category] if category else list(self._data.keys())
        for cat in categories:
            entries = self._data.get(cat, [])
            for entry in entries:
                if key is None or entry.get("key") == key:
                    results.append(
                        f"[{cat}] {entry['key']}: {entry['value']}"
                    )

        if not results:
            return "No matching memories found."
        return "\n".join(results)

    # ── System-prompt injection ─────────────────────────────────

    def format_memory_for_prompt(self) -> str:
        """
        Serialize all memories into a compact block suitable for
        injection into the system prompt at session start.
        """
        if not self._data:
            return "No memories stored yet."

        lines: list[str] = []
        for category, entries in sorted(self._data.items()):
            lines.append(f"## {category.title()}")
            for entry in entries:
                lines.append(f"- {entry['key']}: {entry['value']}")
            lines.append("")

        return "\n".join(lines).strip()

    def get_all(self) -> dict[str, list[dict[str, Any]]]:
        """Return raw memory data (read-only copy)."""
        return json.loads(json.dumps(self._data))

    def get_entry_count(self) -> int:
        return sum(len(v) for v in self._data.values())

    # ── Internal ────────────────────────────────────────────────

    def _trim_category(self, category: str) -> None:
        """Cap entries per category, removing oldest first."""
        entries = self._data.get(category, [])
        if len(entries) > _MAX_ENTRIES_PER_CATEGORY:
            entries.sort(key=lambda e: e.get("updated_at", 0))
            self._data[category] = entries[-_MAX_ENTRIES_PER_CATEGORY:]

    def _trim_total(self) -> None:
        """Cap total entries across all categories."""
        total = self.get_entry_count()
        if total <= _MAX_TOTAL_ENTRIES:
            return

        # Flatten, sort by age, remove oldest
        all_entries: list[tuple[str, dict]] = []
        for cat, entries in self._data.items():
            for entry in entries:
                all_entries.append((cat, entry))

        all_entries.sort(key=lambda x: x[1].get("updated_at", 0))
        to_remove = total - _MAX_TOTAL_ENTRIES

        for cat, entry in all_entries[:to_remove]:
            self._data[cat] = [
                e for e in self._data[cat]
                if e.get("key") != entry.get("key")
            ]
            if not self._data[cat]:
                del self._data[cat]

    def _load(self) -> None:
        _MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        if _MEMORY_FILE.exists():
            try:
                with open(_MEMORY_FILE, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        _MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        with open(_MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)


# Module-level singleton shortcut
memory = MemoryManager()
