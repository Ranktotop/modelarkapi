"""LiteLLM `model_list` export (docs/SPEC.md, section 15).

Apps reach capabilities and prompt guides through LiteLLM's
`GET /v1/model/info`, which returns each deployment's `model_info`, so the
export puts both there.
"""

from __future__ import annotations

import re
from typing import Any

from .prompt_guides import PromptGuides

VENDOR_PREFIXES = ("dreamina-", "bytedance-")
DROPPED_TOKENS = {"generate"}
AUDIO_SPEECH_MODELS = {"kling-tts"}


def family_slug(family: str) -> str:
    """`dreamina-seedance-2-0-fast` → `seedance_20_fast` (the existing LiteLLM naming)."""
    name = family.lower()
    for prefix in VENDOR_PREFIXES:
        name = name.removeprefix(prefix)
    parts: list[str] = []
    for token in name.split("-"):
        if token in DROPPED_TOKENS or not token:
            continue
        token = token.replace(".", "")
        if token.isdigit() and parts and parts[-1].isdigit():
            parts[-1] += token
        else:
            parts.append(token)
    return "_".join(parts)


def export_model_list(
    models: list[dict[str, Any]],
    guides: PromptGuides,
    *,
    api_base: str,
    public_base_url: str | None,
    name_template: str = "{family_slug}_api",
) -> dict[str, Any]:
    entries = []
    for model in models:
        capabilities = model.get("capabilities") or {}
        family = capabilities.get("family") or re.sub(r"-\d{4,10}$", "", model["id"])
        guide = guides.for_model(model["id"])
        guide_url = None
        if guide and public_base_url:
            guide_url = f"{public_base_url.rstrip('/')}/v1/prompt-guides/{guide.id}"
        entries.append(
            {
                "model_name": name_template.format(
                    family_slug=family_slug(family), model=model["id"]
                ),
                "litellm_params": {
                    "model": f"openai/{model['id']}",
                    "api_base": api_base,
                    "api_key": "os.environ/MODELARK_PROXY_API_KEY",
                },
                "model_info": {
                    "mode": "audio_speech"
                    if model["id"] in AUDIO_SPEECH_MODELS
                    else "video_generation",
                    "provider": capabilities.get("provider", model.get("owned_by")),
                    "capabilities": capabilities,
                    "prompt_guide": guide.markdown() if guide else None,
                    "prompt_guide_url": guide_url,
                },
            }
        )
    return {"model_list": entries}
