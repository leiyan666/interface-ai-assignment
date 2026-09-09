"""Compile a discovery trajectory into a reviewable capability artifact."""

from __future__ import annotations

from datetime import datetime, timezone

from .schema import (
    BusinessOutcomeSpec, Capability, CapabilityMetadata, CapabilityStep, Checkpoint,
    InputSpec, OutputSpec, SafetyPolicy, Target, TargetApp,
)


def compile_lookup_capability(entry_point: str, trajectory: list[dict]) -> Capability:
    """The demo compiler intentionally emits a small canonical capability."""
    return Capability(
        capability_id="lookup_savings_balance",
        name="Lookup Savings Balance",
        description="Look up a member and return their savings balance.",
        target_app=TargetApp(app_id="mock_credit_union", entry_point=entry_point),
        inputs=[InputSpec(name="member_id", type="string", description="Synthetic member number")],
        outputs=[OutputSpec(name="savings_balance", type="number")],
        steps=[
            CapabilityStep(
                id="step_1", action="type", target=Target(role="textbox", name="Member Number", frame_hint="Member Lookup"),
                value="{{member_id}}", checkpoint=Checkpoint(type="value_equals", target=Target(role="textbox", name="Member Number", frame_hint="Member Lookup"), value="{{member_id}}"), risk="safe_write",
            ),
            CapabilityStep(
                id="step_2", action="click", target=Target(role="button", name="Search", frame_hint="Member Lookup"),
                checkpoint=Checkpoint(type="any_of", conditions=[Checkpoint(type="text_visible", value=value) for value in ["Savings Account", "Member not found", "No savings account", "Permission denied"]]),
            ),
            CapabilityStep(
                id="step_3", action="extract", target=Target(near_text="Savings Account", frame_hint="Member Lookup"), output_name="savings_balance",
                checkpoint=Checkpoint(type="output_extracted", output_name="savings_balance"),
            ),
        ],
        success_condition=Checkpoint(type="output_extracted", output_name="savings_balance"),
        business_outcomes=[
            BusinessOutcomeSpec(code="MEMBER_NOT_FOUND", description="The member number is not in the console.", checkpoint=Checkpoint(type="text_visible", value="Member not found")),
            BusinessOutcomeSpec(code="NO_SAVINGS_ACCOUNT", description="The member has no savings account.", checkpoint=Checkpoint(type="text_visible", value="No savings account")),
            BusinessOutcomeSpec(code="PERMISSION_DENIED", description="The employee lacks access to this member.", checkpoint=Checkpoint(type="text_visible", value="Permission denied")),
        ],
        safety_policy=SafetyPolicy(),
        metadata=CapabilityMetadata(created_at=datetime.now(timezone.utc).isoformat(), tags=["browser", "read-only"]),
    )
