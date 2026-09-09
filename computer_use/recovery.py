"""Bounded recovery for the demo's read-only member lookup submission."""

import time
from collections.abc import Callable

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .executor import execute_with_retry
from .logging_utils import JsonlLogger
from .schema import Action, ActionResult, Observation, SafetyPolicy
from .surface import SurfaceAdapter

MAX_TRANSIENT_RETRIES = 3


def is_transient(observation: Observation) -> bool:
    return any(text in observation.visible_text.casefold() for text in (
        "temporarily busy", "temporarily unavailable", "temporary unavailable",
    ))


def safe_lookup_submission(app_id: str, action: Action, previous: Action | None) -> bool:
    # Explicitly scoped to our synthetic read-only lookup, not arbitrary clicks.
    return bool(
        app_id == "mock_credit_union" and action.action_type == "click"
        and action.target and action.target.name == "Search"
        and previous and previous.action_type == "type" and previous.target
        and (previous.target.name or "").strip().rstrip(":") == "Member Number"
    )


def execute_lookup_with_recovery(
    action: Action, member_input: Action, surface: SurfaceAdapter,
    policy: SafetyPolicy, logger: JsonlLogger, step_id: str,
    intervene: Callable[[str], None],
) -> ActionResult:
    result = ActionResult(ok=False)
    for attempt in range(MAX_TRANSIENT_RETRIES + 1):
        try:
            if attempt:
                logger.event("retry", step=step_id, retry=attempt, max_retries=MAX_TRANSIENT_RETRIES)
                print(f"Temporary lookup failure: retry {attempt}/{MAX_TRANSIENT_RETRIES}")
                time.sleep(0.25 * attempt)
                # The legacy response clears the form. Restore the original input
                # before resubmission, using the saved semantic action and policy.
                execute_with_retry(member_input, surface, policy)
            result = execute_with_retry(action, surface, policy)
            surface.wait_for_dialog()
            observation = surface.observe()
            if observation.dialog_present:
                intervene("Unexpected dialog during lookup")
                return result
            if not is_transient(observation):
                return result
            reason = "Lookup returned a temporary unavailable/busy state"
        except PlaywrightTimeoutError:
            reason = "Read-only lookup timed out"
        logger.event("recoverable_condition", step=step_id, attempt=attempt, message=reason)
    logger.event("retry_exhausted", step=step_id, retries=MAX_TRANSIENT_RETRIES)
    intervene(f"{reason}; exhausted {MAX_TRANSIENT_RETRIES} retries")
    if is_transient(surface.observe()):
        raise RuntimeError("Lookup remains busy after human intervention")
    return result
