"""Validation of unified requests against a model's capability document.

`strict` (the default) rejects anything the model cannot do, naming the
allowed values. `adapt` moves values to the nearest supported one, drops
unsupported optional fields, and records every change in `adjustments`.
Missing inputs and unsupported tasks are rejected under both policies.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import TYPE_CHECKING, Any

from .capabilities import RESOLUTION_ORDER, ModelCapabilities, Param
from .translation import TranslationError

if TYPE_CHECKING:
    from .unified import UnifiedRequest


class ContractError(TranslationError):
    """A request that breaks the API contract; maps to an HTTP 400."""

    def __init__(
        self, message: str, *, code: str = "invalid_request", param: str | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.param = param


def _same(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, int | float) and isinstance(right, int | float):
        return float(left) == float(right)
    return left == right


def _allowed(value: Any, values: tuple[Any, ...]) -> bool:
    return any(_same(value, candidate) for candidate in values)


def _ratio(value: str) -> float | None:
    try:
        width, height = (float(part) for part in value.split(":"))
        return math.log(width / height)
    except (ValueError, ZeroDivisionError):
        return None


def nearest(value: Any, values: tuple[Any, ...], default: Any = None) -> Any:
    """Closest supported value; ties prefer the larger number or the lower resolution."""
    numbers = [
        v for v in values if isinstance(v, int | float) and not isinstance(v, bool)
    ]
    if isinstance(value, int | float) and not isinstance(value, bool) and numbers:
        return min(numbers, key=lambda v: (abs(v - value), -v))
    if value in RESOLUTION_ORDER:
        tiers = [v for v in values if v in RESOLUTION_ORDER]
        if tiers:
            index = RESOLUTION_ORDER.index(value)
            return min(
                tiers,
                key=lambda v: (
                    abs(RESOLUTION_ORDER.index(v) - index),
                    RESOLUTION_ORDER.index(v),
                ),
            )
    if isinstance(value, str) and _ratio(value) is not None:
        ratios = [v for v in values if isinstance(v, str) and _ratio(v) is not None]
        if ratios:
            target = _ratio(value)
            return min(ratios, key=lambda v: abs(_ratio(v) - target))  # type: ignore[operator]
    if default is not None and _allowed(default, values):
        return default
    return values[0]


def _check_value(
    name: str,
    value: Any,
    param: Param,
    policy: str,
    adjustments: list[dict[str, Any]],
    reason: str | None = None,
) -> Any:
    if param.values is not None and not _allowed(value, param.values):
        if policy == "adapt":
            applied = nearest(value, param.values, param.default)
            adjustments.append(
                {
                    "field": name,
                    "requested": value,
                    "applied": applied,
                    "reason": reason or "value not supported by the model",
                }
            )
            return applied
        supported = ", ".join(str(v) for v in param.values)
        message = reason or f"The model does not support {name}={value}"
        raise ContractError(
            f"{message}; supported values: {supported}",
            code="unsupported_parameter",
            param=name,
        )
    if isinstance(value, int | float) and not isinstance(value, bool):
        low, high = param.minimum, param.maximum
        if (low is not None and value < low) or (high is not None and value > high):
            if policy == "adapt":
                applied = min(
                    max(value, low if low is not None else value),
                    high if high is not None else value,
                )
                adjustments.append(
                    {
                        "field": name,
                        "requested": value,
                        "applied": applied,
                        "reason": "value out of range",
                    }
                )
                return applied
            raise ContractError(
                f"{name} must be between {low} and {high}",
                code="unsupported_parameter",
                param=name,
            )
    return value


def _check_references(caps: ModelCapabilities, request: UnifiedRequest) -> None:
    spec = caps.tasks[request.task]
    slots = {slot.role: slot for slot in spec.references}
    counts: Counter[str] = Counter()
    for reference in request.references:
        role = reference["role"]
        slot = slots.get(role)
        if slot is None:
            allowed = ", ".join(slots) or "none"
            raise ContractError(
                f"Task {request.task} does not accept references with role '{role}' "
                f"on this model; allowed roles: {allowed}",
                code="reference_limit",
                param="references",
            )
        if reference["type"] not in slot.types:
            raise ContractError(
                f"Role '{role}' accepts {', '.join(slot.types)} references, "
                f"not {reference['type']}",
                code="reference_limit",
                param="references",
            )
        counts[role] += 1
    for slot in spec.references:
        if counts[slot.role] < slot.minimum:
            raise ContractError(
                f"Task {request.task} needs at least {slot.minimum} "
                f"{'/'.join(slot.types)} reference(s) with role '{slot.role}'",
                code="reference_limit",
                param="references",
            )
        if counts[slot.role] > slot.maximum:
            raise ContractError(
                f"Task {request.task} accepts at most {slot.maximum} references "
                f"with role '{slot.role}' on this model",
                code="reference_limit",
                param="references",
            )
    present = {reference["type"] for reference in request.references}
    for limit in spec.limits:
        if not limit.applies(present):
            continue
        total = sum(
            1
            for reference in request.references
            if reference["role"] in limit.roles and reference["type"] in limit.types
        )
        if total > limit.maximum:
            raise ContractError(
                f"Task {request.task} accepts at most {limit.maximum} "
                f"{' + '.join(limit.types)} references in this combination",
                code="reference_limit",
                param="references",
            )


def validate(
    caps: ModelCapabilities, request: UnifiedRequest, policy: str | None = None
) -> tuple[UnifiedRequest, list[dict[str, Any]]]:
    policy = policy or request.policy
    adjustments: list[dict[str, Any]] = []
    if request.task not in caps.tasks:
        raise ContractError(
            f"The model does not support task {request.task}; supported tasks: "
            f"{', '.join(caps.tasks)}",
            code="unsupported_task",
            param="task",
        )
    spec = caps.tasks[request.task]

    prompt_required = (
        spec.prompt_required
        if spec.prompt_required is not None
        else caps.prompt_required
    )
    if request.task == "text_to_video" and not request.prompt:
        prompt_required = True
    if prompt_required and not request.prompt:
        raise ContractError("prompt is required for this task", param="prompt")
    if caps.prompt_max_chars and len(request.prompt) > caps.prompt_max_chars:
        raise ContractError(
            f"prompt exceeds {caps.prompt_max_chars} characters",
            code="unsupported_parameter",
            param="prompt",
        )

    _check_references(caps, request)

    parameters = caps.task_parameters(request.task)
    for name in list(request.params):
        if name not in parameters:
            if policy == "adapt":
                adjustments.append(
                    {
                        "field": name,
                        "requested": request.params.pop(name),
                        "applied": None,
                        "reason": "parameter not supported by the model",
                    }
                )
                continue
            raise ContractError(
                f"The model does not support the parameter {name}",
                code="unsupported_parameter",
                param=name,
            )
        request.params[name] = _check_value(
            name, request.params[name], parameters[name], policy, adjustments
        )
    for name, param in spec.parameters.items():
        if name not in request.params and param.default is not None:
            request.params[name] = param.default

    for constraint in caps.constraints:
        matches = all(
            _allowed(request.task if key == "task" else request.params.get(key), values)
            for key, values in constraint.when.items()
        )
        if not matches:
            continue
        for key, values in constraint.then.items():
            if key not in request.params:
                # The model's default when the constraint allows it, else the
                # first allowed value.
                default = parameters[key].default if key in parameters else None
                request.params[key] = (
                    default
                    if default is not None and _allowed(default, values)
                    else values[0]
                )
                continue
            request.params[key] = _check_value(
                key,
                request.params[key],
                Param(values=values),
                policy,
                adjustments,
                reason=constraint.message,
            )

    for name in list(request.extras):
        if name in caps.native_fields:
            continue
        if policy == "adapt":
            adjustments.append(
                {
                    "field": name,
                    "requested": request.extras.pop(name),
                    "applied": None,
                    "reason": "field not supported by this provider",
                }
            )
            continue
        raise ContractError(
            f"Unknown field {name}",
            code="unsupported_parameter",
            param=name,
        )
    return request, adjustments
