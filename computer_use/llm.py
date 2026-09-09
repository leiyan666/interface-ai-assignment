"""Provider boundary for discovery decisions."""

from __future__ import annotations

import json
import os
from typing import Protocol

from dotenv import load_dotenv
from openai import OpenAI

from .schema import Action, Observation, Target


class LLMClient(Protocol):
    def decide(self, goal: str, observation: Observation, history: list[dict]) -> Action: ...


class OpenAIClient:
    def __init__(self) -> None:
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for discovery")
        self.model = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        self.client = OpenAI(api_key=api_key)

    def decide(self, goal: str, observation: Observation, history: list[dict]) -> Action:
        prompt = {
            "goal": goal,
            "observation": observation.model_dump(),
            "recent_history": history[-6:],
            "allowed_actions": ["click", "type", "extract", "navigate", "wait", "finish", "escalate"],
            "instructions": "Choose exactly one next action. Use semantic role/name targets. Finish only after success is observed; escalate for a dialog or unsafe blocker. Return JSON matching Action.",
        }
        messages = [
            {"role": "system", "content": "You are a careful browser discovery agent. Return exactly one flat JSON Action object with keys action_type, target, value, output_name, reason. Do not wrap it in an action key. Use target role/name, never an element ref."},
            {"role": "user", "content": json.dumps(prompt)},
        ]
        last_error: Exception | None = None
        for attempt in range(2):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            try:
                return _parse_action(json.loads(content), observation)
            except Exception as exc:
                last_error = exc
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": "Your JSON did not match the required flat Action schema. Retry with action_type, target, value, output_name, and reason."})
        raise ValueError(f"LLM returned an invalid action after retry: {last_error}")


def _parse_action(payload: dict, observation: Observation) -> Action:
    """Accept minor provider formatting variations without weakening the schema."""
    data = payload.get("action", payload)
    if not isinstance(data, dict):
        raise ValueError("action must be an object")
    data = dict(data)
    if "action_type" not in data and "type" in data:
        data["action_type"] = data.pop("type")
    target = data.get("target")
    if isinstance(target, str):
        # Some models express a semantic target as its visible label.
        data["target"] = Target(name=target.rstrip(":" ).strip())
        target = data["target"]
    if isinstance(target, dict) and "ref" in target:
        element = next((item for item in observation.elements if item.ref == target["ref"]), None)
        if element is None:
            raise ValueError(f"Unknown observation ref: {target['ref']}")
        data["target"] = Target(role=element.role, name=element.name, text=element.text)
    return Action.model_validate(data)
