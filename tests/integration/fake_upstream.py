"""Scripted ModelArk, Gemini and Kling upstreams for the LiteLLM suite.

Every task finishes on its first status poll, so a test can walk the whole
create → status → content path through LiteLLM without waiting.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

VIDEO = b"\x00\x00\x00\x20ftypisomintegration-video"
MP3 = b"ID3\x03\x00\x00\x00integration-mp3"
SEEDANCE_MODEL = "dreamina-seedance-2-5-260628"
SEEDANCE_VIDEO_URL = "https://ark-output.bytepluses.com/out.mp4"
GEMINI_HOST = "generativelanguage.googleapis.com"
KLING_CDN = "v1-kling.klingai.com"


class FakeUpstream:
    """One handler for every provider; `requests` keeps what reached them."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def created(self, host_part: str) -> list[dict[str, Any]]:
        return [
            json.loads(r.content)
            for r in self.requests
            if r.method == "POST" and host_part in r.url.host and r.content
        ]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        host = request.url.host
        if "bytepluses.com" in host and host.startswith("ark-output"):
            return httpx.Response(
                200, content=VIDEO, headers={"content-type": "video/mp4"}
            )
        if "Action" in request.url.params:
            return self._management(request)
        if host.startswith("ark."):
            return self._modelark(request)
        if host == GEMINI_HOST:
            return self._gemini(request)
        if host == KLING_CDN:
            content = MP3 if request.url.path.endswith(".mp3") else VIDEO
            return httpx.Response(200, content=content)
        if "klingai.com" in host:
            return self._kling(request)
        return httpx.Response(404, json={"error": f"unexpected {request.url}"})

    def _modelark(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"id": "cgt-int-1"})
        task_id = request.url.path.rsplit("/", 1)[-1]
        if request.method == "DELETE":
            return httpx.Response(200, json={})
        return httpx.Response(
            200,
            json={
                "id": task_id,
                "model": SEEDANCE_MODEL,
                "status": "succeeded",
                "duration": 5,
                "resolution": "720p",
                "ratio": "16:9",
                "content": {"video_url": SEEDANCE_VIDEO_URL},
            },
        )

    def _management(self, request: httpx.Request) -> httpx.Response:
        if request.url.params.get("Action") == "ListModelActivations":
            items = [
                {
                    "FoundationModelName": "dreamina-seedance-2-5",
                    "DisplayName": "Dreamina-Seedance-2.5",
                    "State": "Available",
                }
            ]
        else:
            items = [
                {
                    "FoundationModelName": "dreamina-seedance-2-5",
                    "ModelVersion": "260628",
                    "Status": "Published",
                }
            ]
        return httpx.Response(200, json={"Result": {"Items": items}})

    def _gemini(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/models"):
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "models/veo-3.1-fast-generate-preview",
                            "supportedGenerationMethods": ["predictLongRunning"],
                        }
                    ]
                },
            )
        if path.endswith(":predictLongRunning"):
            model = path.rsplit("/", 1)[-1].split(":")[0]
            return httpx.Response(200, json={"name": f"models/{model}/operations/op-1"})
        if "/operations/" in path:
            return httpx.Response(
                200,
                json={
                    "name": "op-1",
                    "done": True,
                    "response": {
                        "generateVideoResponse": {
                            "generatedSamples": [
                                {
                                    "video": {
                                        "uri": f"https://{GEMINI_HOST}/v1beta/files/abc:download?alt=media"
                                    }
                                }
                            ]
                        }
                    },
                },
            )
        if path.endswith(":download"):
            return httpx.Response(
                200, content=VIDEO, headers={"content-type": "video/mp4"}
            )
        return httpx.Response(404, json={"error": {"message": f"unexpected {path}"}})

    def _kling(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        ok = lambda data: httpx.Response(
            200, json={"code": 0, "message": "SUCCEED", "data": data}
        )
        if path == "/v1/audio/tts":
            return ok(
                {
                    "task_id": "A",
                    "task_status": "succeed",
                    "task_result": {
                        "audios": [
                            {
                                "id": "aud-1",
                                "url": f"https://{KLING_CDN}/a.mp3",
                                "duration": "2.1",
                            }
                        ]
                    },
                }
            )
        if request.method == "POST":
            return ok({"task_id": "k1", "task_status": "submitted"})
        return ok(
            {
                "task_id": "k1",
                "task_status": "succeed",
                "task_result": {
                    "videos": [
                        {
                            "id": "v1",
                            "url": f"https://{KLING_CDN}/r.mp4",
                            "duration": "5.04",
                        }
                    ]
                },
            }
        )
