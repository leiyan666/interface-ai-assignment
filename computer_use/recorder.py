"""Compile a discovery trajectory into a reviewable capability artifact."""

from __future__ import annotations

from datetime import datetime, timezone

from .schema import (
    BusinessOutcomeSpec, Capability, CapabilityMetadata, CapabilityStep, Checkpoint,
    InputSpec, OutputSpec, SafetyPolicy, Target, TargetApp,
)


def _parameterize(value: str | None, concrete_member_id: str | None) -> str | None:
    if value is None or not concrete_member_id:
        return value
    return "{{member_id}}" if value == concrete_member_id else value


def _trajectory_steps(trajectory: list[dict]) -> tuple[list[CapabilityStep], str | None]:
    """Turn successful executed actions into ordered, replayable steps."""
    steps: list[CapabilityStep] = []
    concrete_member_id: str | None = None
    seen: set[tuple[str, str]] = set()

    for item in trajectory:
        action_data = item.get("action", {})
        result = item.get("result", {})
        if result.get("ok") is False:
            continue
        action_type = action_data.get("action_type", action_data.get("type"))
        if action_type not in {"click", "type", "extract", "navigate", "wait"}:
            continue
        target_data = action_data.get("target")
        target = Target.model_validate(target_data) if target_data else None
        value = action_data.get("value")
        if action_type == "type" and value and concrete_member_id is None:
            concrete_member_id = str(value)
        signature = (action_type, target.model_dump_json() if target else "")
        if action_type == "extract" and signature in seen:
            continue
        seen.add(signature)
        output_name = action_data.get("output_name")
        if action_type == "extract" and output_name is None:
            output_name = "savings_balance"
        elif action_type == "extract":
            # This capability has one declared output; normalize model prose to its contract name.
            output_name = "savings_balance"
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
            risk="safe_write" if action_type == "type" else "read",
        ))
    return steps, concrete_member_id


def compile_lookup_capability(entry_point: str, trajectory: list[dict]) -> Capability:
    """Compile the successful executed trajectory, with only small demo normalization."""
    steps, concrete_member_id = _trajectory_steps(trajectory)
    for step in steps:
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
