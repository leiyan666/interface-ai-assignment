"""Observe-decide-act discovery loop."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from .handoff import handoff
from .llm import LLMClient
from .logging_utils import JsonlLogger
from .recorder import compile_lookup_capability
from .safety import SafetyViolation, validate_action
from .schema import Action, SafetyPolicy
from .surface import PlaywrightSurface


def discover(goal: str, target: str, client: LLMClient, headless: bool = False, max_steps: int = 12) -> Path:
    run_id = uuid.uuid4().hex[:10]
    logger = JsonlLogger("evidence/discovery_success.jsonl", run_id, "discovery")
    surface = PlaywrightSurface(target, headless=headless)
    trajectory: list[dict] = []
    try:
        surface.start()
        for step_number in range(1, max_steps + 1):
            observation = surface.observe()
            logger.event("observation", step=step_number, url=observation.url, element_count=len(observation.elements))
            if observation.dialog_present:
                handoff(surface, logger, "evidence/failure_or_handoff.png")
                observation = surface.observe()
            action = client.decide(goal, observation, trajectory)
            logger.event("action_proposed", step=step_number, action=action.action_type, reason=action.reason)
            if action.action_type == "escalate":
                handoff(surface, logger, "evidence/failure_or_handoff.png")
                continue
            validate_action(action, SafetyPolicy(), surface.current_url())
            result = surface.execute(action)
            trajectory.append({"step": step_number, "action": action.model_dump(), "result": result.model_dump()})
            logger.event("action_executed", step=step_number, action=action.action_type, target=action.target.model_dump() if action.target else None, value=action.value, output_name=action.output_name, reason=action.reason, status="ok")
            # A successful extraction is sufficient evidence that this demo goal is complete,
            # even if a provider keeps repeating the extraction instead of saying finish.
            goal_complete = action.action_type == "finish" or (action.action_type == "extract" and result.value)
            if goal_complete:
                artifact = compile_lookup_capability(target, trajectory)
                path = Path("artifacts/lookup_savings_balance.json")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(artifact.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8")
                Path("evidence/discovery_trajectory.json").write_text(json.dumps(trajectory, indent=2) + "\n", encoding="utf-8")
                logger.event("discovery_completed", step=step_number, artifact=str(path), reason="finish action or successful extraction")
                return path
            time.sleep(0.1)
        raise RuntimeError("Discovery stopped after max_steps without a finish action")
    finally:
        surface.close()
