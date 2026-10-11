"""Streaming of upstream results with per-hop host checks."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import AsyncIterator, Callable, Mapping
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from .validation import ContractError


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


def system_resolver(host: str) -> list[str]:
    return [info[4][0] for info in socket.getaddrinfo(host, 443)]


def is_public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


async def host_is_public(host: str, resolver: Callable[[str], list[str]]) -> bool:
    try:
        addresses = await asyncio.to_thread(resolver, host)
    except OSError:
        return False
    return bool(addresses) and all(is_public_address(address) for address in addresses)


async def safe_fetch(
    url: str,
    *,
    max_bytes: int,
    transport: httpx.AsyncBaseTransport | None,
    resolver: Callable[[str], list[str]] = system_resolver,
    timeout: float = 60.0,
    max_redirects: int = 3,
) -> tuple[bytes, str | None]:
    """Download a client-supplied URL without letting it reach private networks.

    Only https is allowed, and every hop (including redirects) must resolve
    to public addresses only.
    """
    async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
        for _ in range(max_redirects + 1):
            parsed = urlparse(url)
            if parsed.scheme != "https" or not parsed.hostname:
                raise ContractError(
                    "Reference URLs must use https",
                    code="reference_unavailable",
                    param="references",
                )
            if not await host_is_public(parsed.hostname, resolver):
                raise ContractError(
                    f"Reference host {parsed.hostname} is not publicly reachable",
                    code="reference_unavailable",
                    param="references",
                )
            async with client.stream("GET", url) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers["location"])
                    continue
                if response.is_error:
                    raise ContractError(
                        f"Reference download failed with HTTP {response.status_code}",
                        code="reference_unavailable",
                        param="references",
                    )
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > max_bytes:
                        raise ContractError(
                            f"Reference exceeds {max_bytes} bytes",
                            code="reference_limit",
                            param="references",
                        )
                return bytes(data), response.headers.get("content-type")
    raise ContractError(
        "Reference URL redirects too often",
        code="reference_unavailable",
        param="references",
    )
