"""Audio length detection for providers that need exact sound timings."""

from __future__ import annotations

import io

import mutagen


def audio_length_ms(data: bytes) -> int | None:
    """Duration of an mp3, wav, m4a or aac file in milliseconds, if readable."""
    try:
        audio = mutagen.File(io.BytesIO(data))
    except mutagen.MutagenError:
        return None
    length = getattr(getattr(audio, "info", None), "length", None)
    return int(length * 1000) if length else None
