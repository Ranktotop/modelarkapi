"""Capability document v2 (docs/SPEC.md, section 13).

One description per model drives request validation, `/v1/models`, the LiteLLM
export, and the studio's forms, so clients can check what a model accepts
before they call it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RESOLUTION_ORDER = ("360p", "480p", "720p", "1080p", "4k")


@dataclass(frozen=True)
class Param:
    """Allowed values for one request parameter (an empty Param allows any)."""

    values: tuple[Any, ...] | None = None
    minimum: float | None = None
    maximum: float | None = None
    default: Any = None

    def to_dict(self) -> dict[str, Any]:
        document: dict[str, Any] = {}
        if self.values is not None:
            document["values"] = list(self.values)
        if self.minimum is not None:
            document["min"] = self.minimum
        if self.maximum is not None:
            document["max"] = self.maximum
        if self.default is not None:
            document["default"] = self.default
        return document


@dataclass(frozen=True)
class ReferenceSlot:
    role: str
    types: tuple[str, ...]
    minimum: int = 0
    maximum: int = 1
    max_bytes: int | None = None
    formats: tuple[str, ...] | None = None
    min_seconds: float | None = None
    max_seconds: float | None = None
    total_max_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "role": self.role,
            "types": list(self.types),
            "min": self.minimum,
            "max": self.maximum,
        }
        for key in ("max_bytes", "min_seconds", "max_seconds", "total_max_seconds"):
            value = getattr(self, key)
            if value is not None:
                document[key] = value
        if self.formats is not None:
            document["formats"] = list(self.formats)
        return document


@dataclass(frozen=True)
class GroupLimit:
    """Caps the combined count of several reference types, e.g. images + elements."""

    roles: tuple[str, ...]
    types: tuple[str, ...]
    maximum: int
    when_has: tuple[str, ...] | None = None
    when_lacks: tuple[str, ...] | None = None

    def applies(self, present_types: set[str]) -> bool:
        if self.when_has and not present_types.intersection(self.when_has):
            return False
        return not (self.when_lacks and present_types.intersection(self.when_lacks))

    def to_dict(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "roles": list(self.roles),
            "types": list(self.types),
            "max": self.maximum,
        }
        condition: dict[str, Any] = {}
        if self.when_has:
            condition["has"] = list(self.when_has)
        if self.when_lacks:
            condition["lacks"] = list(self.when_lacks)
        if condition:
            document["if"] = condition
        return document


@dataclass(frozen=True)
class TaskSpec:
    references: tuple[ReferenceSlot, ...] = ()
    parameters: dict[str, Param] = field(default_factory=dict)
    limits: tuple[GroupLimit, ...] = ()
    prompt_required: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        document: dict[str, Any] = {}
        if self.references:
            document["references"] = [slot.to_dict() for slot in self.references]
        if self.parameters:
            document["parameters"] = {
                name: param.to_dict() for name, param in self.parameters.items()
            }
        if self.limits:
            document["limits"] = [limit.to_dict() for limit in self.limits]
        if self.prompt_required is not None:
            document["prompt_required"] = self.prompt_required
        return document


@dataclass(frozen=True)
class Constraint:
    """When every `when` field holds one of its values, `then` fields are narrowed.

    The pseudo-field `task` matches the resolved task.
    """

    when: dict[str, tuple[Any, ...]]
    then: dict[str, tuple[Any, ...]]
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "if": {key: list(values) for key, values in self.when.items()},
            "then": {key: list(values) for key, values in self.then.items()},
            "message": self.message,
        }


@dataclass(frozen=True)
class ModelCapabilities:
    provider: str
    family: str
    parameters: dict[str, Param]
    tasks: dict[str, TaskSpec]
    constraints: tuple[Constraint, ...] = ()
    backend: str | None = None
    launch_stage: str | None = None
    prompt_max_chars: int | None = None
    prompt_required: bool = True
    max_outputs: int = 1
    output_types: tuple[str, ...] = ("video",)
    continuation: str = "none"
    features: dict[str, bool] = field(default_factory=dict)
    provider_options: tuple[str, ...] = ()
    # Request fields that are valid for this provider but are not unified
    # parameters (e.g. ModelArk's legacy passthrough fields).
    native_fields: tuple[str, ...] = ()

    def task_parameters(self, task: str) -> dict[str, Param]:
        parameters = dict(self.parameters)
        spec = self.tasks.get(task)
        if spec:
            parameters.update(spec.parameters)
        return parameters

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "provider": self.provider,
            "backend": self.backend,
            "family": self.family,
            "launch_stage": self.launch_stage,
            "prompt": {
                "max_chars": self.prompt_max_chars,
                "required": self.prompt_required,
            },
            "outputs": {"max": self.max_outputs, "types": list(self.output_types)},
            "parameters": {
                name: param.to_dict() for name, param in self.parameters.items()
            },
            "tasks": {name: spec.to_dict() for name, spec in self.tasks.items()},
            "constraints": [constraint.to_dict() for constraint in self.constraints],
            "continuation": self.continuation,
            "features": dict(self.features),
            "provider_options": list(self.provider_options),
        }
