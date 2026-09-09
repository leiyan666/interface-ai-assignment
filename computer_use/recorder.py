"""Compile a discovery trajectory into a reviewable capability artifact."""

from __future__ import annotations

from datetime import datetime, timezone
from .safety import action_risk
from .success import parse_balance

from .schema import (
    BusinessOutcomeSpec, Capability, CapabilityMetadata, CapabilityStep, Checkpoint,
    InputSpec, OutputSpec, SafetyPolicy, Target, TargetApp, Action,
)


def _parameterize(value: str | None, concrete_member_id: str | None) -> str | None:
    if value is None or not concrete_member_id:
        return value
    return "{{member_id}}" if value == concrete_member_id else value


def _trajectory_steps(trajectory: list[dict]) -> tuple[list[CapabilityStep], str | None]:
    """Turn successful executed actions into ordered, replayable steps."""
    steps: list[CapabilityStep] = []
    concrete_member_id: str | None = None
    phase = -1

    for item in trajectory:
        action_data = item.get("action", {})
        result = item.get("result", {})
        if result.get("ok") is not True:
            continue
        action_type = action_data.get("action_type", action_data.get("type"))
        if action_type not in {"click", "type", "extract"}:
            continue
        next_phase = {"type": 0, "click": 1, "extract": 2}[action_type]
        if next_phase < phase or next_phase > phase + 1:
            raise ValueError("Lookup trajectory must follow type -> click -> extract order")
        phase = next_phase
        target_data = action_data.get("target")
        target = Target.model_validate(target_data) if target_data else None
        if target is None or not any((target.role, target.name, target.text, target.near_text, target.fallbacks)):
            raise ValueError("Every lookup action requires a target")
        value = action_data.get("value")
        if action_type == "type":
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Lookup trajectory requires a non-empty member ID")
            if concrete_member_id is not None and value != concrete_member_id:
                raise ValueError("Lookup trajectory has ambiguous member ID values")
            concrete_member_id = value
        if action_type == "extract" and parse_balance(result.get("value")) is None:
            raise ValueError("Lookup trajectory requires a verified monetary extraction")
        # The demo has one declared output; non-extract actions have no output.
        output_name = "savings_balance" if action_type == "extract" else None
        checkpoint = None
        if action_type == "type" and target:
            checkpoint = Checkpoint(type="value_equals", target=target, value=value)
        elif action_type == "click":
            checkpoint = Checkpoint(type="any_of", conditions=[Checkpoint(type="text_visible", value=text) for text in ["Savings Account", "Member not found", "No savings account", "Permission denied"]])
        elif action_type == "extract":
            checkpoint = Checkpoint(type="output_extracted", output_name=output_name)
        steps.append(CapabilityStep(
            id=f"step_{len(steps) + 1}", action=action_type, target=target,
            value=value, output_name=output_name, checkpoint=checkpoint,
            risk=action_risk(Action(action_type=action_type, target=target,
                risk=action_data.get("risk", "read"), reason="compile executed action")),
        ))
    if phase != 2 or concrete_member_id is None:
        raise ValueError("Lookup trajectory requires successful type, click and extract actions")
    return steps, concrete_member_id


def compile_lookup_capability(entry_point: str, trajectory: list[dict]) -> Capability:
    """Compile the successful executed trajectory, with only small demo normalization."""
    steps, concrete_member_id = _trajectory_steps(trajectory)
    for step in steps:
        if step.action == "type":
            step.value = _parameterize(step.value, concrete_member_id)
        if step.checkpoint and step.checkpoint.type == "value_equals":
            step.checkpoint.value = _parameterize(step.checkpoint.value, concrete_member_id)
    return Capability(
        capability_id="lookup_savings_balance",
        name="Lookup Savings Balance",
        description="Look up a member and return their savings balance.",
        target_app=TargetApp(app_id="mock_credit_union", entry_point=entry_point),
        inputs=[InputSpec(name="member_id", type="string", description="Synthetic member number")],
        outputs=[OutputSpec(name="savings_balance", type="number")],
        steps=steps,
        success_condition=Checkpoint(type="output_extracted", output_name="savings_balance"),
        business_outcomes=[
            BusinessOutcomeSpec(code="MEMBER_NOT_FOUND", description="The member number is not in the console.", checkpoint=Checkpoint(type="text_visible", value="Member not found")),
            BusinessOutcomeSpec(code="NO_SAVINGS_ACCOUNT", description="The member has no savings account.", checkpoint=Checkpoint(type="text_visible", value="No savings account")),
            BusinessOutcomeSpec(code="PERMISSION_DENIED", description="The employee lacks access to this member.", checkpoint=Checkpoint(type="text_visible", value="Permission denied")),
        ],
        safety_policy=SafetyPolicy(),
        metadata=CapabilityMetadata(created_at=datetime.now(timezone.utc).isoformat(), tags=["browser", "read-only"]),
    )
