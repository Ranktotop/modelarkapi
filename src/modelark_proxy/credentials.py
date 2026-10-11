"""Credential health per provider.

Every configured provider is validated with a free, read-only upstream call.
A provider whose credentials are invalid only blocks requests to itself; a
provider without any configured credentials is `disabled`. A network failure
says nothing about a credential, so it never invalidates one that already
worked.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import httpx

from .assets import AssetAPIError, AssetClient
from .client import ModelArkClient, ModelArkError
from .config import Settings
from .google_auth import TokenSource
from .providers import ProviderUnavailable

logger = logging.getLogger(__name__)

LABELS = {"modelark": "ModelArk", "google": "Google", "kling": "Kling"}

# (component, error message or None, unreachable)
ComponentResult = tuple[str, str | None, bool]
Check = Callable[[], Awaitable[list[ComponentResult]]]


class ProviderCredentialsError(RuntimeError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


async def _guarded(
    timeout: float,
    label: str,
    upstream: str,
    call: Callable[[], Awaitable[str | None]],
) -> tuple[str | None, bool]:
    try:
        async with asyncio.timeout(timeout):
            return await call(), False
    except TimeoutError:
        return f"{label} validation timed out", True
    except httpx.HTTPError:
        return f"{label} validation could not reach {upstream}", True
    except Exception:
        logger.exception("Unexpected %s validation failure", label)
        return f"{label} validation failed unexpectedly", False


def modelark_check(
    settings: Settings, ark: ModelArkClient, assets: AssetClient
) -> Check:
    timeout = settings.credential_validation_timeout_seconds

    async def ark_api_key() -> tuple[str | None, bool]:
        if not settings.ark_api_key:
            return "ARK_API_KEY is not configured", False
        try:
            async with asyncio.timeout(timeout):
                await ark.validate_api_key()
        except ModelArkError as exc:
            return f"ARK_API_KEY was rejected with HTTP {exc.status_code}", False
        except TimeoutError:
            return "ARK_API_KEY validation timed out", True
        except httpx.HTTPError:
            return "ARK_API_KEY validation could not reach ModelArk", True
        except Exception:
            logger.exception("Unexpected ARK_API_KEY validation failure")
            return "ARK_API_KEY validation failed unexpectedly", False
        return None, False

    async def iam() -> tuple[str | None, bool]:
        if not settings.byteplus_access_key_id:
            return "BYTEPLUS_ACCESS_KEY_ID is not configured", False
        if not settings.byteplus_secret_access_key:
            return "BYTEPLUS_SECRET_ACCESS_KEY is not configured", False
        try:
            async with asyncio.timeout(timeout):
                await assets.validate_management_access()
        except AssetAPIError:
            return (
                "BYTEPLUS_ACCESS_KEY_ID/BYTEPLUS_SECRET_ACCESS_KEY "
                "were rejected by the ModelArk management API",
                False,
            )
        except TimeoutError:
            return "IAM credential validation timed out", True
        except httpx.HTTPError:
            return (
                "IAM credential validation could not reach the ModelArk management API",
                True,
            )
        except Exception:
            logger.exception("Unexpected IAM credential validation failure")
            return "IAM credential validation failed unexpectedly", False
        return None, False

    async def check() -> list[ComponentResult]:
        (ark_message, ark_down), (iam_message, iam_down) = await asyncio.gather(
            ark_api_key(), iam()
        )
        return [("ark_api_key", ark_message, ark_down), ("iam", iam_message, iam_down)]

    return check


def google_check(
    settings: Settings, http: httpx.AsyncClient, token_source: TokenSource | None
) -> Check:
    timeout = settings.credential_validation_timeout_seconds

    async def gemini() -> str | None:
        response = await http.get(
            f"{settings.gemini_base_url.rstrip('/')}/models",
            params={"pageSize": 1},
            headers={"x-goog-api-key": settings.gemini_api_key},
        )
        if response.is_success:
            return None
        if response.status_code >= 500:
            raise httpx.HTTPError(f"HTTP {response.status_code}")
        return f"GEMINI_API_KEY was rejected with HTTP {response.status_code}"

    async def vertex() -> str | None:
        try:
            token = await token_source()  # type: ignore[misc]
        except Exception as exc:
            return (
                "GOOGLE_APPLICATION_CREDENTIALS could not produce an access token: "
                f"{type(exc).__name__}"
            )
        response = await http.get(
            f"https://aiplatform.googleapis.com/v1beta1/projects/"
            f"{settings.vertex_project}/locations/global/interactions",
            params={"pageSize": 1},
            headers={
                "authorization": f"Bearer {token}",
                "x-goog-user-project": settings.vertex_project,
            },
        )
        if response.is_success:
            return None
        if response.status_code >= 500:
            raise httpx.HTTPError(f"HTTP {response.status_code}")
        return (
            "VERTEX_PROJECT/GOOGLE_APPLICATION_CREDENTIALS were rejected by "
            f"Vertex AI with HTTP {response.status_code}"
        )

    async def check() -> list[ComponentResult]:
        calls: list[tuple[str, str, Callable[[], Awaitable[str | None]]]] = []
        if settings.gemini_api_key:
            calls.append(("gemini", "GEMINI_API_KEY", gemini))
        if settings.vertex_project:
            calls.append(("vertex", "Vertex AI credential", vertex))
        results = await asyncio.gather(
            *(_guarded(timeout, label, "Google", call) for _, label, call in calls)
        )
        return [
            (component, message, down)
            for (component, _, _), (message, down) in zip(calls, results, strict=True)
        ]

    return check


def kling_check(settings: Settings, http: httpx.AsyncClient) -> Check:
    timeout = settings.credential_validation_timeout_seconds

    async def account() -> str | None:
        now = int(time.time() * 1000)
        response = await http.get(
            f"{settings.kling_base_url.rstrip('/')}/account/costs",
            params={"start_time": now - 86_400_000, "end_time": now},
            headers={"authorization": f"Bearer {settings.kling_api_key}"},
        )
        try:
            code = response.json().get("code")
        except ValueError:
            code = None
        if response.is_success and code == 0:
            return None
        if response.status_code >= 500 or code in (1302, 1303):
            raise httpx.HTTPError(f"HTTP {response.status_code}")
        return (
            f"KLING_API_KEY was rejected with HTTP {response.status_code} (code {code})"
        )

    async def check() -> list[ComponentResult]:
        message, down = await _guarded(timeout, "KLING_API_KEY", "Kling", account)
        return [("api_key", message, down)]

    return check


class CredentialMonitor:
    def __init__(self, checks: dict[str, Check | None], *, validate: bool) -> None:
        self.checks = checks
        self.state: dict[str, dict[str, Any]] = {}
        for name, check in checks.items():
            status = (
                "disabled" if check is None else ("checking" if validate else "valid")
            )
            self.state[name] = {
                "status": status,
                "message": None,
                "last_checked_at": None,
            }

    def enabled(self, name: str) -> bool:
        return self.state.get(name, {}).get("status", "disabled") != "disabled"

    def needs_recheck(self) -> bool:
        return any(
            state["status"] not in {"valid", "disabled"}
            for state in self.state.values()
        )

    async def refresh(self) -> None:
        names = [name for name, check in self.checks.items() if check is not None]
        results = await asyncio.gather(*(self.checks[name]() for name in names))  # type: ignore[misc]
        for name, components in zip(names, results, strict=True):
            self._apply(name, components)

    def _apply(self, name: str, components: list[ComponentResult]) -> None:
        state = self.state[name]
        fields: dict[str, str] = {}
        for component, message, unreachable in components:
            if message is None:
                fields[component] = "valid"
            elif unreachable:
                # Keep a credential that already worked; otherwise stay
                # undecided so the fast recheck loop can settle it.
                fields[component] = (
                    "valid" if state.get(component) == "valid" else "checking"
                )
            else:
                fields[component] = "invalid"
        if "invalid" in fields.values():
            status = "invalid"
        elif "checking" in fields.values():
            status = "checking"
        else:
            status = "valid"
        errors = [message for _, message, _ in components if message]
        state.update(
            status=status,
            message="; ".join(errors) if errors else None,
            last_checked_at=datetime.now(UTC).isoformat(),
            **fields,
        )
        if errors:
            logger.warning(
                "%s credential check reported %s: %s",
                LABELS.get(name, name),
                status,
                "; ".join(errors),
            )

    def require(self, name: str) -> None:
        state = self.state.get(name)
        if state is None or state["status"] == "disabled":
            raise ProviderUnavailable(
                f"The '{name}' provider is not configured on this proxy"
            )
        label = LABELS.get(name, name)
        message = state["message"] or "validation is still pending"
        if state["status"] == "checking":
            raise ProviderCredentialsError(
                f"{label} credentials could not be validated yet: {message}",
                "upstream_credentials_unavailable",
            )
        if state["status"] == "invalid":
            raise ProviderCredentialsError(
                f"{label} credentials are currently invalid: {message}",
                "upstream_credentials_invalid",
            )

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return deepcopy(self.state)
