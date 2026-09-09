"""Checkpoint evaluation and safe, retrying action execution."""

from __future__ import annotations

import re
import time
from typing import Any

from .schema import Action, ActionResult, Checkpoint, Observation
from .safety import validate_action
from .schema import SafetyPolicy
from .surface import SurfaceAdapter

PARAMETER = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}")


def substitute(value: str | None, parameters: dict[str, Any]) -> str | None:
    if value is None:
        return None
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in parameters:
            raise ValueError(f"Missing runtime parameter: {key}")
        return str(parameters[key])
    return PARAMETER.sub(replace, value)


def resolve_action(action: Action, parameters: dict[str, Any]) -> Action:
    return action.model_copy(update={"value": substitute(action.value, parameters)})


def resolve_checkpoint(checkpoint: Checkpoint, parameters: dict[str, Any]) -> Checkpoint:
    updates = {
        "value": substitute(checkpoint.value, parameters),
        "conditions": [resolve_checkpoint(item, parameters) for item in checkpoint.conditions],
    }
    return checkpoint.model_copy(update=updates)


def check_checkpoint(checkpoint: Checkpoint, surface: SurfaceAdapter, outputs: dict[str, Any]) -> bool:
    observation: Observation = surface.observe()
    if checkpoint.type == "text_visible":
        return (checkpoint.value or "").lower() in observation.visible_text.lower()
    if checkpoint.type == "element_visible":
        return bool(checkpoint.target and _target_exists(checkpoint.target, surface))
    if checkpoint.type == "url_matches":
        return bool(checkpoint.value and checkpoint.value in surface.current_url())
    if checkpoint.type == "output_extracted":
        return checkpoint.output_name in outputs
    if checkpoint.type == "value_equals":
        if not checkpoint.target:
            return False
        return surface.resolve(checkpoint.target).input_value() == checkpoint.value
    if checkpoint.type == "any_of":
        return any(check_checkpoint(item, surface, outputs) for item in checkpoint.conditions)
    if checkpoint.type == "all_of":
        return all(check_checkpoint(item, surface, outputs) for item in checkpoint.conditions)
    return False


def _target_exists(target, surface: SurfaceAdapter) -> bool:
    try:
        surface.resolve(target)
        return True
    except Exception:
        return False


def execute_with_retry(action: Action, surface: SurfaceAdapter, policy: SafetyPolicy, retries: int = 0) -> ActionResult:
    validate_action(action, policy, surface.current_url())
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return surface.execute(action)
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.25 * (attempt + 1))
    assert last_error is not None
    raise last_error
