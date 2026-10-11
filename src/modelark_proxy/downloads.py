"""Streaming of upstream results with per-hop host checks."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse


def host_allowed(url: str, allowed_host_suffixes: list[str]) -> bool:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and any(
        hostname == suffix.lstrip(".").lower() or hostname.endswith(suffix.lower())
        for suffix in allowed_host_suffixes
    )


async def stream_remote(
    url: str,
    *,
    headers: Mapping[str, str],
    allowed_host_suffixes: list[str],
    transport: httpx.AsyncBaseTransport | None,
    timeout: float,
    media_type: str | None = None,
    max_redirects: int = 5,
) -> StreamingResponse:
    """Stream an upstream file, following only redirects to allowed hosts.

    Credentials go to the first host only; signed CDN redirects get none.
    """
    client = httpx.AsyncClient(timeout=timeout, transport=transport)
    request_headers = dict(headers)
    try:
        for _ in range(max_redirects + 1):
            if not host_allowed(url, allowed_host_suffixes):
                raise HTTPException(
                    status_code=502,
                    detail="Upstream returned a disallowed download URL",
                )
            response = await client.send(
                client.build_request("GET", url, headers=request_headers), stream=True
            )
            if response.is_redirect:
                await response.aclose()
                next_url = urljoin(url, response.headers["location"])
                if urlparse(next_url).hostname != urlparse(url).hostname:
                    request_headers = {}
                url = next_url
                continue
            if response.is_error:
                await response.aclose()
                raise HTTPException(
                    status_code=502,
                    detail=f"Upstream download failed with HTTP {response.status_code}",
                )
            break
        else:
            raise HTTPException(status_code=502, detail="Too many upstream redirects")
    except BaseException:
        await client.aclose()
        raise

    async def body() -> AsyncIterator[bytes]:
        try:
            async for chunk in response.aiter_bytes():
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()

    content_type = media_type or response.headers.get("content-type", "").split(";")[0]
    return StreamingResponse(body(), media_type=content_type or None)
