"""Reference resolution: every source works for providers that need bytes (T10)."""

from __future__ import annotations

import base64
from pathlib import Path

import httpx
import pytest

from modelark_proxy.config import Settings
from modelark_proxy.media import MediaStore
from modelark_proxy.outputs import OutputStore
from modelark_proxy.provider_jobs import ProviderJobStore
from modelark_proxy.references import ReferenceResolver
from modelark_proxy.validation import ContractError

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
MP4 = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 32


async def chunks(data: bytes):
    yield data


def public(host: str) -> list[str]:
    return ["93.184.216.34"]


@pytest.fixture
def parts(tmp_path: Path):
    settings = Settings(
        public_base_url="https://proxy.example.com",
        media_dir=tmp_path / "media",
        provider_job_db=tmp_path / "jobs.db",
        output_dir=tmp_path / "outputs",
        max_inline_reference_bytes=64,
    )
    media = MediaStore(settings.media_dir, settings.max_upload_bytes, 3600)
    jobs = ProviderJobStore(settings.provider_job_db, ttl_seconds=3600)
    outputs = OutputStore(settings.output_dir)
    return settings, media, jobs, outputs


def resolver_for(parts, handler=None, resolve=public) -> ReferenceResolver:
    settings, media, jobs, outputs = parts
    transport = httpx.MockTransport(handler or (lambda r: httpx.Response(500)))
    return ReferenceResolver(
        settings, media, jobs, outputs, transport=transport, resolver=resolve
    )


async def test_data_uri_is_decoded_and_its_type_verified(parts):
    resolved = await resolver_for(parts).fetch(
        {
            "type": "image",
            "url": "data:image/png;base64," + base64.b64encode(PNG).decode(),
        }
    )

    assert resolved.data == PNG
    assert resolved.mime_type == "image/png"


async def test_declared_type_must_match_the_content(parts):
    with pytest.raises(ContractError) as error:
        await resolver_for(parts).fetch(
            {
                "type": "image",
                "url": "data:image/png;base64," + base64.b64encode(MP4).decode(),
            }
        )
    assert error.value.code == "reference_limit"


async def test_oversized_data_uri_is_rejected(parts):
    with pytest.raises(ContractError) as error:
        await resolver_for(parts).fetch(
            {
                "type": "image",
                "url": "data:image/png;base64," + base64.b64encode(PNG * 4).decode(),
            }
        )
    assert error.value.code == "reference_limit"


async def test_uploads_and_own_media_urls_are_read_locally(parts):
    _, media, _, _ = parts
    name, _ = await media.save(chunks(PNG), filename="a.png", declared_type="image/png")
    resolver = resolver_for(parts)

    by_id = await resolver.fetch({"type": "image", "upload_id": name})
    by_url = await resolver.fetch(
        {"type": "image", "url": f"https://proxy.example.com/media/reference/{name}"}
    )

    assert by_id.data == by_url.data == PNG


async def test_external_https_urls_are_downloaded(parts):
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.path == "/start.png":
            return httpx.Response(
                302, headers={"location": "https://cdn.example.org/real.png"}
            )
        return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})

    resolved = await resolver_for(parts, handler).fetch(
        {"type": "image", "url": "https://images.example.org/start.png"}
    )

    assert resolved.data == PNG
    assert seen == [
        "https://images.example.org/start.png",
        "https://cdn.example.org/real.png",
    ]


@pytest.mark.parametrize(
    "url", ["http://images.example.org/a.png", "https://internal.example.org/a.png"]
)
async def test_unsafe_urls_are_never_fetched(parts, url):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=PNG)

    resolver = resolver_for(parts, handler, resolve=lambda host: ["10.1.2.3"])
    with pytest.raises(ContractError) as error:
        await resolver.fetch({"type": "image", "url": url})

    assert error.value.code == "reference_unavailable"
    assert seen == []


async def test_redirects_to_private_addresses_are_refused(parts):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://metadata.internal/x"})

    resolver = resolver_for(
        parts,
        handler,
        resolve=lambda host: (
            ["169.254.169.254"] if host == "metadata.internal" else ["93.184.216.34"]
        ),
    )
    with pytest.raises(ContractError) as error:
        await resolver.fetch(
            {"type": "image", "url": "https://images.example.org/a.png"}
        )
    assert error.value.code == "reference_unavailable"


async def test_outputs_of_earlier_jobs_can_be_reused(parts):
    _, _, jobs, outputs = parts
    job = jobs.create("google", "veo", "text_to_video", {}, slug="veo")
    await outputs.save(job["id"], 0, "video", chunks(MP4), "video/mp4")
    jobs.update(
        job["id"],
        status="completed",
        outputs=[{"index": 0, "stored": True, "mime_type": "video/mp4"}],
    )

    resolved = await resolver_for(parts).fetch({"type": "video", "task_id": job["id"]})

    assert resolved.data == MP4
    assert resolved.mime_type == "video/mp4"


async def test_unknown_or_unfinished_jobs_are_unavailable(parts):
    _, _, jobs, _ = parts
    job = jobs.create("google", "veo", "text_to_video", {}, slug="veo")

    with pytest.raises(ContractError) as error:
        await resolver_for(parts).fetch({"type": "video", "task_id": job["id"]})
    assert error.value.code == "reference_unavailable"
