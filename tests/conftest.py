from __future__ import annotations

import pytest

from modelark_proxy.config import Settings

# Provider credentials that would otherwise leak in from a developer's shell.
_PROVIDER_ENV = (
    "ARK_API_KEY",
    "BYTEPLUS_ACCESS_KEY_ID",
    "BYTEPLUS_SECRET_ACCESS_KEY",
    "PROXY_API_KEY",
    "GEMINI_API_KEY",
    "VERTEX_PROJECT",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "KLING_API_KEY",
    "WEBHOOK_SECRET",
)


@pytest.fixture(autouse=True)
def hermetic_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests independent of the developer's .env and real credentials."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for name in _PROVIDER_ENV:
        monkeypatch.delenv(name, raising=False)
