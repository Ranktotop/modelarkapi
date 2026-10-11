"""Prompt guides per model family (docs/SPEC.md, section 14).

`prompt_guides/manifest.yaml` lists each guide with the model ID prefixes it
covers; the longest matching prefix wins, so a variant-specific guide beats a
family-wide one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .providers import strip_model_namespace


@dataclass(frozen=True)
class PromptGuide:
    id: str
    file: str
    title: str
    language: str
    updated: str
    models: tuple[str, ...]
    path: Path

    def markdown(self) -> str:
        return self.path.read_text(encoding="utf-8")

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "language": self.language,
            "updated": self.updated,
            "models": list(self.models),
            "url": f"/v1/prompt-guides/{self.id}",
        }


class PromptGuides:
    def __init__(self, directory: Path) -> None:
        self.guides: dict[str, PromptGuide] = {}
        manifest = directory / "manifest.yaml"
        if not manifest.is_file():
            return
        entries = (yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}).get(
            "guides", []
        )
        for entry in entries:
            path = (directory / entry["file"]).resolve()
            if path.parent != directory.resolve() or not path.is_file():
                raise ValueError(f"Prompt guide file not found: {entry['file']}")
            updated = entry.get("updated")
            self.guides[entry["id"]] = PromptGuide(
                id=entry["id"],
                file=entry["file"],
                title=entry.get("title", entry["id"]),
                language=entry.get("language", "de"),
                updated=updated.isoformat()
                if isinstance(updated, date)
                else str(updated or ""),
                models=tuple(entry.get("models", [])),
                path=path,
            )

    def all(self) -> list[PromptGuide]:
        return list(self.guides.values())

    def get(self, guide_id: str) -> PromptGuide | None:
        return self.guides.get(guide_id)

    def for_model(self, model: str) -> PromptGuide | None:
        bare = strip_model_namespace(model)
        best: tuple[int, PromptGuide] | None = None
        for guide in self.guides.values():
            for prefix in guide.models:
                if bare.startswith(prefix) and (best is None or len(prefix) > best[0]):
                    best = (len(prefix), guide)
        return best[1] if best else None
