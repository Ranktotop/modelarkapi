"""End-to-end compatibility with a real LiteLLM proxy (T28, docs/SPEC.md 15).

LiteLLM runs as a subprocess from a separate virtualenv in front of this proxy,
whose providers are scripted fakes; nothing reaches a real provider. The suite
is opt-in because it needs those virtualenvs:

    LITELLM_VENVS=/path/to/venv-1.104.2:/path/to/venv-1.105.0 pytest -m litellm

Each venv needs `litellm[proxy]` installed. LiteLLM is configured with the
proxy's own `/v1/litellm/config` export, so the export is tested as well.
"""

from __future__ import annotations

import os
import socket
import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
import yaml

from modelark_proxy.app import create_app
from modelark_proxy.config import Settings

from .fake_upstream import MP3, SEEDANCE_VIDEO_URL, VIDEO, FakeUpstream

VENVS = [Path(p) for p in os.environ.get("LITELLM_VENVS", "").split(os.pathsep) if p]
MASTER_KEY = "sk-integration"
MODELS = {
    "seedance": "dreamina-seedance-2-5-260628",
    "veo": "veo-3.1-fast-generate-preview",
    "kling": "kling-3.0",
    "tts": "kling-tts",
}

pytestmark = [
    pytest.mark.litellm,
    pytest.mark.skipif(not VENVS, reason="set LITELLM_VENVS to run the LiteLLM suite"),
]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Stack:
    """This proxy (in a thread) and one LiteLLM proxy (a subprocess)."""

    def __init__(self, venv: Path, workdir: Path) -> None:
        self.fake = FakeUpstream()
        self.proxy_port = free_port()
        proxy_url = f"http://127.0.0.1:{self.proxy_port}"
        settings = Settings(
            ark_api_key="ark-test",
            byteplus_access_key_id="ak-test",
            byteplus_secret_access_key="sk-test",
            gemini_api_key="gemini-key",
            google_veo_backend="gemini",
            google_omni_backend="none",
            kling_api_key="kling-key",
            proxy_api_key=None,
            require_proxy_api_key=False,
            public_base_url=proxy_url,
            media_dir=workdir / "media",
            asset_job_db=workdir / "asset-jobs.db",
            provider_job_db=workdir / "provider-jobs.db",
            output_dir=workdir / "outputs",
            provider_poll_interval_seconds=0.2,
            provider_status_min_interval_seconds=0,
        )
        transport = httpx.MockTransport(self.fake)
        app = create_app(
            settings,
            ark_transport=transport,
            asset_transport=transport,
            download_transport=transport,
            google_transport=transport,
            kling_transport=transport,
            validate_startup_credentials=False,
        )
        self.server = uvicorn.Server(
            uvicorn.Config(
                app, host="127.0.0.1", port=self.proxy_port, log_level="warning"
            )
        )
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        wait_until(lambda: self.server.started, "the proxy did not start")

        config = httpx.get(
            f"{proxy_url}/v1/litellm/config",
            params={"format": "json", "api_base": f"{proxy_url}/v1"},
        ).json()
        self.names = {
            entry["litellm_params"]["model"].removeprefix("openai/"): entry[
                "model_name"
            ]
            for entry in config["model_list"]
        }
        config["general_settings"] = {"master_key": MASTER_KEY}
        config_path = workdir / "litellm.yaml"
        config_path.write_text(yaml.safe_dump(config))

        self.litellm_port = free_port()
        self.log = (workdir / "litellm.log").open("w")
        self.process = subprocess.Popen(
            [
                str(venv / "bin" / "litellm"),
                "--config",
                str(config_path),
                "--host",
                "127.0.0.1",
                "--port",
                str(self.litellm_port),
            ],
            cwd=workdir,
            env={**os.environ, "MODELARK_PROXY_API_KEY": "unused"},
            stdout=self.log,
            stderr=subprocess.STDOUT,
        )
        self.client = httpx.Client(
            base_url=f"http://127.0.0.1:{self.litellm_port}",
            headers={"Authorization": f"Bearer {MASTER_KEY}"},
            timeout=30,
        )
        wait_until(self._litellm_ready, "LiteLLM did not start", timeout=120)

    def _litellm_ready(self) -> bool:
        if self.process.poll() is not None:
            raise RuntimeError(f"LiteLLM exited with {self.process.returncode}")
        try:
            return self.client.get("/health/liveliness").status_code == 200
        except httpx.TransportError:
            return False

    def name(self, key: str) -> str:
        return self.names[MODELS[key]]

    def finish(self, video_id: str) -> dict[str, Any]:
        """Poll the status through LiteLLM until the video is done."""
        body: dict[str, Any] = {}

        def done() -> bool:
            nonlocal body
            response = self.client.get(f"/v1/videos/{video_id}")
            assert response.status_code == 200, response.text
            body = response.json()
            return body["status"] in {"completed", "failed"}

        wait_until(done, f"{video_id} did not finish", timeout=20)
        return body

    def close(self) -> None:
        self.client.close()
        self.process.terminate()
        try:
            self.process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.process.kill()
        self.log.close()
        self.server.should_exit = True
        self.thread.join(timeout=10)


def wait_until(check, message: str, timeout: float = 15) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.25)
    raise TimeoutError(message)


@pytest.fixture(scope="module", params=VENVS, ids=lambda venv: venv.name)
def stack(request, tmp_path_factory) -> Iterator[Stack]:
    stack = Stack(request.param, tmp_path_factory.mktemp("litellm"))
    yield stack
    stack.close()


def test_model_info_carries_guides_and_capabilities(stack: Stack):
    response = stack.client.get("/v1/model/info")

    assert response.status_code == 200, response.text
    infos = {
        entry["model_name"]: entry["model_info"] for entry in response.json()["data"]
    }
    for key in MODELS:
        info = infos[stack.name(key)]
        assert info["prompt_guide"].startswith("# "), key
        assert info["capabilities"]["provider"] in {"modelark", "google", "kling"}
    assert infos[stack.name("tts")]["mode"] == "audio_speech"


@pytest.mark.parametrize(
    ("key", "seconds", "extra", "upstream_host", "upstream_check"),
    [
        (
            "seedance",
            "5",
            {"generate_audio": False, "seed": 7},
            "ark.",
            lambda body: body["generate_audio"] is False and body["seed"] == 7,
        ),
        (
            "veo",
            "8",
            {"seed": 7},
            "googleapis.com",
            lambda body: body["parameters"]["seed"] == 7,
        ),
        (
            "kling",
            "5",
            {"negative_prompt": "blur"},
            "klingai.com",
            lambda body: body["negative_prompt"] == "blur",
        ),
    ],
)
def test_json_create_status_and_content(
    stack: Stack, key, seconds, extra, upstream_host, upstream_check
):
    created = stack.client.post(
        "/v1/videos",
        json={
            "model": stack.name(key),
            "prompt": "a fox runs",
            "seconds": seconds,
            **extra,
        },
    )

    assert created.status_code == 200, created.text
    video_id = created.json()["id"]
    assert video_id.startswith("video_")
    assert upstream_check(stack.fake.created(upstream_host)[-1])
    assert stack.finish(video_id)["status"] == "completed"
    content = stack.client.get(f"/v1/videos/{video_id}/content")
    assert content.status_code == 200, content.text
    assert content.content == VIDEO


def test_multipart_create_reaches_the_provider_like_json(stack: Stack):
    fields = {
        "model": stack.name("seedance"),
        "prompt": "a fox runs",
        "seconds": "5",
        "generate_audio": "false",
    }

    json_call = stack.client.post(
        "/v1/videos", json={**fields, "generate_audio": False}
    )
    json_body = stack.fake.created("ark.")[-1]
    form_call = stack.client.post(
        "/v1/videos", files=[(name, (None, value)) for name, value in fields.items()]
    )
    form_body = stack.fake.created("ark.")[-1]

    assert json_call.status_code == 200, json_call.text
    assert form_call.status_code == 200, form_call.text
    assert form_body == json_body


def test_remix_edits_the_source_video(stack: Stack):
    created = stack.client.post(
        "/v1/videos", json={"model": stack.name("seedance"), "prompt": "a fox"}
    )
    video_id = created.json()["id"]
    stack.finish(video_id)

    remix = stack.client.post(
        f"/v1/videos/{video_id}/remix", json={"prompt": "make it snow"}
    )

    assert remix.status_code == 200, remix.text
    body = stack.fake.created("ark.")[-1]
    assert body["omni_reference_task_type"] == "edit"
    assert body["content"][-1]["video_url"]["url"] == SEEDANCE_VIDEO_URL


def test_speech_returns_the_audio(stack: Stack):
    response = stack.client.post(
        "/v1/audio/speech",
        json={
            "model": stack.name("tts"),
            "input": "Hallo Welt",
            "voice": "oversea_male1",
        },
    )

    assert response.status_code == 200, response.text
    assert response.content == MP3


@pytest.mark.parametrize(
    ("route", "body", "task"),
    [
        ("/v1/videos/edits", {"prompt": "make it snow"}, "edit"),
        # LiteLLM requires `seconds` for extensions.
        ("/v1/videos/extensions", {"prompt": "go on", "seconds": "auto"}, "extend"),
    ],
)
def test_edits_and_extensions_reach_the_provider(stack: Stack, route, body, task):
    created = stack.client.post(
        "/v1/videos", json={"model": stack.name("seedance"), "prompt": "a fox"}
    )
    video_id = created.json()["id"]
    stack.finish(video_id)

    response = stack.client.post(
        route, json={"model": stack.name("seedance"), "video": {"id": video_id}, **body}
    )

    assert response.status_code == 200, response.text
    upstream = stack.fake.created("ark.")[-1]
    assert upstream["omni_reference_task_type"] == task
    assert upstream["content"][-1]["video_url"]["url"] == SEEDANCE_VIDEO_URL


def test_characters_pass_through(stack: Stack):
    created = stack.client.post(
        "/v1/videos/characters",
        data={"name": "Mia", "model": stack.name("kling")},
        files={"video": ("mia.mp4", VIDEO, "video/mp4")},
    )

    assert created.status_code == 200, created.text
    assert created.json()["id"].startswith("character_")
    fetched = stack.client.get(
        f"/v1/videos/characters/{created.json()['id']}",
        params={"model": stack.name("kling")},
    )
    assert fetched.status_code == 200, fetched.text
