"""Video IDs in LiteLLM's managed format.

LiteLLM embeds the model into every video ID it hands out and routes follow-up
calls by it, but only the create response carries the model; status, remix,
edit, and extension responses encode an empty one, which LiteLLM then cannot
route back to this proxy. Returning IDs that are already encoded avoids this:
LiteLLM passes encoded IDs through unchanged and strips them back to our
internal ID before calling us.

The format must match LiteLLM's decoder exactly: standard base64 with padding.
"""

from __future__ import annotations

import base64
import binascii

VIDEO_ID_PREFIX = "video_"
_TEMPLATE = "litellm:custom_llm_provider:openai;model_id:{model};video_id:{video_id}"
# Standard base64 only emits "/" or "+" for these ASCII bytes. Without them an
# encoded ID is always safe inside a URL path segment.
_PATH_UNSAFE = frozenset("?>~\x7f;")


def encode_video_id(video_id: str, model: str | None) -> str:
    model = model or ""
    if video_id.startswith(VIDEO_ID_PREFIX) or not video_id.isascii():
        return video_id
    if not model.isascii() or _PATH_UNSAFE.intersection(video_id + model):
        return video_id
    raw = _TEMPLATE.format(model=model, video_id=video_id)
    return VIDEO_ID_PREFIX + base64.b64encode(raw.encode()).decode()


def decode_video_id(value: str) -> str:
    """Return the internal ID for an encoded or plain video ID."""
    if not value.startswith(VIDEO_ID_PREFIX):
        return value
    encoded = value[len(VIDEO_ID_PREFIX) :]
    encoded += "=" * (-len(encoded) % 4)
    try:
        decoded = base64.b64decode(encoded, validate=True).decode()
    except (binascii.Error, UnicodeDecodeError):
        return value
    for part in decoded.split(";"):
        if part.startswith("video_id:"):
            return part[len("video_id:") :]
    return value
