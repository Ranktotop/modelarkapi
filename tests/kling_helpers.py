"""Shared test helper for Kling request bodies."""

from __future__ import annotations

from typing import Any


def strip_external(body: dict[str, Any]) -> dict[str, Any]:
    """Drop the per-request external task ID (tested in test_create_recovery)."""
    body = dict(body)
    body.pop("external_task_id", None)
    options = body.get("options")
    if isinstance(options, dict) and "external_task_id" in options:
        options = {k: v for k, v in options.items() if k != "external_task_id"}
        if options:
            body["options"] = options
        else:
            body.pop("options")
    return body
