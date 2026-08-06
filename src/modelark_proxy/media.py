from __future__ import annotations

import secrets
import time
from collections.abc import AsyncIterable
from pathlib import Path


class UploadTooLarge(ValueError):
    pass


def detect_media_type(
    header: bytes, filename: str | None, declared: str | None
) -> tuple[str, str]:
    lower_name = (filename or "").lower()
    if b"ftyp" in header[:64]:
        if b"qt  " in header[:64] or lower_name.endswith(".mov"):
            return "video/quicktime", ".mov"
        return "video/mp4", ".mp4"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif", ".gif"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp", ".webp"
    if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return "audio/wav", ".wav"
    if header.startswith((b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
        return "audio/mpeg", ".mp3"
    if declared in {"video/mp4", "video/quicktime"}:
        return declared, ".mp4" if declared == "video/mp4" else ".mov"
    if declared in {"audio/mpeg", "audio/mp3"} and lower_name.endswith(".mp3"):
        return "audio/mpeg", ".mp3"
    if declared in {"audio/wav", "audio/x-wav"} and lower_name.endswith(".wav"):
        return "audio/wav", ".wav"
    raise ValueError(
        "reference must be MP4/MOV video, PNG/JPEG/GIF/WEBP image, or MP3/WAV audio"
    )


class MediaStore:
    def __init__(self, directory: Path, max_bytes: int, ttl_seconds: int):
        self.directory = directory
        self.max_bytes = max_bytes
        self.ttl_seconds = ttl_seconds
        directory.mkdir(parents=True, exist_ok=True)

    async def save(
        self,
        chunks: AsyncIterable[bytes],
        *,
        filename: str | None,
        declared_type: str | None,
    ) -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        temp_path = self.directory / f".{token}.upload"
        total = 0
        header = bytearray()
        try:
            with temp_path.open("wb") as output:
                async for chunk in chunks:
                    total += len(chunk)
                    if total > self.max_bytes:
                        raise UploadTooLarge(f"Upload exceeds {self.max_bytes} bytes")
                    if len(header) < 64:
                        header.extend(chunk[: 64 - len(header)])
                    output.write(chunk)
            media_type, extension = detect_media_type(
                bytes(header), filename, declared_type
            )
            final_path = self.directory / f"{token}{extension}"
            temp_path.replace(final_path)
            return final_path.name, media_type
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    def resolve(self, name: str) -> Path | None:
        if Path(name).name != name or name.startswith("."):
            return None
        path = self.directory / name
        return path if path.is_file() else None

    def remove(self, name: str) -> bool:
        path = self.resolve(name)
        if not path:
            return False
        path.unlink()
        return True

    def cleanup(self) -> None:
        cutoff = time.time() - self.ttl_seconds
        for path in self.directory.iterdir():
            try:
                if path.is_file() and path.stat().st_mtime < cutoff:
                    path.unlink()
            except FileNotFoundError:
                pass
