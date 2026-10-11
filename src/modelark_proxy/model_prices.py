"""Model prices for the LiteLLM export (docs/SPEC.md, section 15).

`model_prices.yaml` maps model ID prefixes to LiteLLM cost fields; the longest
matching prefix wins, so `kling-3.0-turbo` beats `kling-3.0`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .providers import strip_model_namespace


class ModelPrices:
    def __init__(self, path: Path) -> None:
        self.prices: dict[str, dict[str, float]] = {}
        if not path.is_file():
            return
        entries = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get(
            "prices", []
        )
        for entry in entries:
            fields = {key: value for key, value in entry.items() if key != "model"}
            if not fields or not all(
                isinstance(value, int | float) for value in fields.values()
            ):
                raise ValueError(f"Invalid price entry for {entry.get('model')!r}")
            self.prices[entry["model"]] = {
                key: float(value) for key, value in fields.items()
            }

    def for_model(self, model: str) -> dict[str, Any]:
        bare = strip_model_namespace(model)
        matches = [prefix for prefix in self.prices if bare.startswith(prefix)]
        return dict(self.prices[max(matches, key=len)]) if matches else {}
